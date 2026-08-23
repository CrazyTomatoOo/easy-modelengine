"""阶段引擎 —— Task 各阶段(下载/校验/传输)共用的文件级跟踪与判定机器。

纯 Python,无 Qt:与 TaskManager 的通信全部经回调注入(由 TaskManager 包装成
Qt 信号转发)。引擎只做四件事:文件完成/失败跟踪、活跃 worker 注册、阶段完成
判定、暂停/取消时的退役等待。阶段差异(worker 构造、恢复预跳过、校验结果写库)
由调用方在注入的回调与 begin() 流程中表达——download/verify/transfer 是同一台
机器的三个实例(Q4A 决策),不再是三套镜像处理器。

回调契约:
- is_blocked() -> bool      暂停/取消 guard:阶段被阻塞时完成判定不得推进
- on_progress(file_path, current, total)
- on_conclude(engine)        全部文件处理完且未阻塞时调用;调用方读取
                             has_failures() 决定路由
- on_result(file_path, result, success)  单文件结果回调(Q5B:校验的实际哈希
                             经此回写,下载/传输不消费)
"""

from typing import Callable, Optional


class StageEngine:
    def __init__(
        self,
        *,
        is_blocked: Callable[[], bool],
        on_conclude: Callable[['StageEngine'], None],
        on_progress: Optional[Callable[[str, int, int], None]] = None,
        on_result: Optional[Callable[[str, object, bool], None]] = None,
    ):
        self._is_blocked = is_blocked
        self._on_conclude = on_conclude
        self._on_progress = on_progress or (lambda *_args: None)
        self._on_result = on_result or (lambda *_args: None)

        self._total = 0
        self._completed: set[str] = set()
        self._failed: set[str] = set()
        self._active: dict[str, object] = {}
        self._retired: list = []

    # ---- 生命周期 ----

    def begin(self, total: int) -> None:
        """阶段开始:登记文件总数,重置跟踪状态。"""
        self._total = total
        self._completed.clear()
        self._failed.clear()
        self._active.clear()
        self._retired.clear()

    def mark_done(self, file_path: str) -> None:
        """预跳过文件(恢复续传的已完成文件、无源校验和的文件)——直接计完成。"""
        self._completed.add(file_path)

    def register(self, file_path: str, worker: object) -> None:
        """登记活跃 worker(cancel flag 与 done_event 的载体)。"""
        self._active[file_path] = worker

    def get_worker(self, file_path: str) -> object:
        """按路径取活跃 worker(供调用方读取校验结果等)。"""
        return self._active.get(file_path)

    def retire(self) -> list:
        """暂停/取消:把活跃 worker 全部拉进退役表(cancel flag 由调用方先置)。"""
        retired = list(self._active.values())
        self._active.clear()
        self._retired.extend(retired)
        return retired

    def wait_retired(self) -> None:
        """等待退役 worker 真正结束(其下载仍在写 .tmp,恢复前必须等完)。"""
        for worker in self._retired:
            done_event = getattr(worker, "done_event", None)
            if done_event is not None:
                done_event.wait()
        self._retired.clear()

    # ---- 单文件结果 ----

    def progress(self, file_path: str, current: int, total: int) -> None:
        self._on_progress(file_path, current, total)

    def finish(self, file_path: str, success: bool, result: object = None) -> object:
        """单文件完成/失败:记录、移除注册、回调结果、尝试收束。

        返回被移除的 worker(供调用方读取 result 之外的属性)。
        """
        worker = self._active.pop(file_path, None)
        if success:
            self._completed.add(file_path)
        else:
            self._failed.add(file_path)
        self._on_result(file_path, result, success)
        self._maybe_conclude()
        return worker

    # ---- 判定 ----

    def has_failures(self) -> bool:
        return bool(self._failed)

    def done(self) -> bool:
        return len(self._completed) + len(self._failed) >= self._total

    def maybe_conclude(self) -> None:
        """公开收束入口:begin()+mark_done 后全跳过场景需要主动触发。"""
        self._maybe_conclude()

    def _maybe_conclude(self) -> None:
        """全部处理完且未阻塞才推进(暂停/取消时残留信号不得推进)。"""
        if self.done() and not self._is_blocked():
            self._on_conclude(self)
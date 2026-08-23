from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool, QRunnable

from core.database import Database
from core.proxy_config import load as load_proxy
from core.task_config import TaskConfig, TaskType, TaskState, TaskFile, StageState
from core.interfaces import FileInfo
from core.task_intake import create_strategies
from core.stage_engine import StageEngine
from core.workers import DownloadWorker, TransferWorker, VerifyWorker
from core.server_profile import find as find_profile
from core.transfers.rsync_transfer import RsyncTransfer


class StageRunnable(QRunnable):
    def __init__(self, task_manager: 'TaskManager', task_id: str, stage_method: Callable[[str], None]):
        super().__init__()
        self._task_manager = task_manager
        self._task_id = task_id
        self._stage_method = stage_method

    def run(self):
        self._stage_method(self._task_id)


class TaskManager(QObject):
    task_state_changed = pyqtSignal(str, str)
    task_progress = pyqtSignal(str, str, int, int)
    task_error = pyqtSignal(str, str, str)
    task_warning = pyqtSignal(str, str, str)
    task_completed = pyqtSignal(str)
    task_failed = pyqtSignal(str)

    MAX_CONCURRENT_TASKS = 2

    def __init__(self, db: Database):
        super().__init__()
        self._db = db
        self._task_queue: list[str] = []
        self._active_tasks: set[str] = set()
        self._download_pool = QThreadPool()
        self._verify_pool = QThreadPool()
        self._transfer_pool = QThreadPool()

        # 每阶段一台 StageEngine(纯 Python 机器:文件跟踪/注册/判定/退役)
        self._engines: dict[str, StageEngine] = {}

    def create_task(self, config: TaskConfig) -> str:
        task_id = self._db.create_task(
            task_type=config.task_type.value,
            model_source=config.model_source,
            model_id=config.model_id,
            local_cache_dir=str(config.local_cache_dir),
            revision=config.revision,
            remote_host=config.remote_host,
            remote_path=config.remote_path,
            file_filter=config.file_filter
        )

        for task_file in config.files:
            self._db.add_task_file(
                task_id=task_id,
                file_path=task_file.file_path,
                file_size=task_file.file_size,
                expected_hash=task_file.expected_hash,
                hash_algorithm=task_file.hash_algorithm
            )

        self._task_queue.append(task_id)
        self._try_schedule_next()

        return task_id

    def _try_schedule_next(self) -> None:
        while len(self._active_tasks) < self.MAX_CONCURRENT_TASKS and self._task_queue:
            task_id = self._task_queue.pop(0)
            self._active_tasks.add(task_id)
            self._start_task(task_id)

    def _start_task(self, task_id: str) -> None:
        task = self._db.get_task(task_id)
        if task is None:
            if task_id in self._active_tasks:
                self._active_tasks.remove(task_id)
            return

        if task.state == TaskState.CANCELLED.value:
            if task_id in self._active_tasks:
                self._active_tasks.remove(task_id)
            self._try_schedule_next()
            return

        # 从传输暂停恢复:直接回到传输阶段(避免 FULL_PIPELINE 误入下载)
        if task.state == TaskState.PAUSED_TRANSFER.value:
            runnable = StageRunnable(self, task_id, self._execute_transfer_stage)
            self._transfer_pool.start(runnable)
            return

        task_type = TaskType(task.task_type)

        if task_type == TaskType.DOWNLOAD_ONLY:
            runnable = StageRunnable(self, task_id, self._execute_download_stage)
            self._download_pool.start(runnable)
        elif task_type == TaskType.TRANSFER_ONLY:
            runnable = StageRunnable(self, task_id, self._execute_transfer_stage)
            self._transfer_pool.start(runnable)
        elif task_type == TaskType.FULL_PIPELINE:
            runnable = StageRunnable(self, task_id, self._execute_download_stage)
            self._download_pool.start(runnable)

    def _create_downloader(self, model_source: str):
        """根据模型源创建下载器,自动应用代理设置(经统一策略构造)。"""
        strategies = create_strategies(load_proxy(self._db))
        try:
            return strategies[model_source]
        except KeyError:
            raise ValueError(f"不支持的模型源: {model_source}")

    # ---- 引擎公共件 ----

    def _stage_blocked(self, task_id: str, states: tuple) -> bool:
        """暂停/取消 guard:处于目标状态时,残留信号不得推进完成判定。"""
        task = self._db.get_task(task_id)
        return task is not None and task.state in states

    def _new_engine(self, task_id: str, blocked_states: tuple, on_result=None) -> StageEngine:
        engine = StageEngine(
            is_blocked=lambda: self._stage_blocked(task_id, blocked_states),
            on_conclude=lambda eng: self._on_stage_concluded(task_id, eng),
            on_result=on_result,
        )
        self._engines[task_id] = engine
        return engine

    def _wire(self, worker) -> None:
        """worker 信号统一接通用处理器。"""
        worker.signals.progress.connect(self._on_stage_progress)
        worker.signals.finished.connect(self._on_stage_file_finished)
        worker.signals.error.connect(self._on_stage_file_error)

    def _on_stage_progress(self, task_id: str, file_path: str, current: int, total: int):
        """各阶段共享的进度转发"""
        self.task_progress.emit(task_id, file_path, current, total)

    def _on_stage_file_finished(self, task_id: str, file_path: str, success: bool):
        """各阶段共享的单文件完成处理"""
        engine = self._engines.get(task_id)
        if engine is None:
            return
        worker = engine.get_worker(file_path)
        result = getattr(worker, "actual_hash", None)
        engine.finish(file_path, success, result=result)

    def _on_stage_file_error(self, task_id: str, file_path: str, error: str):
        """各阶段共享的单文件错误处理"""
        self.task_error.emit(task_id, file_path, error)

        engine = self._engines.get(task_id)
        if engine is None:
            return
        worker = engine.get_worker(file_path)
        result = getattr(worker, "actual_hash", None)
        engine.finish(file_path, False, result=result)

    def _on_stage_concluded(self, task_id: str, engine: StageEngine) -> None:
        """阶段收束:按当前状态路由下一阶段或终态(暂停/取消残留不推进)。"""
        task = self._db.get_task(task_id)
        if task is None or task.state in (
            TaskState.CANCELLED.value,
            TaskState.PAUSED_DOWNLOAD.value,
            TaskState.PAUSED_TRANSFER.value,
        ):
            return
        if engine.has_failures():
            self._fail_task(task_id)
            return

        task_type = TaskType(task.task_type)
        if task.state == TaskState.DOWNLOADING.value:
            if task_type == TaskType.FULL_PIPELINE:
                self._start_verify_stage(task_id)
            else:
                self._complete_task(task_id)
        elif task.state == TaskState.VERIFYING.value:
            if task_type == TaskType.FULL_PIPELINE:
                self._start_transfer_stage(task_id)
            else:
                self._complete_task(task_id)
        elif task.state == TaskState.TRANSFERRING.value:
            self._complete_task(task_id)

    # ---- 下载阶段 ----

    def _execute_download_stage(self, task_id: str) -> None:
        task = self._db.get_task(task_id)
        if task is None or task.state == TaskState.CANCELLED.value:
            return
        self._db.update_task_state(task_id, TaskState.DOWNLOADING.value)
        self.task_state_changed.emit(task_id, TaskState.DOWNLOADING.value)

        task = self._db.get_task(task_id)
        files = self._db.get_task_files(task_id)

        if not files:
            self._on_stage_concluded(task_id, self._new_engine(
                task_id, (TaskState.PAUSED_DOWNLOAD.value, TaskState.CANCELLED.value)))
            return

        engine = self._new_engine(
            task_id, (TaskState.PAUSED_DOWNLOAD.value, TaskState.CANCELLED.value))
        engine.begin(len(files))

        # 跳过已完成文件(本地存在、无 .tmp、大小一致)——恢复调度不再重下
        cache = Path(task.local_cache_dir)
        pending = []
        for file_dict in files:
            target = cache / file_dict["file_path"]
            tmp = cache / (file_dict["file_path"] + ".tmp")
            if (target.exists() and not tmp.exists()
                    and target.stat().st_size == file_dict["file_size"]):
                engine.mark_done(file_dict["file_path"])
            else:
                pending.append(file_dict)

        if engine.done():
            engine.maybe_conclude()
            return

        downloader = self._create_downloader(task.model_source)

        for file_dict in pending:
            file_info = FileInfo(
                path=file_dict['file_path'],
                size=file_dict['file_size'],
            )
            local_path = Path(task.local_cache_dir) / file_dict['file_path']

            worker = DownloadWorker(
                task_id=task_id,
                file_info=file_info,
                downloader=downloader,
                model_id=task.model_id,
                revision=task.revision,
                local_path=local_path,
            )
            self._wire(worker)
            engine.register(file_dict['file_path'], worker)
            self._download_pool.start(worker)

    # ---- 校验阶段 ----

    def _start_verify_stage(self, task_id: str) -> None:
        runnable = StageRunnable(self, task_id, self._execute_verify_stage)
        self._verify_pool.start(runnable)

    def _execute_verify_stage(self, task_id: str) -> None:
        """执行校验阶段——按源校验和做全文件哈希比对,结果落库(Q5B)。"""
        task = self._db.get_task(task_id)
        if task is None or task.state == TaskState.CANCELLED.value:
            return
        self._db.update_task_state(task_id, TaskState.VERIFYING.value)
        self.task_state_changed.emit(task_id, TaskState.VERIFYING.value)

        task = self._db.get_task(task_id)
        files = self._db.get_task_files(task_id)

        if not files:
            self._on_stage_concluded(
                task_id, self._new_engine(task_id, (TaskState.CANCELLED.value,)))
            return

        ids = {f["file_path"]: f.get("id") for f in files}

        def on_result(file_path: str, result, success: bool) -> None:
            """校验结果写回(Q5B):DB 写只发生在 TaskManager 一处。"""
            file_id = ids.get(file_path)
            if file_id is None:
                return
            self._db.update_file_state(
                file_id=file_id,
                verify_state=(
                    StageState.COMPLETED.value if success else StageState.FAILED.value
                ),
                actual_hash=result,
            )

        engine = self._new_engine(
            task_id, (TaskState.CANCELLED.value,), on_result=on_result)
        engine.begin(len(files))

        for file_dict in files:
            local_path = Path(task.local_cache_dir) / file_dict['file_path']

            if not file_dict.get('expected_hash') or not file_dict.get('hash_algorithm'):
                # 无源校验和:显式标记「未校验」,不静默当作通过
                engine.mark_done(file_dict['file_path'])
                file_id = ids.get(file_dict['file_path'])
                if file_id is not None:
                    self._db.update_file_state(
                        file_id=file_id,
                        verify_state=StageState.SKIPPED.value,
                    )
                continue

            worker = VerifyWorker(
                task_id=task_id,
                file_path=file_dict['file_path'],
                local_path=local_path,
                expected_hash=file_dict['expected_hash'],
                hash_algorithm=file_dict.get('hash_algorithm') or 'sha256',
            )
            self._wire(worker)
            engine.register(file_dict['file_path'], worker)
            self._verify_pool.start(worker)

        if engine.done():
            engine.maybe_conclude()

    # ---- 传输阶段 ----

    def pause_task(self, task_id: str) -> None:
        """暂停任务(仅下载/传输阶段)。运行中的文件 worker 被取消跟踪;排队 worker 不再启动。"""
        task = self._db.get_task(task_id)
        if task is None:
            return
        state = task.state
        if state == TaskState.DOWNLOADING.value:
            self._set_paused(task_id, TaskState.PAUSED_DOWNLOAD)
        elif state == TaskState.TRANSFERRING.value:
            self._set_paused(task_id, TaskState.PAUSED_TRANSFER)
        else:
            self.task_warning.emit(task_id, "lifecycle", "当前阶段不可暂停(等待/校验/已完成/失败)")

    def resume_task(self, task_id: str) -> None:
        """恢复暂停的任务。丢弃未完成文件的 .tmp 重新全量调度,保证无并发写。"""
        task = self._db.get_task(task_id)
        if task is None:
            return
        state = task.state
        if state in (TaskState.PAUSED_DOWNLOAD.value, TaskState.PAUSED_TRANSFER.value):
            # 等待被暂停的旧 worker 真正结束(它们仍在写 .tmp),避免并发写同一文件
            self._wait_retired(task_id)
            # 放回队列由调度器启动:保证并发名额上限(MAX_CONCURRENT_TASKS)不被突破
            self._discard_tmp_files(task_id)
            if task_id not in self._task_queue and task_id not in self._active_tasks:
                self._task_queue.append(task_id)
            self._try_schedule_next()
        else:
            self.task_warning.emit(task_id, "lifecycle", "任务当前不在可恢复状态")

    def cancel_task(self, task_id: str) -> None:
        """取消任务:置 CANCELLED,活跃 worker 收到 cancel,已下载部分保留。"""
        task = self._db.get_task(task_id)
        if task is None:
            return
        state = task.state
        if state in (
            TaskState.PENDING.value,
            TaskState.DOWNLOADING.value,
            TaskState.PAUSED_DOWNLOAD.value,
            TaskState.VERIFYING.value,
            TaskState.TRANSFERRING.value,
            TaskState.PAUSED_TRANSFER.value,
        ):
            self._cancel_workers(task_id)
            self._db.update_task_state(task_id, TaskState.CANCELLED.value)
            self.task_state_changed.emit(task_id, TaskState.CANCELLED.value)
            self._engines.pop(task_id, None)
            if task_id in self._task_queue:
                self._task_queue.remove(task_id)
            self._active_tasks.discard(task_id)
            self._try_schedule_next()
        else:
            self.task_warning.emit(task_id, "lifecycle", "任务已完成或已结束,无法取消")

    def _set_paused(self, task_id: str, paused_state: TaskState) -> None:
        self._db.update_task_state(task_id, paused_state.value)
        self.task_state_changed.emit(task_id, paused_state.value)
        self._cancel_workers(task_id)
        self._active_tasks.discard(task_id)
        self._try_schedule_next()

    def _cancel_workers(self, task_id: str) -> None:
        """暂停/取消:引擎退役所有活跃 worker 并置 cancel flag。"""
        engine = self._engines.get(task_id)
        if engine is None:
            return
        for worker in engine.retire():
            worker.cancel()

    def _wait_retired(self, task_id: str) -> None:
        """等待该任务被暂停/取消的 worker 真正结束(其下载仍在写同一 .tmp)。"""
        engine = self._engines.get(task_id)
        if engine is not None:
            engine.wait_retired()

    def _discard_tmp_files(self, task_id: str) -> None:
        """删除任务未完成文件的 .tmp,恢复时全量重下,避免与旧 worker 并发写同一文件。"""
        task = self._db.get_task(task_id)
        if task is None:
            return
        try:
            cache = Path(task.local_cache_dir)
        except (TypeError, ValueError):
            return
        for file_dict in self._db.get_task_files(task_id):
            tmp = cache / (file_dict["file_path"] + ".tmp")
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def _build_transfer(self, task, profile=None) -> RsyncTransfer:
        """按任务引用的 Server profile 构造传输器。

        remote_host 为 profile name(自然键);空或查不到时回退默认
        主机/用户,兼容未配置服务器与旧任务。profile 可由调用方预解析
        并传入,避免 stage 内重复查询产生不一致快照。
        """
        server_name = task.remote_host or ""
        if profile is None and server_name:
            profile = find_profile(self._db, server_name)
        if profile is not None:
            return profile.to_transfer()
        return RsyncTransfer(host="localhost", username="user")

    def _start_transfer_stage(self, task_id: str) -> None:
        runnable = StageRunnable(self, task_id, self._execute_transfer_stage)
        self._transfer_pool.start(runnable)

    def _execute_transfer_stage(self, task_id: str) -> None:
        """执行传输阶段"""
        task = self._db.get_task(task_id)
        if task is None or task.state == TaskState.CANCELLED.value:
            return
        self._db.update_task_state(task_id, TaskState.TRANSFERRING.value)
        self.task_state_changed.emit(task_id, TaskState.TRANSFERRING.value)

        task = self._db.get_task(task_id)
        files = self._db.get_task_files(task_id)

        if not files:
            self._on_stage_concluded(task_id, self._new_engine(
                task_id, (TaskState.PAUSED_TRANSFER.value, TaskState.CANCELLED.value)))
            return

        engine = self._new_engine(
            task_id, (TaskState.PAUSED_TRANSFER.value, TaskState.CANCELLED.value))
        engine.begin(len(files))

        # 创建传输器:按任务引用的 Server profile 解析真实连接参数
        server_name = task.remote_host or ""
        profile = find_profile(self._db, server_name) if server_name else None
        transfer = self._build_transfer(task, profile=profile)
        if server_name and profile is None:
            self.task_warning.emit(
                task_id,
                "server",
                f"未找到服务器配置 {server_name!r},使用默认传输设置",
            )

        for file_dict in files:
            local_path = Path(task.local_cache_dir) / file_dict['file_path']
            remote_path = f"{task.remote_path or ''}/{file_dict['file_path']}"

            worker = TransferWorker(
                task_id=task_id,
                file_path=file_dict['file_path'],
                transfer=transfer,
                local_path=local_path,
                remote_path=remote_path,
                expected_hash=file_dict.get('expected_hash'),
                hash_algorithm=file_dict.get('hash_algorithm') or 'sha256',
            )
            self._wire(worker)
            engine.register(file_dict['file_path'], worker)
            self._transfer_pool.start(worker)

    # ---- 终态 ----

    def _fail_task(self, task_id: str):
        """任务失败:更新状态、广播、清理残留、释放并发名额(不进入后续阶段)。"""
        task = self._db.get_task(task_id)
        if task is None or task.state == TaskState.CANCELLED.value:
            return
        self._db.update_task_state(task_id, TaskState.FAILED.value)
        self.task_state_changed.emit(task_id, TaskState.FAILED.value)
        self.task_failed.emit(task_id)

        self._engines.pop(task_id, None)

        if task_id in self._active_tasks:
            self._active_tasks.remove(task_id)
        self._try_schedule_next()

    def _complete_task(self, task_id: str):
        """完成任务(CANCELLED 终态不被覆盖)"""
        task = self._db.get_task(task_id)
        if task is None or task.state == TaskState.CANCELLED.value:
            return
        self._db.update_task_state(task_id, TaskState.COMPLETED.value)
        self.task_state_changed.emit(task_id, TaskState.COMPLETED.value)
        self.task_completed.emit(task_id)

        self._engines.pop(task_id, None)

        if task_id in self._active_tasks:
            self._active_tasks.remove(task_id)
        self._try_schedule_next()
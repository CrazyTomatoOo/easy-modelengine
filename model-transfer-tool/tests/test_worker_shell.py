"""WorkerBase 壳契约测试——取消、单终态发射、异常兜底。

信号经真实连接收集(Qt 直连,同线程即时);策略用可编程探针,不触真实下载。
"""

from core.workers import WorkerBase


class _Probe(WorkerBase):
    def __init__(self, behavior, task_id="t1", file_path="a.bin"):
        super().__init__(task_id, file_path)
        self._behavior = behavior
        self._terminated = []  # ("finished"|"error", payload)

    def _run_impl(self):
        self._behavior(self)

    def emit_finished(self, success):
        super().emit_finished(success)
        self._terminated.append(("finished", success))

    def emit_error(self, message):
        super().emit_error(message)
        self._terminated.append(("error", message))


def _collect(worker):
    """挂接信号收集器,返回 (finished_list, error_list)。"""
    finished, errors = [], []

    def on_finished(tid, path, ok):
        finished.append((tid, path, ok))

    def on_error(tid, path, msg):
        errors.append((tid, path, msg))

    worker.signals.finished.connect(on_finished)
    worker.signals.error.connect(on_error)
    return finished, errors


class TestWorkerShell:
    def test_cancelled_run_emits_nothing(self):
        ran = []

        def behavior(self):
            ran.append(True)

        w = _Probe(behavior)
        w.cancel()
        w.run()
        assert ran == [], "取消后不得执行策略"
        assert w._terminated == []

    def test_shell_emits_error_when_impl_raises(self):
        def behavior(self):
            raise ValueError("boom")

        w = _Probe(behavior)
        _finished, errors = _collect(w)
        w.run()
        assert (_finished, errors) == ([], [("t1", "a.bin", "boom")])

    def test_shell_never_double_emits(self):
        """策略已发射终态后异常:壳不补发。"""

        def behavior(self):
            self.emit_error("策略失败")
            raise ValueError("boom")

        w = _Probe(behavior)
        _finished, errors = _collect(w)
        w.run()
        assert w._terminated == [("error", "策略失败")]
        assert errors == [("t1", "a.bin", "策略失败")]

    def test_finished_signal_flow(self):
        def behavior(self):
            self.emit_finished(True)

        w = _Probe(behavior)
        finished, errors = _collect(w)
        w.run()
        assert finished == [("t1", "a.bin", True)]
        assert errors == []

    def test_done_event_always_set(self):
        """run 兜底:即使策略抛异常,done_event 也置位(退役等待不挂死)。"""

        def behavior(self):
            raise RuntimeError("die")

        w = _Probe(behavior)
        w.run()
        assert w.done_event.is_set()
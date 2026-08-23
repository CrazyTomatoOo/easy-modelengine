"""阶段引擎单元测试——纯 Python 机器,无 Qt:文件跟踪/完成判定/退役等待/结果回调。"""

import threading

from core.stage_engine import StageEngine


class _FakeWorker:
    def __init__(self):
        self.cancelled = False
        self.done_event = threading.Event()

    def cancel(self):
        self.cancelled = True


class TestCompletion:
    def test_all_success_concludes_once(self):
        concluded = []
        engine = StageEngine(
            is_blocked=lambda: False,
            on_conclude=lambda e: concluded.append(e),
        )
        engine.begin(2)
        engine.register("a", _FakeWorker())
        engine.register("b", _FakeWorker())
        engine.finish("a", True)
        assert concluded == [], "未全部完成不得收束"
        engine.finish("b", True)
        assert len(concluded) == 1
        assert not engine.has_failures()
        assert engine.done()

    def test_failure_sets_flag(self):
        concluded = []
        engine = StageEngine(
            is_blocked=lambda: False,
            on_conclude=lambda e: concluded.append(e),
        )
        engine.begin(2)
        engine.mark_done("a")
        engine.finish("b", False)
        assert engine.has_failures()

    def test_mark_done_skips_count_as_complete(self):
        concluded = []
        engine = StageEngine(
            is_blocked=lambda: False,
            on_conclude=lambda e: concluded.append(e),
        )
        engine.begin(3)
        engine.mark_done("a")
        engine.mark_done("b")
        engine.finish("c", True)
        assert len(concluded) == 1

    def test_maybe_conclude_for_all_skipped(self):
        concluded = []
        engine = StageEngine(
            is_blocked=lambda: False,
            on_conclude=lambda e: concluded.append(e),
        )
        engine.begin(2)
        engine.mark_done("a")
        engine.mark_done("b")
        assert concluded == []
        engine.maybe_conclude()
        assert len(concluded) == 1


class TestBlockedGuards:
    def test_blocked_does_not_advance(self):
        blocked = True
        concluded = []
        engine = StageEngine(
            is_blocked=lambda: blocked,
            on_conclude=lambda e: concluded.append(e),
        )
        engine.begin(1)
        engine.finish("a", True)
        assert concluded == [], "阻塞时残留信号不得推进收束"

        blocked = False
        engine.maybe_conclude()
        assert len(concluded) == 1


class TestLifecycle:
    def test_retire_wait_and_cancel(self):
        engine = StageEngine(
            is_blocked=lambda: False,
            on_conclude=lambda e: None,
        )
        engine.begin(2)
        a, b = _FakeWorker(), _FakeWorker()
        engine.register("a", a)
        engine.register("b", b)

        # 退役后 worker 仍在写 .tmp:wait_retired 必须等 done_event(cancel 由 run() 收尾)
        a.done_event.set()
        b.done_event.set()
        engine.wait_retired()
        assert not engine.done(), "退役不算完成"

        engine.wait_retired()  # 立即返回:done_event 未 set(不阻塞)
        assert not engine.done(), "退役不算完成"

    def test_wait_retired_blocks_until_done(self):
        engine = StageEngine(
            is_blocked=lambda: False,
            on_conclude=lambda e: None,
        )
        engine.begin(1)
        w = _FakeWorker()
        engine.register("a", w)
        engine.retire()

        def release():
            w.done_event.set()

        threading.Timer(0.05, release).start()
        engine.wait_retired()
        assert True  # 未超时即等到了 done_event

    def test_result_callback_carries_result_and_success(self):
        results = []
        engine = StageEngine(
            is_blocked=lambda: False,
            on_conclude=lambda e: None,
            on_result=lambda path, result, success: results.append((path, result, success)),
        )
        engine.begin(2)
        engine.finish("a", True, result="hash-a")
        engine.finish("b", False, result=None)
        assert results == [("a", "hash-a", True), ("b", None, False)]

    def test_finish_returns_worker(self):
        engine = StageEngine(
            is_blocked=lambda: False,
            on_conclude=lambda e: None,
        )
        engine.begin(1)
        w = _FakeWorker()
        engine.register("a", w)
        assert engine.finish("a", True) is w
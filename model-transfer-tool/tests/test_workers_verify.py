"""TransferWorker 远程校验测试——传输成功后必须对远端副本做哈希比对。"""

import hashlib
import threading
from pathlib import Path

import pytest
from PyQt6.QtCore import QCoreApplication

from core.interfaces import TransferStrategy
from core.workers import TransferWorker, VerifyWorker


@pytest.fixture(scope="module")
def qt_app():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


class _FakeTransfer(TransferStrategy):
    def __init__(self, transfer_ok=True, remote_ok=True):
        self.transfer_ok = transfer_ok
        self.remote_ok = remote_ok
        self.transfer_calls = []
        self.verify_calls = []

    def transfer_file(self, local_path, remote_path, progress_callback=None):
        self.transfer_calls.append((str(local_path), remote_path))
        return self.transfer_ok

    def verify_remote_checksum(self, remote_path, expected_hash, algorithm):
        self.verify_calls.append((remote_path, expected_hash, algorithm))
        return self.remote_ok

    def check_connectivity(self):
        return True, ""


class _Harness:
    """同步驱动 QRunnable 并收集终态信号。"""

    def __init__(self):
        self.finished = []
        self.errors = []
        self.done = threading.Event()

    def on_finished(self, task_id, file_path, ok):
        self.finished.append((task_id, file_path, ok))
        self.done.set()

    def on_error(self, task_id, file_path, error):
        self.errors.append((task_id, file_path, error))
        self.done.set()


def _run(worker, harness, timeout=5):
    worker.signals.finished.connect(harness.on_finished)
    worker.signals.error.connect(harness.on_error)
    worker.run()
    assert harness.done.wait(timeout)


class TestRemoteVerify:
    def test_passes_source_hash_to_remote(self, tmp_path):
        local = tmp_path / "a.bin"
        local.write_bytes(b"data")
        transfer = _FakeTransfer()

        worker = TransferWorker(
            task_id="t1",
            file_path="a.bin",
            transfer=transfer,
            local_path=local,
            remote_path="/remote/a.bin",
            expected_hash="E" * 64,
            hash_algorithm="sha256",
        )
        h = _Harness()
        _run(worker, h)

        assert transfer.verify_calls == [("/remote/a.bin", "E" * 64, "sha256")]
        assert h.finished == [("t1", "a.bin", True)]
        assert not h.errors

    def test_local_source_uses_local_actual_hash(self, tmp_path):
        """本地源无源校验和:期望值取传输时本地实时哈希(副本与源一致)。"""
        local = tmp_path / "a.bin"
        local.write_bytes(b"payload")
        digest = hashlib.sha256(b"payload").hexdigest()
        transfer = _FakeTransfer()

        worker = TransferWorker(
            task_id="t1",
            file_path="a.bin",
            transfer=transfer,
            local_path=local,
            remote_path="/remote/a.bin",
        )
        h = _Harness()
        _run(worker, h)

        assert transfer.verify_calls[0][1] == digest
        assert transfer.verify_calls[0][2] == "sha256"
        assert h.finished == [("t1", "a.bin", True)]

    def test_remote_mismatch_fails_task(self, tmp_path):
        local = tmp_path / "a.bin"
        local.write_bytes(b"data")
        transfer = _FakeTransfer(remote_ok=False)

        worker = TransferWorker(
            task_id="t1",
            file_path="a.bin",
            transfer=transfer,
            local_path=local,
            remote_path="/remote/a.bin",
            expected_hash="H",
        )
        h = _Harness()
        _run(worker, h)

        assert not h.finished
        assert h.errors and "远程校验失败" in h.errors[0][2]
        assert transfer.verify_calls, "传输成功后必须执行远程校验"

    def test_transfer_failure_skips_verify(self, tmp_path):
        local = tmp_path / "a.bin"
        local.write_bytes(b"data")
        transfer = _FakeTransfer(transfer_ok=False)

        worker = TransferWorker(
            task_id="t1",
            file_path="a.bin",
            transfer=transfer,
            local_path=local,
            remote_path="/remote/a.bin",
            expected_hash="H",
        )
        h = _Harness()
        _run(worker, h)

        assert transfer.verify_calls == []
        assert h.errors and "传输失败" in h.errors[0][2]

class TestVerifyWorker:
    """校验 worker:只算不写(Q5B),失配删除损坏文件。"""

    def _run(self, worker, harness):
        worker.signals.finished.connect(harness.on_finished)
        worker.signals.error.connect(harness.on_error)
        worker.run()
        assert harness.done.wait(5)

    def test_match_emits_finished_with_hash(self, tmp_path):
        import hashlib

        local = tmp_path / "a.bin"
        data = b"good-data"
        local.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        worker = VerifyWorker("t1", "a.bin", local, digest)
        h = _Harness()
        self._run(worker, h)

        assert h.finished == [("t1", "a.bin", True)]
        assert worker.actual_hash == digest

    def test_mismatch_deletes_corrupt_file(self, tmp_path):
        local = tmp_path / "a.bin"
        local.write_bytes(b"corrupted")
        worker = VerifyWorker("t1", "a.bin", local, "x" * 64)
        h = _Harness()
        self._run(worker, h)

        assert not h.finished
        assert h.errors and "校验失败" in h.errors[0][2]
        assert not local.exists(), "哈希不匹配必须删除损坏文件"

    def test_missing_file_errors(self, tmp_path):
        worker = VerifyWorker("t1", "missing.bin", tmp_path / "missing.bin", "x" * 64)
        h = _Harness()
        self._run(worker, h)

        assert not h.finished
        assert h.errors and "文件不存在" in h.errors[0][2]

    def test_cancel_emits_nothing(self, tmp_path):
        local = tmp_path / "a.bin"
        local.write_bytes(b"data")
        worker = VerifyWorker("t1", "a.bin", local, "x" * 64)
        worker.cancel()
        h = _Harness()
        worker.run()

        assert not h.finished
        assert not h.errors

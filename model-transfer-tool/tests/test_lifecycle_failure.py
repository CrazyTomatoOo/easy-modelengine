"""TaskManager 失败语义测试——spec 定义的 seam:下载/传输/校验失败 → FAILED。"""

import tempfile
import os
from pathlib import Path

import pytest

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication

from core.database import Database
from core.task_config import TaskConfig, TaskType, TaskFile
from core.task_manager import TaskManager
from core.interfaces import FileInfo


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    db.init_schema()
    yield db
    db.close()
    os.unlink(db_path)


_QT_APP = None


@pytest.fixture
def manager(temp_db):
    global _QT_APP
    if QCoreApplication.instance() is None:
        _QT_APP = QApplication([])  # QApplication:pytest-qt 的 qtbot 要求;持有引用防 GC
    m = TaskManager(temp_db)

    class FailingDownloader:
        def download_file(self, model_id, revision, file_info, local_path, progress_callback=None):
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text("part")
            return False

    class SucceedingDownloader:
        def download_file(self, model_id, revision, file_info, local_path, progress_callback=None):
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text("ok")
            progress_callback(file_info.size, file_info.size)
            return True

    m._create_downloader = lambda source: FailingDownloader()
    m._succeeding = SucceedingDownloader()

    original_start = m._start_task

    def noop_start(task_id):
        pass  # 测试显式驱动目标 stage,避免 create_task 自动执行造成双 worker

    m._start_task = noop_start
    yield m

    m._task_file_total.clear()
    m._task_file_completed.clear()
    m._task_file_failed.clear()
    m._active_download_workers.clear()
    m._active_transfer_workers.clear()
    m._download_pool.waitForDone(5000)
    m._verify_pool.waitForDone(5000)
    m._transfer_pool.waitForDone(5000)
    if QCoreApplication.instance():
        QCoreApplication.processEvents()
    m._start_task = original_start


def _config(task_type=TaskType.DOWNLOAD_ONLY, files=None, cache=None):
    return TaskConfig(
        task_type=task_type,
        model_source="huggingface",
        model_id="org/m",
        files=files or [TaskFile(file_path="a.bin", file_size=8)],
        local_cache_dir=Path(cache or tempfile.mkdtemp()),
    )


def _settle(manager):
    import traceback
    import time

    manager._download_pool.waitForDone(5000)
    manager._verify_pool.waitForDone(5000)
    manager._transfer_pool.waitForDone(5000)
    app = QCoreApplication.instance()
    if app:
        for _ in range(20):
            app.processEvents()
            time.sleep(0.02)


class TestFailurePropagation:
    def test_download_failure_marks_failed(self, manager):
        task_id = manager.create_task(_config())
        manager._execute_download_stage(task_id)
        _settle(manager)

        assert manager._db.get_task(task_id).state == "failed"

    def test_failed_task_releases_slot(self, manager):
        first = manager.create_task(_config())
        second = manager.create_task(_config())
        manager._execute_download_stage(first)
        _settle(manager)

        assert manager._db.get_task(first).state == "failed"
        assert first not in manager._active_tasks
        # 失败任务释放名额后,后续任务可被调度
        manager._execute_download_stage(second)
        _settle(manager)
        assert second not in manager._active_tasks

    def test_success_still_completes(self, manager):
        manager._create_downloader = lambda source: manager._succeeding
        task_id = manager.create_task(_config())
        manager._execute_download_stage(task_id)
        _settle(manager)
        assert manager._db.get_task(task_id).state == "completed"

    def test_failed_signal_emitted(self, manager):
        from PyQt6.QtTest import QSignalSpy

        task_id = manager.create_task(_config())
        spy = QSignalSpy(manager.task_failed)
        manager._execute_download_stage(task_id)
        _settle(manager)
        assert len(spy) == 1
        assert spy[0][0] == task_id

    def test_download_failure_skips_pipeline_continue(self, manager):
        """FULL_PIPELINE 下载失败:不得进入 verify/transfer 阶段"""
        task_id = manager.create_task(_config(task_type=TaskType.FULL_PIPELINE))
        state_log = []

        def watch_state(tid, state):
            state_log.append(state)

        manager.task_state_changed.connect(watch_state)
        manager._execute_download_stage(task_id)
        _settle(manager)

        assert manager._db.get_task(task_id).state == "failed"
        assert "verifying" not in state_log
        assert "transferring" not in state_log

    def test_verify_failure_marks_failed(self, manager, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "a.bin").write_bytes(b"corrupted")
        task_id = manager.create_task(_config(
            task_type=TaskType.FULL_PIPELINE,
            files=[TaskFile(file_path="a.bin", file_size=8, expected_hash="x" * 64, hash_algorithm="sha256")],
            cache=cache,
        ))
        manager._execute_verify_stage(task_id)
        _settle(manager)
        assert manager._db.get_task(task_id).state == "failed"

    def test_verify_success_continues_to_transfer(self, manager, tmp_path):
        import hashlib

        cache = tmp_path / "cache"
        cache.mkdir()
        data = b"good-data"
        (cache / "a.bin").write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        class OkTransfer:
            def transfer_file(self, local_path, remote_path, progress_callback=None):
                return True

        manager._build_transfer = lambda task, profile=None: OkTransfer()

        task_id = manager.create_task(_config(
            task_type=TaskType.FULL_PIPELINE,
            files=[TaskFile(file_path="a.bin", file_size=len(data), expected_hash=digest, hash_algorithm="sha256")],
            cache=cache,
        ))
        manager._execute_verify_stage(task_id)
        _settle(manager)

        task = manager._db.get_task(task_id)
        # 真实校验通过后进入 transfer(无文件阶段空转例外)或完成;绝不 FAILED
        assert task.state != "failed"
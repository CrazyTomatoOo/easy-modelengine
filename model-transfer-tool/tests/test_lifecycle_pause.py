"""TaskManager 暂停/恢复/取消测试——spec 定义的 seam:生命周期 API 行为。"""

import tempfile
import os
import time
from pathlib import Path

import threading
import pytest

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication

from core.database import Database
from core.task_config import TaskConfig, TaskType, TaskFile, TaskState
from core.task_manager import TaskManager

_QT_APP = None


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    db.init_schema()
    yield db
    db.close()
    os.unlink(db_path)


@pytest.fixture
def manager(temp_db):
    global _QT_APP
    if QCoreApplication.instance() is None:
        _QT_APP = QApplication([])

    m = TaskManager(temp_db)
    gate = threading.Event()

    class GatedDownloader:
        """下载前等待门控:测试在断言暂停前确保 worker 未完成,消除与完成信号的竞态。"""

        def download_file(self, model_id, revision, file_info, local_path, progress_callback=None):
            gate.wait(5)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(b"data")
            if progress_callback:
                progress_callback(file_info.size, file_info.size)
            return True

    m._create_downloader = lambda source: GatedDownloader()
    m._gate = gate

    original_start = m._start_task

    def sync_start(task_id):
        m._execute_download_stage(task_id)

    m._start_task = sync_start
    yield m

    m._engines.clear()
    gate.set()  # 先放行残留 worker,再等待,避免超时
    m._download_pool.waitForDone(5000)
    m._transfer_pool.waitForDone(5000)
    m._verify_pool.waitForDone(5000)
    if QCoreApplication.instance():
        for _ in range(10):
            QCoreApplication.processEvents()
            time.sleep(0.02)
    m._start_task = original_start


def _config(cache):
    return TaskConfig(
        task_type=TaskType.DOWNLOAD_ONLY,
        model_source="huggingface",
        model_id="org/m",
        files=[TaskFile(file_path="a.bin", file_size=8)],
        local_cache_dir=Path(cache),
    )


def _settle(manager):
    manager._gate.set()
    manager._download_pool.waitForDone(5000)
    manager._verify_pool.waitForDone(5000)
    manager._transfer_pool.waitForDone(5000)
    app = QCoreApplication.instance()
    if app:
        for _ in range(20):
            app.processEvents()
            time.sleep(0.02)


class TestPause:
    def test_pause_sets_paused_state(self, manager, tmp_path):
        task_id = manager.create_task(_config(str(tmp_path)))
        manager.pause_task(task_id)
        assert manager._db.get_task(task_id).state == TaskState.PAUSED_DOWNLOAD.value

    def test_pause_releases_slot(self, manager, tmp_path):
        task_id = manager.create_task(_config(str(tmp_path)))
        manager.pause_task(task_id)
        assert task_id not in manager._active_tasks

    def test_pause_emits_state(self, manager, tmp_path):
        task_id = manager.create_task(_config(str(tmp_path)))
        spy = QSignalSpy(manager.task_state_changed)
        manager.pause_task(task_id)
        assert any(args[1] == "paused_dl" for args in spy)

    def test_pause_ignored_in_verify_with_warning(self, manager, tmp_path):
        task_id = manager.create_task(_config(str(tmp_path)))
        # 模拟 verify 阶段
        manager._db.update_task_state(task_id, TaskState.VERIFYING.value)
        spy = QSignalSpy(manager.task_warning)
        manager.pause_task(task_id)
        assert manager._db.get_task(task_id).state == TaskState.VERIFYING.value
        assert len(spy) == 1

    def test_pause_completed_task_warns(self, manager, tmp_path):
        task_id = manager.create_task(_config(str(tmp_path)))
        manager._db.update_task_state(task_id, TaskState.COMPLETED.value)
        spy = QSignalSpy(manager.task_warning)
        manager.pause_task(task_id)
        assert len(spy) == 1


class TestResume:
    def test_resume_completes_task(self, manager, tmp_path):
        task_id = manager.create_task(_config(str(tmp_path)))
        manager.pause_task(task_id)
        manager.resume_task(task_id)
        _settle(manager)
        assert manager._db.get_task(task_id).state == TaskState.COMPLETED.value

    def test_resume_not_paused_warns(self, manager, tmp_path):
        task_id = manager.create_task(_config(str(tmp_path)))
        manager._db.update_task_state(task_id, TaskState.COMPLETED.value)
        spy = QSignalSpy(manager.task_warning)
        manager.resume_task(task_id)
        assert len(spy) == 1

    def test_resume_discards_tmp_files(self, manager, tmp_path):
        cache = tmp_path / "cache"
        cache.mkdir()
        task_id = manager.create_task(_config(str(cache)))
        # 模拟中断残留的断点文件
        (cache / "a.bin.tmp").write_bytes(b"partial")
        manager.pause_task(task_id)
        manager.resume_task(task_id)
        _settle(manager)
        assert (cache / "a.bin.tmp").exists() is False
        assert (cache / "a.bin").exists() is True


class TestCancel:
    def test_cancel_sets_state(self, manager, tmp_path):
        task_id = manager.create_task(_config(str(tmp_path)))
        manager.cancel_task(task_id)
        assert manager._db.get_task(task_id).state == TaskState.CANCELLED.value
        assert task_id not in manager._active_tasks

    def test_cancel_completed_task_warns(self, manager, tmp_path):
        task_id = manager.create_task(_config(str(tmp_path)))
        manager._db.update_task_state(task_id, TaskState.COMPLETED.value)
        spy = QSignalSpy(manager.task_warning)
        manager.cancel_task(task_id)
        assert len(spy) == 1
        assert manager._db.get_task(task_id).state == TaskState.COMPLETED.value

    def test_cancelled_download_does_not_progress_to_verify(self, manager, tmp_path):
        """FULL_PIPELINE 下载阶段后被取消:不得进入 verify/complete"""
        config = TaskConfig(
            task_type=TaskType.FULL_PIPELINE,
            model_source="huggingface",
            model_id="org/m",
            files=[TaskFile(file_path="a.bin", file_size=8)],
            local_cache_dir=Path(str(tmp_path)),
        )
        task_id = manager.create_task(config)
        manager.cancel_task(task_id)
        _settle(manager)
        assert manager._db.get_task(task_id).state == TaskState.CANCELLED.value
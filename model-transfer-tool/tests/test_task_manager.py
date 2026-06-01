import pytest
import tempfile
import os
from pathlib import Path

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtTest import QSignalSpy

from core.database import Database
from core.task_config import TaskConfig, TaskType, TaskState, TaskFile, StageState
from core.task_manager import TaskManager


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
def task_manager(temp_db):
    manager = TaskManager(temp_db)
    
    # Mock downloader to prevent actual network operations
    original_create_downloader = manager._create_downloader
    def mock_create_downloader(model_source):
        class MockDownloader:
            def download_file(self, model_id, revision, file_info, local_path, progress_callback):
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_text("mock")
                progress_callback(file_info.size, file_info.size)
                return True
        return MockDownloader()
    manager._create_downloader = mock_create_downloader
    
    # Override _start_task to run synchronously for testing
    original_start_task = manager._start_task
    
    def sync_start_task(task_id):
        task = manager._db.get_task(task_id)
        if task is None:
            if task_id in manager._active_tasks:
                manager._active_tasks.remove(task_id)
            return
        
        task_type = TaskType(task.task_type)
        
        if task_type == TaskType.DOWNLOAD_ONLY:
            manager._execute_download_stage(task_id)
        elif task_type == TaskType.TRANSFER_ONLY:
            manager._execute_transfer_stage(task_id)
        elif task_type == TaskType.FULL_PIPELINE:
            manager._execute_download_stage(task_id)
    
    manager._start_task = sync_start_task
    
    yield manager
    
    # Wait for all thread pools to finish
    manager._download_pool.waitForDone(5000)
    manager._verify_pool.waitForDone(5000)
    manager._transfer_pool.waitForDone(5000)
    
    # Process any pending Qt events/signals
    if QCoreApplication.instance():
        QCoreApplication.processEvents()
    
    # Restore original
    manager._start_task = original_start_task
    manager._create_downloader = original_create_downloader


class TestTaskCreation:
    def test_create_task_returns_id(self, task_manager):
        config = TaskConfig(
            task_type=TaskType.DOWNLOAD_ONLY,
            model_source="huggingface",
            model_id="bert-base-uncased"
        )
        task_id = task_manager.create_task(config)
        
        assert task_id is not None
        assert isinstance(task_id, str)
        assert len(task_id) > 0
    
    def test_create_task_saves_to_database(self, task_manager):
        config = TaskConfig(
            task_type=TaskType.DOWNLOAD_ONLY,
            model_source="huggingface",
            model_id="bert-base-uncased",
            revision="v1.0",
            local_cache_dir=Path("/tmp/cache")
        )
        task_id = task_manager.create_task(config)
        
        task = task_manager._db.get_task(task_id)
        assert task is not None
        assert task.task_type == "download_only"
        assert task.model_source == "huggingface"
        assert task.model_id == "bert-base-uncased"
        assert task.revision == "v1.0"
        assert task.local_cache_dir == "/tmp/cache"
    
    def test_create_task_with_files(self, task_manager):
        config = TaskConfig(
            task_type=TaskType.DOWNLOAD_ONLY,
            model_source="huggingface",
            model_id="bert-base-uncased",
            files=[
                TaskFile(file_path="model.bin", file_size=1024),
                TaskFile(file_path="config.json", file_size=256)
            ]
        )
        task_id = task_manager.create_task(config)
        
        files = task_manager._db.get_task_files(task_id)
        assert len(files) == 2
        assert files[0]['file_path'] in ["model.bin", "config.json"]
        assert files[1]['file_path'] in ["model.bin", "config.json"]
    
    def test_create_task_with_optional_fields(self, task_manager):
        config = TaskConfig(
            task_type=TaskType.FULL_PIPELINE,
            model_source="modelscope",
            model_id="llama-7b",
            revision="main",
            local_cache_dir=Path("cache"),
            file_filter="*.bin",
            remote_host="192.168.1.1",
            remote_path="/models"
        )
        task_id = task_manager.create_task(config)
        
        task = task_manager._db.get_task(task_id)
        assert task is not None
        assert task.remote_host == "192.168.1.1"
        assert task.remote_path == "/models"


class TestTaskExecution:
    def test_execute_download_stage_updates_state(self, task_manager):
        config = TaskConfig(
            task_type=TaskType.DOWNLOAD_ONLY,
            model_source="huggingface",
            model_id="bert-base-uncased"
        )
        task_id = task_manager.create_task(config)
        
        task_manager._execute_download_stage(task_id)
        
        task = task_manager._db.get_task(task_id)
        assert task.state == "completed"
    
    def test_execute_download_stage_with_files(self, task_manager, qtbot):
        config = TaskConfig(
            task_type=TaskType.DOWNLOAD_ONLY,
            model_source="huggingface",
            model_id="bert-base-uncased",
            files=[
                TaskFile(file_path="model.bin", file_size=1024),
                TaskFile(file_path="config.json", file_size=256)
            ]
        )
        task_id = task_manager.create_task(config)
        
        spy = QSignalSpy(task_manager.task_progress)
        task_manager._execute_download_stage(task_id)
        
        qtbot.wait(500)
        assert len(spy) >= 2
    
    def test_execute_transfer_stage_updates_state(self, task_manager):
        config = TaskConfig(
            task_type=TaskType.TRANSFER_ONLY,
            model_source="huggingface",
            model_id="bert-base-uncased"
        )
        task_id = task_manager.create_task(config)
        
        task_manager._execute_transfer_stage(task_id)
        
        task = task_manager._db.get_task(task_id)
        assert task.state == "completed"
    
    def test_execute_verify_stage_updates_state(self, task_manager):
        config = TaskConfig(
            task_type=TaskType.DOWNLOAD_ONLY,
            model_source="huggingface",
            model_id="bert-base-uncased"
        )
        task_id = task_manager.create_task(config)
        
        task_manager._execute_verify_stage(task_id)
        
        task = task_manager._db.get_task(task_id)
        assert task.state == "completed"


class TestTaskSignals:
    def test_task_state_changed_signal(self, task_manager, qtbot):
        config = TaskConfig(
            task_type=TaskType.DOWNLOAD_ONLY,
            model_source="huggingface",
            model_id="bert-base-uncased"
        )
        task_id = task_manager.create_task(config)
        
        spy = QSignalSpy(task_manager.task_state_changed)
        task_manager._execute_download_stage(task_id)
        
        assert len(spy) >= 1
        
        # Check that the signal was emitted with correct arguments
        found_downloading = False
        for i in range(len(spy)):
            args = spy[i]
            if args[0] == task_id and args[1] == "downloading":
                found_downloading = True
        
        assert found_downloading
    
    def test_task_completed_signal(self, task_manager, qtbot):
        config = TaskConfig(
            task_type=TaskType.DOWNLOAD_ONLY,
            model_source="huggingface",
            model_id="bert-base-uncased"
        )
        task_id = task_manager.create_task(config)
        
        spy = QSignalSpy(task_manager.task_completed)
        task_manager._execute_download_stage(task_id)
        
        assert len(spy) == 1
        assert spy[0][0] == task_id
    
    def test_transfer_task_state_changed(self, task_manager, qtbot):
        config = TaskConfig(
            task_type=TaskType.TRANSFER_ONLY,
            model_source="huggingface",
            model_id="bert-base-uncased"
        )
        task_id = task_manager.create_task(config)
        
        spy = QSignalSpy(task_manager.task_state_changed)
        task_manager._execute_transfer_stage(task_id)
        
        assert len(spy) >= 1
        
        found_transferring = False
        for i in range(len(spy)):
            args = spy[i]
            if args[0] == task_id and args[1] == "transferring":
                found_transferring = True
        
        assert found_transferring


class TestTaskScheduling:
    def test_concurrent_task_limit(self, task_manager, monkeypatch):
        active_executions = []
        
        def mock_download_stage(tid):
            active_executions.append(tid)
            task_manager._db.update_task_state(tid, "downloading")
            task_manager.task_state_changed.emit(tid, "downloading")
            # Don't complete - simulate long-running task
        
        monkeypatch.setattr(task_manager, '_execute_download_stage', mock_download_stage)
        
        configs = [
            TaskConfig(
                task_type=TaskType.DOWNLOAD_ONLY,
                model_source="huggingface",
                model_id=f"model-{i}"
            )
            for i in range(3)
        ]
        
        task_ids = []
        for config in configs:
            tid = task_manager.create_task(config)
            task_ids.append(tid)
        
        # Should have at most MAX_CONCURRENT_TASKS active
        assert len(task_manager._active_tasks) <= task_manager.MAX_CONCURRENT_TASKS
        assert task_manager.MAX_CONCURRENT_TASKS == 2
        
        # Third task should be in queue
        if len(task_manager._active_tasks) == 2:
            assert len(task_manager._task_queue) == 1
    
    def test_task_queue_processing(self, task_manager):
        task_ids = []
        for i in range(3):
            config = TaskConfig(
                task_type=TaskType.DOWNLOAD_ONLY,
                model_source="huggingface",
                model_id=f"model-{i}"
            )
            tid = task_manager.create_task(config)
            task_ids.append(tid)
        
        # All tasks should be completed (synchronous execution)
        for tid in task_ids:
            task = task_manager._db.get_task(tid)
            assert task.state == "completed"
    
    def test_full_pipeline_task(self, task_manager, qtbot):
        config = TaskConfig(
            task_type=TaskType.FULL_PIPELINE,
            model_source="huggingface",
            model_id="bert-base-uncased"
        )
        task_id = task_manager.create_task(config)
        
        spy = QSignalSpy(task_manager.task_state_changed)
        task_manager._execute_download_stage(task_id)
        
        assert len(spy) >= 1
        
        def check_completed():
            task = task_manager._db.get_task(task_id)
            return task.state == "completed"
        
        qtbot.wait(500)

        task = task_manager._db.get_task(task_id)
        assert task.state == "completed"
        


class TestTaskConfig:
    def test_task_type_enum(self):
        assert TaskType.DOWNLOAD_ONLY.value == "download_only"
        assert TaskType.TRANSFER_ONLY.value == "transfer_only"
        assert TaskType.FULL_PIPELINE.value == "full_pipeline"
    
    def test_task_state_enum(self):
        assert TaskState.PENDING.value == "pending"
        assert TaskState.DOWNLOADING.value == "downloading"
        assert TaskState.COMPLETED.value == "completed"
    
    def test_stage_state_enum(self):
        assert StageState.NOT_STARTED.value == "not_started"
        assert StageState.IN_PROGRESS.value == "in_progress"
        assert StageState.COMPLETED.value == "completed"
    
    def test_task_file_default_values(self):
        task_file = TaskFile(file_path="test.bin", file_size=1024)
        
        assert task_file.expected_hash is None
        assert task_file.hash_algorithm is None
        assert task_file.download_state == StageState.NOT_STARTED
        assert task_file.download_bytes == 0
        assert task_file.local_path is None
        assert task_file.verify_state == StageState.NOT_STARTED
        assert task_file.actual_hash is None
        assert task_file.transfer_state == StageState.NOT_STARTED
        assert task_file.transfer_bytes == 0
        assert task_file.remote_path is None
        assert task_file.retry_count == 0
        assert task_file.error_message is None
    
    def test_task_config_default_values(self):
        config = TaskConfig(
            task_type=TaskType.DOWNLOAD_ONLY,
            model_source="huggingface",
            model_id="bert-base"
        )
        
        assert config.revision == "main"
        assert config.local_cache_dir == Path("cache")
        assert config.file_filter is None
        assert config.remote_host is None
        assert config.remote_path is None
        assert config.files == []

import pytest
import tempfile
import os
import sqlite3
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

# Import the Database class (will fail initially)
try:
    from core.database import Database, TaskRecord
except ImportError:
    TaskRecord = None
    Database = None


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = Database(db_path)
    db.init_schema()
    
    yield db
    
    # Cleanup
    db.close()
    os.unlink(db_path)


class TestTaskRecord:
    def test_task_record_exists(self):
        """TaskRecord dataclass should exist with correct fields."""
        assert TaskRecord is not None
    
    def test_task_record_creation(self):
        """TaskRecord should be creatable with required fields."""
        if TaskRecord is None:
            pytest.skip("TaskRecord not implemented yet")
        
        record = TaskRecord(
            id="test-123",
            task_type="download",
            state="pending",
            model_source="huggingface",
            model_id="bert-base",
            revision="main",
            local_cache_dir="/tmp/test"
        )
        
        assert record.id == "test-123"
        assert record.task_type == "download"
        assert record.state == "pending"
        assert record.model_source == "huggingface"
        assert record.model_id == "bert-base"
        assert record.revision == "main"
        assert record.local_cache_dir == "/tmp/test"
        assert record.remote_host is None
        assert record.remote_path is None


class TestDatabaseSchema:
    def test_database_init(self):
        """Database should initialize with a path."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            db = Database(db_path)
            assert db is not None
            db.close()
        finally:
            os.unlink(db_path)
    
    def test_init_schema_creates_tables(self, temp_db):
        """init_schema should create all required tables."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        # Get list of tables
        conn = sqlite3.connect(temp_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        required_tables = {'tasks', 'task_files', 'server_configs', 'app_settings', 'operation_logs'}
        assert required_tables.issubset(tables), f"Missing tables: {required_tables - tables}"


class TestTaskCRUD:
    def test_create_task(self, temp_db):
        """Should create a task and return its ID."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        task_id = temp_db.create_task(
            task_type="download",
            model_source="huggingface",
            model_id="bert-base-uncased",
            revision="main",
            local_cache_dir="/tmp/cache",
            remote_host="server1",
            remote_path="/models"
        )
        
        assert task_id is not None
        assert isinstance(task_id, str)
    
    def test_get_task(self, temp_db):
        """Should retrieve a created task."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        task_id = temp_db.create_task(
            task_type="upload",
            model_source="modelscope",
            model_id="llama-7b",
            local_cache_dir="/tmp/cache2"
        )
        
        task = temp_db.get_task(task_id)
        
        assert task is not None
        assert task.id == task_id
        assert task.task_type == "upload"
        assert task.model_source == "modelscope"
        assert task.model_id == "llama-7b"
        assert task.state == "pending"
    
    def test_get_task_not_found(self, temp_db):
        """Should return None for non-existent task."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        task = temp_db.get_task("non-existent-id")
        assert task is None
    
    def test_update_task_state(self, temp_db):
        """Should update task state."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        task_id = temp_db.create_task(
            task_type="download",
            model_source="huggingface",
            model_id="test-model",
            local_cache_dir="/tmp/cache"
        )
        
        success = temp_db.update_task_state(task_id, "running")
        assert success is True
        
        task = temp_db.get_task(task_id)
        assert task.state == "running"
    
    def test_update_task_state_with_progress(self, temp_db):
        """Should update task state with progress info."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        task_id = temp_db.create_task(
            task_type="download",
            model_source="huggingface",
            model_id="test-model",
            local_cache_dir="/tmp/cache"
        )
        
        success = temp_db.update_task_state(
            task_id, 
            "completed",
            completed_files=10,
            total_files=10,
            completed_bytes=1024000,
            total_bytes=1024000
        )
        
        assert success is True
        
        task = temp_db.get_task(task_id)
        assert task.state == "completed"


class TestFileCRUD:
    def test_add_task_file(self, temp_db):
        """Should add a file to a task."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        task_id = temp_db.create_task(
            task_type="download",
            model_source="huggingface",
            model_id="test-model",
            local_cache_dir="/tmp/cache"
        )
        
        file_id = temp_db.add_task_file(
            task_id=task_id,
            file_path="model.bin",
            file_size=1024,
            expected_hash="abc123"
        )
        
        assert file_id is not None
        assert isinstance(file_id, int)
    
    def test_get_task_files(self, temp_db):
        """Should retrieve files for a task."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        task_id = temp_db.create_task(
            task_type="download",
            model_source="huggingface",
            model_id="test-model",
            local_cache_dir="/tmp/cache"
        )
        
        temp_db.add_task_file(task_id, "file1.bin", 100)
        temp_db.add_task_file(task_id, "file2.bin", 200)
        
        files = temp_db.get_task_files(task_id)
        
        assert len(files) == 2
        assert files[0]['file_path'] in ['file1.bin', 'file2.bin']
        assert files[1]['file_path'] in ['file1.bin', 'file2.bin']
    
    def test_update_file_state(self, temp_db):
        """Should update file download state."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        task_id = temp_db.create_task(
            task_type="download",
            model_source="huggingface",
            model_id="test-model",
            local_cache_dir="/tmp/cache"
        )
        
        file_id = temp_db.add_task_file(task_id, "model.bin", 1024)
        
        success = temp_db.update_file_state(
            file_id,
            download_state="downloading",
            download_bytes=512
        )
        
        assert success is True
        
        files = temp_db.get_task_files(task_id)
        assert files[0]['download_state'] == "downloading"
        assert files[0]['download_bytes'] == 512


class TestServerConfig:
    def test_save_server_config(self, temp_db):
        """Should save server configuration."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        config_id = temp_db.save_server_config(
            name="server1",
            host="192.168.1.1",
            port=22,
            username="admin",
            auth_type="password",
            encrypted_auth=b"encrypted_data",
            auth_salt=b"salt_data"
        )
        
        assert config_id is not None
        assert isinstance(config_id, int)
    
    def test_get_server_configs(self, temp_db):
        """Should retrieve all server configurations."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        temp_db.save_server_config(
            name="server1",
            host="192.168.1.1",
            username="admin",
            auth_type="password",
            encrypted_auth=b"encrypted_data",
            auth_salt=b"salt_data"
        )
        
        temp_db.save_server_config(
            name="server2",
            host="192.168.1.2",
            username="root",
            auth_type="key",
            encrypted_auth=b"encrypted_key",
            auth_salt=b"salt_key"
        )
        
        configs = temp_db.get_server_configs()
        
        assert len(configs) == 2
        assert configs[0]['name'] in ['server1', 'server2']
        assert configs[1]['name'] in ['server1', 'server2']


class TestAppSettings:
    def test_set_and_get_setting(self, temp_db):
        """Should set and retrieve application settings."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        temp_db.set_setting("download_dir", "/tmp/downloads")
        
        value = temp_db.get_setting("download_dir")
        
        assert value == "/tmp/downloads"
    
    def test_get_setting_default(self, temp_db):
        """Should return default value for non-existent setting."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        value = temp_db.get_setting("non_existent", default="default_value")
        
        assert value == "default_value"
    
    def test_update_setting(self, temp_db):
        """Should update existing setting."""
        if Database is None:
            pytest.skip("Database not implemented yet")
        
        temp_db.set_setting("key1", "value1")
        temp_db.set_setting("key1", "value2")
        
        value = temp_db.get_setting("key1")
        
        assert value == "value2"

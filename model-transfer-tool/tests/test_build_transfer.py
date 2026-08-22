"""TaskManager 传输解析测试——spec 定义的 seam 2:_build_transfer 按 profile 构造 RsyncTransfer。"""

import os
import tempfile
from types import SimpleNamespace

import pytest

from core.database import Database
from core.task_manager import TaskManager
from core.transfers.rsync_transfer import RsyncTransfer
from utils.crypto import SecureStorage


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    db.init_schema()

    db.save_server_config(
        name="prod",
        host="10.0.0.9",
        username="deploy",
        auth_type="ssh_key",
        encrypted_auth=b"\x00" * (SecureStorage.NONCE_LENGTH + 4),
        auth_salt=b"\x01" * SecureStorage.SALT_LENGTH,
        port=2222,
    )
    yield db
    db.close()
    os.unlink(db_path)


@pytest.fixture
def task_manager(temp_db):
    return TaskManager(temp_db)


def _task(remote_host):
    return SimpleNamespace(remote_host=remote_host)


class TestBuildTransfer:
    def test_uses_profile_values(self, task_manager, monkeypatch):
        monkeypatch.setattr(
            SecureStorage, "decrypt",
            classmethod(lambda cls, ciphertext, nonce, salt: "/home/deploy/.ssh/id_ed25519"),
        )
        transfer = task_manager._build_transfer(_task("prod"))

        assert isinstance(transfer, RsyncTransfer)
        assert transfer.host == "10.0.0.9"
        assert transfer.username == "deploy"
        assert transfer.port == 2222
        assert transfer.ssh_key == "/home/deploy/.ssh/id_ed25519"

    def test_no_server_falls_back_to_defaults(self, task_manager):
        transfer = task_manager._build_transfer(_task(None))
        assert transfer.host == "localhost"
        assert transfer.username == "user"

    def test_unknown_name_falls_back_to_defaults(self, task_manager):
        transfer = task_manager._build_transfer(_task("ghost"))
        assert transfer.host == "localhost"
        assert transfer.username == "user"

    def test_password_profile_has_no_key(self, task_manager, temp_db):
        temp_db.save_server_config(
            name="pw",
            host="10.0.0.5",
            username="root",
            auth_type="password",
            encrypted_auth=b"\x00" * (SecureStorage.NONCE_LENGTH + 4),
            auth_salt=b"\x01" * SecureStorage.SALT_LENGTH,
            port=22,
        )
        transfer = task_manager._build_transfer(_task("pw"))
        assert transfer.host == "10.0.0.5"
        assert transfer.ssh_key is None
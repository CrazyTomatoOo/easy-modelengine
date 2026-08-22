"""ServerProfile 模块测试——spec 定义的 seam 1:DB rows ↔ 类型化 profile + 密钥路径解密。"""

import tempfile
import os

import pytest

from core.database import Database
from core.server_profile import ServerProfile, load_all, find
from utils.crypto import SecureStorage


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    db.init_schema()
    yield db
    db.close()
    os.unlink(db_path)


def _save(db, name="srv-1", host="192.168.1.10", port=22, username="ubuntu", auth_type="ssh_key"):
    db.save_server_config(
        name=name,
        host=host,
        username=username,
        auth_type=auth_type,
        encrypted_auth=b"\x00" * (SecureStorage.NONCE_LENGTH + 4),
        auth_salt=b"\x01" * SecureStorage.SALT_LENGTH,
        port=port,
    )


class TestFromRow:
    def test_constructs_from_row(self, temp_db):
        _save(temp_db)
        profile = load_all(temp_db)[0]
        assert profile.name == "srv-1"
        assert profile.host == "192.168.1.10"
        assert profile.port == 22
        assert profile.username == "ubuntu"
        assert profile.auth_type == "ssh_key"
        assert profile.encrypted_auth == b"\x00" * (SecureStorage.NONCE_LENGTH + 4)
        assert profile.auth_salt == b"\x01" * SecureStorage.SALT_LENGTH

    def test_load_all_returns_multiple(self, temp_db):
        _save(temp_db, name="a")
        _save(temp_db, name="b", host="10.0.0.2")
        profiles = load_all(temp_db)
        assert {p.name for p in profiles} == {"a", "b"}


class TestFind:
    def test_finds_by_name(self, temp_db):
        _save(temp_db, name="prod")
        profile = find(temp_db, "prod")
        assert profile is not None
        assert profile.host == "192.168.1.10"

    def test_missing_name_returns_none(self, temp_db):
        _save(temp_db)
        assert find(temp_db, "nope") is None


class TestPassword:
    def test_decrypts_password_for_password_auth(self, temp_db, monkeypatch):
        _save(temp_db, auth_type="password")
        monkeypatch.setattr(
            SecureStorage, "decrypt",
            classmethod(lambda cls, ciphertext, nonce, salt: "s3cret"),
        )
        profile = load_all(temp_db)[0]
        assert profile.password() == "s3cret"

    def test_ssh_key_auth_returns_none(self, temp_db):
        _save(temp_db, auth_type="ssh_key")
        assert load_all(temp_db)[0].password() is None

    def test_decrypt_failure_returns_none(self, temp_db, monkeypatch):
        _save(temp_db, auth_type="password")

        def boom(cls, ciphertext, nonce, salt):
            raise ValueError("bad")

        monkeypatch.setattr(SecureStorage, "decrypt", classmethod(boom))
        assert load_all(temp_db)[0].password() is None


class TestSshKeyPath:
    def test_decrypts_key_path_for_ssh_key_auth(self, temp_db, monkeypatch):
        _save(temp_db)
        monkeypatch.setattr(
            SecureStorage, "decrypt",
            classmethod(lambda cls, ciphertext, nonce, salt: "/home/u/.ssh/id_ed25519"),
        )
        profile = load_all(temp_db)[0]
        assert profile.ssh_key_path() == "/home/u/.ssh/id_ed25519"

    def test_password_auth_returns_none(self, temp_db):
        _save(temp_db, auth_type="password")
        profile = load_all(temp_db)[0]
        assert profile.ssh_key_path() is None

    def test_decrypt_failure_returns_none(self, temp_db, monkeypatch):
        _save(temp_db)
        def boom(cls, ciphertext, nonce, salt):
            raise ValueError("解密失败")
        monkeypatch.setattr(SecureStorage, "decrypt", classmethod(boom))
        profile = load_all(temp_db)[0]
        assert profile.ssh_key_path() is None
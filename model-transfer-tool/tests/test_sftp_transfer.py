"""SftpTransfer 测试——spec #25 的 seam 1:注入客户端工厂,零网络。"""

import io
import sys
from pathlib import Path

import pytest

from core.transfers.sftp_transfer import SftpTransfer, _require_paramiko


class FakeSFTP:
    def __init__(self):
        self.put_args = []

    def put(self, local, remote):
        self.put_args.append((local, remote))

    def close(self):
        pass


class FakeClient:
    def __init__(self, fail_connect=None):
        self.sftp = FakeSFTP()
        self.connected = 0
        self.connect_kwargs = None
        self.exec_cmd = None
        self.exec_output = b""
        self.fail_connect = fail_connect

    def set_missing_host_key_policy(self, policy):
        self.policy = policy

    def connect(self, **kwargs):
        if self.fail_connect:
            raise self.fail_connect
        self.connected += 1
        self.connect_kwargs = kwargs

    def open_sftp(self):
        return self.sftp

    def exec_command(self, cmd):
        self.exec_cmd = cmd
        return (io.StringIO(), io.BytesIO(self.exec_output), io.BytesIO(b""))

    def close(self):
        pass


def _attach(transfer, client, monkeypatch):
    """注入客户端工厂,让 _connect 使用给定 fake 实例。"""
    monkeypatch.setattr(transfer, "_new_client", lambda paramiko: client)
    monkeypatch.setattr(
        "core.transfers.sftp_transfer._require_paramiko", lambda: object()
    )
    return client


TRANSFER = SftpTransfer(host="10.0.0.9", username="deploy", port=2222, password="secret")


class TestConnect:
    def test_password_passed_to_connect(self, monkeypatch):
        client = _attach(TRANSFER, FakeClient(), monkeypatch)
        TRANSFER._connect()
        assert client.connected == 1
        assert client.connect_kwargs["password"] == "secret"
        assert client.connect_kwargs["port"] == 2222
        assert client.connect_kwargs["key_filename"] is None

    def test_key_passed_when_given(self, monkeypatch):
        transfer = SftpTransfer("h", "u", ssh_key="/home/u/.ssh/id_ed25519")
        client = _attach(transfer, FakeClient(), monkeypatch)
        transfer._connect()
        assert client.connect_kwargs["key_filename"] == "/home/u/.ssh/id_ed25519"

    def test_missing_paramiko_raises_with_guidance(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "paramiko", None)
        with pytest.raises(RuntimeError, match="pip install paramiko"):
            _require_paramiko()


class TestTransferFile:
    def test_uploads_and_reports_progress(self, monkeypatch, tmp_path):
        client = _attach(TRANSFER, FakeClient(), monkeypatch)
        src = tmp_path / "a.bin"
        src.write_bytes(b"x" * 16)
        progress = []

        ok = TRANSFER.transfer_file(src, "/models/a.bin", progress_callback=lambda c, t: progress.append((c, t)))

        assert ok is True
        assert client.sftp.put_args == [(str(src), "/models/a.bin")]
        assert progress == [(16, 16)]

    def test_failure_returns_false(self, monkeypatch, tmp_path):
        _attach(TRANSFER, FakeClient(), monkeypatch)
        missing = tmp_path / "nope.bin"
        assert TRANSFER.transfer_file(missing, "/models/nope.bin") is False

    def test_upload_error_returns_false(self, monkeypatch, tmp_path):
        src = tmp_path / "a.bin"
        src.write_bytes(b"x")

        class BoomClient(FakeClient):
            def open_sftp(self):
                raise OSError("sftp down")

        _attach(TRANSFER, BoomClient(), monkeypatch)
        assert TRANSFER.transfer_file(src, "/m/a.bin") is False


class TestVerifyChecksum:
    def test_matching_hash(self, monkeypatch):
        client = _attach(TRANSFER, FakeClient(), monkeypatch)
        client.exec_output = b"abc123  /models/a.bin\n"
        assert TRANSFER.verify_remote_checksum("/models/a.bin", "ABC123", "sha256") is True
        # '/' 是 shlex 安全字符:不额外加引号
        assert client.exec_cmd == "sha256sum /models/a.bin"

    def test_mismatch(self, monkeypatch):
        client = _attach(TRANSFER, FakeClient(), monkeypatch)
        client.exec_output = b"deadbeef  /models/a.bin\n"
        assert TRANSFER.verify_remote_checksum("/models/a.bin", "abc123", "sha256") is False

    def test_unsupported_algorithm(self, monkeypatch):
        _attach(TRANSFER, FakeClient(), monkeypatch)
        assert TRANSFER.verify_remote_checksum("/m", "x", "sha1") is False

    def test_injection_paths_are_quoted(self, monkeypatch):
        client = _attach(TRANSFER, FakeClient(), monkeypatch)
        client.exec_output = b"abc123  /m\n"
        TRANSFER.verify_remote_checksum("/models/evil; rm -rf /", "abc123", "sha256")
        assert client.exec_cmd == "sha256sum '/models/evil; rm -rf /'"


class TestConnectivity:
    def test_success(self, monkeypatch):
        client = _attach(TRANSFER, FakeClient(), monkeypatch)
        ok, msg = TRANSFER.check_connectivity()
        assert ok is True
        assert client.connected == 1

    def test_failure_reports_reason(self, monkeypatch):
        client = _attach(TRANSFER, FakeClient(fail_connect=TimeoutError("timed out")), monkeypatch)
        ok, msg = TRANSFER.check_connectivity()
        assert ok is False
        assert "timed out" in msg
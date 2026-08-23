"""RemoteShell 单元测试——校验编排与命令构造的单一 seam,零网络。"""

import subprocess

import pytest

from core.remote_shell import RemoteShell, SSHProcessConnector


class FakeConnector:
    def __init__(self, rc=0, output="", error=None):
        self.rc = rc
        self.output = output
        self.error = error
        self.commands = []

    def exec(self, remote_command):
        self.commands.append(remote_command)
        if self.error:
            raise self.error
        return self.rc, self.output


def _shell(connector=None):
    return RemoteShell(connector or FakeConnector())


class TestVerifyChecksum:
    def test_matching_hash(self):
        connector = FakeConnector(output="abc123  /models/a.bin\n")
        assert _shell(connector).verify_checksum("/models/a.bin", "ABC123", "sha256") is True
        assert connector.commands == ["sha256sum /models/a.bin"]

    def test_mismatch(self):
        connector = FakeConnector(output="deadbeef  /models/a.bin\n")
        assert _shell(connector).verify_checksum("/models/a.bin", "abc123", "sha256") is False

    def test_unsupported_algorithm_skips_exec(self):
        connector = FakeConnector()
        assert _shell(connector).verify_checksum("/m", "x", "sha1") is False
        assert connector.commands == []

    def test_remote_path_quoted_against_injection(self):
        """注入面:路径经 shlex.quote 后才拼进远程命令。"""
        connector = FakeConnector(output="abc123  /m\n")
        _shell(connector).verify_checksum("/models/evil; rm -rf /", "abc123", "sha256")
        assert connector.commands == ["sha256sum '/models/evil; rm -rf /'"]

    def test_rc_nonzero_is_failure(self):
        connector = FakeConnector(rc=2, output="abc123  /m\n")
        assert _shell(connector).verify_checksum("/m", "abc123", "sha256") is False

    def test_md5_uses_md5sum(self):
        connector = FakeConnector(output="d41d8cd98f00b204e9800998ecf8427e  /m\n")
        assert _shell(connector).verify_checksum("/m", "D41D8CD98F00B204E9800998ECF8427E", "md5") is True
        assert connector.commands == ["md5sum /m"]


class TestConnectivity:
    def test_success(self):
        connector = FakeConnector(output="ok")
        assert _shell(connector).check_connectivity() == (True, "Connected successfully")

    def test_nonzero_rc_failure(self):
        connector = FakeConnector(rc=1, output="")
        ok, msg = _shell(connector).check_connectivity()
        assert ok is False
        assert msg == "Connection failed"

    def test_exception_reports_reason(self):
        connector = FakeConnector(error=TimeoutError("timed out"))
        ok, msg = _shell(connector).check_connectivity()
        assert ok is False
        assert "timed out" in msg

    def test_runtime_error_guidance_propagates(self):
        """paramiko 缺失指引必须到达调用方,不得被泛化失败吞掉。"""
        connector = FakeConnector(error=RuntimeError("pip install paramiko"))
        with pytest.raises(RuntimeError, match="paramiko"):
            _shell(connector).check_connectivity()


class TestSSHProcessConnector:
    def test_build_cmd_structure(self):
        """远程命令是最后一个 argv:不经过本地 shell,注入无从发生。"""
        c = SSHProcessConnector(host="10.0.0.9", username="deploy", port=2222, ssh_key="/k/id")
        cmd = c._build_cmd("sha256sum '/m'")
        assert cmd == [
            "ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
            "-p", "2222", "-i", "/k/id", "deploy@10.0.0.9",
            "sha256sum '/m'",
        ]

    def test_no_key_omits_i_flag(self):
        c = SSHProcessConnector(host="h", username="u")
        assert "-i" not in c._build_cmd("echo ok")

    def test_exec_passes_argv_through(self, monkeypatch):
        import core.remote_shell as rs_mod

        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess([], 0, stdout="abc  /m\n", stderr="")

        monkeypatch.setattr(rs_mod.subprocess, "run", fake_run)
        c = SSHProcessConnector("h", "u")
        code, output = c.exec("sha256sum /m")
        assert (code, output) == (0, "abc  /m\n")
        assert calls == [
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
             "-p", "22", "u@h", "sha256sum /m"],
        ]
"""RemoteShell —— 远程命令执行与校验编排的单一 seam。

connector 接口抽象两种传输:ssh 子进程(rsync 密钥路径)与 paramiko exec
(密码路径);checksum 验证与连通性编排在这里只写一次(Q1A 决策),测试注入
fake connector 即可脱离真实网络。命令构造与路径引用集中在 RemoteShell
一处——rsync/sftp 的引用分歧(先前 rsync 裸插值)从根上消除。

契约:Connector.exec(remote_command) 返回 (exit_code, stdout);
RemoteShell 负责 algorithm guard、shlex 引用、输出解析与比对。
"""

import shlex
import subprocess
from abc import ABC, abstractmethod
from typing import Optional, Tuple

_HASH_CMDS = {"sha256": "sha256sum", "md5": "md5sum"}


def _require_paramiko():
    """懒加载 paramiko;缺失时抛出带安装指引的 RuntimeError。"""
    try:
        import paramiko
    except ImportError as e:
        raise RuntimeError(
            "密码认证传输需要 paramiko,请安装: pip install paramiko"
        ) from e
    return paramiko


class Connector(ABC):
    """远程命令执行通道(adapter 差异:子进程 vs paramiko)。"""

    @abstractmethod
    def exec(self, remote_command: str) -> Tuple[int, str]:
        """执行远程命令;返回 (exit_code, stdout)。失败抛异常由调用方处理。"""
        ...


class SSHProcessConnector(Connector):
    """ssh 子进程通道:密钥认证,无密码(rsync 路径)。"""

    def __init__(
        self,
        host: str,
        username: str,
        port: int = 22,
        ssh_key: Optional[str] = None,
    ):
        self.host = host
        self.username = username
        self.port = port
        self.ssh_key = ssh_key

    def _build_cmd(self, remote_command: str) -> list[str]:
        cmd = [
            'ssh',
            '-o', 'ConnectTimeout=5',
            '-o', 'BatchMode=yes',
            '-p', str(self.port),
        ]
        if self.ssh_key:
            cmd.extend(['-i', self.ssh_key])
        cmd.extend([f'{self.username}@{self.host}', remote_command])
        return cmd

    def exec(self, remote_command: str) -> Tuple[int, str]:
        result = subprocess.run(
            self._build_cmd(remote_command),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout


class ParamikoConnector(Connector):
    """paramiko exec_command 通道:密码与密钥认证(懒加载,RejectPolicy)。"""

    def __init__(
        self,
        host: str,
        username: str,
        port: int = 22,
        password: Optional[str] = None,
        ssh_key: Optional[str] = None,
    ):
        self.host = host
        self.username = username
        self.port = port
        self.password = password
        self.ssh_key = ssh_key

    def _new_client(self, paramiko):
        """创建并配置 SSHClient(测试可注入实例工厂)。

        拒绝未知主机密钥(不静默信任,防 MITM 窃取密码);已存在于
        系统 known_hosts 的主机可正常连接。
        """
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        return client

    def exec(self, remote_command: str) -> Tuple[int, str]:
        paramiko = _require_paramiko()
        client = self._new_client(paramiko)
        try:
            client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                key_filename=self.ssh_key,
                timeout=10,
            )
            _stdin, stdout, _stderr = client.exec_command(remote_command)
            code = stdout.channel.recv_exit_status()
            return code, stdout.read().decode(errors="replace").strip()
        finally:
            client.close()


class RemoteShell:
    """远程 shell 编排:checksum 验证与连通性探测(Connector 之上)。

    路径引用集中于此(shlex.quote)——两个传输通道共享同一引用语义。
    """

    def __init__(self, connector: Connector):
        self._connector = connector

    def verify_checksum(
        self, remote_path: str, expected_hash: str, algorithm: str
    ) -> bool:
        hash_cmd = _HASH_CMDS.get(algorithm)
        if hash_cmd is None:
            return False
        try:
            code, output = self._connector.exec(
                f"{hash_cmd} {shlex.quote(remote_path)}"
            )
        except RuntimeError:
            raise  # paramiko 缺失指引必须到达调用方
        except Exception:
            return False
        if code:
            return False
        parts = output.strip().split()
        return bool(parts) and parts[0].lower() == expected_hash.lower()

    def check_connectivity(self) -> Tuple[bool, str]:
        try:
            code, output = self._connector.exec("echo ok")
        except RuntimeError:
            raise  # paramiko 缺失指引必须到达调用方
        except subprocess.TimeoutExpired:
            return False, "Connection timed out"
        except Exception as e:
            return False, str(e)
        if code == 0 and "ok" in output:
            return True, "Connected successfully"
        return False, "Connection failed"
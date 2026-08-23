"""SftpTransfer —— 基于 paramiko 的 SFTP 传输适配器(spec #25)。

密码与密钥认证均支持;paramiko 懒加载,缺失时给出安装指引。
RsyncTransfer 保留用于 SSH 密钥路径,密码路径走本适配器。
"""

from pathlib import Path
from typing import Callable, Optional, Tuple

from core.interfaces import TransferStrategy
from core.remote_shell import _require_paramiko, ParamikoConnector, RemoteShell


class SftpTransfer(TransferStrategy):
    """通过 paramiko SFTP 传输文件,支持密码与 SSH 密钥认证。

    校验/连通性委托 RemoteShell(Q1A);本类只管 SFTP 上传。
    """

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
        self._shell = RemoteShell(self._build_connector())

    def _build_connector(self) -> ParamikoConnector:
        return ParamikoConnector(
            host=self.host,
            username=self.username,
            port=self.port,
            password=self.password,
            ssh_key=self.ssh_key,
        )

    def _new_client(self, paramiko):
        """创建并配置 SSHClient(测试可注入实例工厂)。

        拒绝未知主机密钥(不静默信任,防 MITM 窃取密码);已存在于
        系统 known_hosts 的主机可正常连接。
        """
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        return client

    def _connect(self):
        paramiko = _require_paramiko()
        client = self._new_client(paramiko)
        client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            key_filename=self.ssh_key,
            timeout=10,
        )
        return client

    def transfer_file(
        self,
        local_path: Path,
        remote_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """上传单个文件;失败按策略契约返回 False。"""
        try:
            total = Path(local_path).stat().st_size
            client = self._connect()
            try:
                sftp = client.open_sftp()
                try:
                    sftp.put(str(local_path), remote_path)
                finally:
                    sftp.close()
            finally:
                client.close()
            if progress_callback:
                progress_callback(total, total)
            return True
        except RuntimeError:
            raise  # paramiko 缺失指引必须到达调用方,不能被泛化失败吞掉
        except Exception:
            return False

    def verify_remote_checksum(
        self, remote_path: str, expected_hash: str, algorithm: str
    ) -> bool:
        """在远程计算校验和并比对(委托 RemoteShell)"""
        return self._shell.verify_checksum(remote_path, expected_hash, algorithm)

    def check_connectivity(self) -> Tuple[bool, str]:
        """尝试建立 SSH 连接;成功返回 (True, ...),失败返回原因。"""
        return self._shell.check_connectivity()
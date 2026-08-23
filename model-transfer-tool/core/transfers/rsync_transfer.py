import re
import shlex
import subprocess
from pathlib import Path
from typing import Callable, Optional, Tuple

from core.interfaces import TransferStrategy
from core.remote_shell import RemoteShell, SSHProcessConnector


class RsyncTransfer(TransferStrategy):
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
        # 校验/连通性委托 RemoteShell(Q1A):rsync 只管传输
        self._shell = RemoteShell(self._build_connector())

    def _build_connector(self) -> SSHProcessConnector:
        return SSHProcessConnector(
            host=self.host,
            username=self.username,
            port=self.port,
            ssh_key=self.ssh_key,
        )

    def _build_rsync_cmd(
        self, local_path: Path, remote_path: str, progress: bool = False
    ) -> list[str]:
        cmd = ['rsync', '-avz', '--partial', '--append-verify']
        if progress:
            cmd.append('--info=progress2')
        ssh_opts = f"-p {self.port}"
        if self.ssh_key:
            ssh_opts += f" -i {self.ssh_key}"
        cmd.extend(['-e', f'ssh {ssh_opts}'])
        cmd.append(str(local_path))
        # 远端目标引用:注入面修复(Q1A)
        cmd.append(f"{self.username}@{self.host}:{shlex.quote(remote_path)}")
        return cmd

    def transfer_file(
        self,
        local_path: Path,
        remote_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        progress = progress_callback is not None
        cmd = self._build_rsync_cmd(local_path, remote_path, progress=progress)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            total_size = local_path.stat().st_size if local_path.exists() else 0

            if process.stdout is not None and progress_callback is not None:
                for line in process.stdout:
                    match = re.search(r'(\d+)%', line)
                    if match:
                        percent = int(match.group(1))
                        transferred = int(total_size * percent / 100)
                        progress_callback(transferred, total_size)

            stdout, stderr = process.communicate()
            return process.returncode == 0
        except Exception:
            return False

    def verify_remote_checksum(
        self, remote_path: str, expected_hash: str, algorithm: str
    ) -> bool:
        return self._shell.verify_checksum(remote_path, expected_hash, algorithm)

    def check_connectivity(self) -> Tuple[bool, str]:
        return self._shell.check_connectivity()
import re
import subprocess
from pathlib import Path
from typing import Callable, Optional, Tuple

from core.interfaces import TransferStrategy


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
        cmd.append(f"{self.username}@{self.host}:{remote_path}")
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
        if algorithm not in ('sha256', 'md5'):
            return False

        cmd = self._build_ssh_cmd(algorithm, remote_path)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return False

            output = result.stdout.strip()
            parts = output.split()
            if not parts:
                return False

            remote_hash = parts[0]
            return remote_hash.lower() == expected_hash.lower()
        except Exception:
            return False

    def check_connectivity(self) -> Tuple[bool, str]:
        cmd = [
            'ssh',
            '-o',
            'ConnectTimeout=5',
            '-o',
            'BatchMode=yes',
            '-p',
            str(self.port),
        ]
        if self.ssh_key:
            cmd.extend(['-i', self.ssh_key])
        cmd.append(f'{self.username}@{self.host}')
        cmd.append('echo ok')

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and 'ok' in result.stdout:
                return True, 'Connected successfully'
            return False, result.stderr.strip() or 'Connection failed'
        except subprocess.TimeoutExpired:
            return False, 'Connection timed out'
        except Exception as e:
            return False, str(e)

    def _build_ssh_cmd(self, algorithm: str, remote_path: str) -> list[str]:
        hash_cmd = 'sha256sum' if algorithm == 'sha256' else 'md5sum'
        cmd = [
            'ssh',
            '-o',
            'ConnectTimeout=5',
            '-p',
            str(self.port),
        ]
        if self.ssh_key:
            cmd.extend(['-i', self.ssh_key])
        cmd.extend([
            f'{self.username}@{self.host}',
            f'{hash_cmd} {remote_path}',
        ])
        return cmd

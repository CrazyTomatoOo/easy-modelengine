from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple


@dataclass
class FileInfo:
    path: str
    size: int
    url: Optional[str] = None


class DownloadStrategy(ABC):
    @abstractmethod
    def list_files(self, model_id: str, revision: str) -> list[FileInfo]:
        pass

    @abstractmethod
    def download_file(
        self,
        model_id: str,
        revision: str,
        file_info: FileInfo,
        local_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        pass

    @abstractmethod
    def get_checksum(
        self, model_id: str, revision: str, file_path: str
    ) -> Optional[Tuple[str, str]]:
        pass


class TransferStrategy(ABC):
    @abstractmethod
    def transfer_file(
        self,
        local_path: Path,
        remote_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        pass

    @abstractmethod
    def verify_remote_checksum(self, remote_path: str, expected_hash: str, algorithm: str) -> bool:
        pass

    @abstractmethod
    def check_connectivity(self) -> Tuple[bool, str]:
        pass

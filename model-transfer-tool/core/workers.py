import threading
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtCore import QObject, pyqtSignal, QRunnable

from core.interfaces import DownloadStrategy, FileInfo, TransferStrategy
from core.verifier import FileVerifier


class WorkerSignals(QObject):
    """Worker 信号定义"""

    progress = pyqtSignal(str, str, int, int)
    finished = pyqtSignal(str, str, bool)
    error = pyqtSignal(str, str, str)


class DownloadWorker(QRunnable):
    """下载工作线程"""

    def __init__(
        self,
        task_id: str,
        file_info: FileInfo,
        downloader: DownloadStrategy,
        model_id: str,
        revision: str,
        local_path: Path,
    ):
        super().__init__()
        self.task_id = task_id
        self.file_info = file_info
        self.downloader = downloader
        self.model_id = model_id
        self.revision = revision
        self.local_path = Path(local_path)
        self.signals = WorkerSignals()
        self._cancelled = False
        self.done_event = threading.Event()

    def run(self):
        """执行下载任务"""
        if self._cancelled:
            self.done_event.set()
            return

        try:
            self.local_path.parent.mkdir(parents=True, exist_ok=True)

            def progress_callback(current: int, total: int):
                if not self._cancelled:
                    self.signals.progress.emit(
                        self.task_id,
                        self.file_info.path,
                        current,
                        total,
                    )

            success = self.downloader.download_file(
                model_id=self.model_id,
                revision=self.revision,
                file_info=self.file_info,
                local_path=self.local_path,
                progress_callback=progress_callback,
            )

            if self._cancelled:
                return

            if success:
                self.signals.finished.emit(
                    self.task_id,
                    self.file_info.path,
                    True,
                )
            else:
                self.signals.error.emit(
                    self.task_id,
                    self.file_info.path,
                    "下载失败",
                )

        except Exception as e:
            if not self._cancelled:
                self.signals.error.emit(
                    self.task_id,
                    self.file_info.path,
                    str(e),
                )
        finally:
            self.done_event.set()

    def cancel(self):
        """取消下载任务"""
        self._cancelled = True


class TransferWorker(QRunnable):
    """传输工作线程"""

    def __init__(
        self,
        task_id: str,
        file_path: str,
        transfer: TransferStrategy,
        local_path: Path,
        remote_path: str,
        expected_hash: Optional[str] = None,
        hash_algorithm: str = "sha256",
    ):
        super().__init__()
        self.task_id = task_id
        self.file_path = file_path
        self.transfer = transfer
        self.local_path = Path(local_path)
        self.remote_path = remote_path
        self.expected_hash = expected_hash
        self.hash_algorithm = hash_algorithm
        self.signals = WorkerSignals()
        self._cancelled = False
        self.done_event = threading.Event()

    def run(self):
        """执行传输任务"""
        if self._cancelled:
            self.done_event.set()
            return

        try:
            total_size = self.local_path.stat().st_size if self.local_path.exists() else 0

            def progress_callback(current: int, total: int):
                if not self._cancelled:
                    self.signals.progress.emit(
                        self.task_id,
                        self.file_path,
                        current,
                        total,
                    )

            success = self.transfer.transfer_file(
                local_path=self.local_path,
                remote_path=self.remote_path,
                progress_callback=progress_callback,
            )

            if self._cancelled:
                return

            if success:
                # 传输后远程校验:期望值来自源校验和;本地源无源校验和,取本地实时哈希
                expected = self.expected_hash
                try:
                    if not expected:
                        expected = FileVerifier.compute_hash(
                            self.local_path, self.hash_algorithm
                        )
                    remote_ok = self.transfer.verify_remote_checksum(
                        remote_path=self.remote_path,
                        expected_hash=expected,
                        algorithm=self.hash_algorithm,
                    )
                except Exception as e:
                    self.signals.error.emit(
                        self.task_id,
                        self.file_path,
                        f"远程校验错误: {str(e)}",
                    )
                    return

                if remote_ok:
                    self.signals.finished.emit(
                        self.task_id,
                        self.file_path,
                        True,
                    )
                else:
                    # 远端校验失败:本地文件完好,任务失败,远端残件保留(rsync 可续传)
                    self.signals.error.emit(
                        self.task_id,
                        self.file_path,
                        "远程校验失败：远端哈希与期望不符",
                    )
            else:
                self.signals.error.emit(
                    self.task_id,
                    self.file_path,
                    "传输失败",
                )

        except Exception as e:
            if not self._cancelled:
                self.signals.error.emit(
                    self.task_id,
                    self.file_path,
                    str(e),
                )
        finally:
            self.done_event.set()

    def cancel(self):
        """取消传输任务"""
        self._cancelled = True
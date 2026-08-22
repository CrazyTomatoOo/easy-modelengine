import threading
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtCore import QObject, pyqtSignal, QRunnable

from core.interfaces import DownloadStrategy, FileInfo, TransferStrategy


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
    ):
        super().__init__()
        self.task_id = task_id
        self.file_path = file_path
        self.transfer = transfer
        self.local_path = Path(local_path)
        self.remote_path = remote_path
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
                self.signals.finished.emit(
                    self.task_id,
                    self.file_path,
                    True,
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

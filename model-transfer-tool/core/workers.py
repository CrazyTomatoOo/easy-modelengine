import threading
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from core.interfaces import DownloadStrategy, FileInfo, TransferStrategy
from core.verifier import FileVerifier


class WorkerSignals(QObject):
    """Worker 信号定义"""

    progress = pyqtSignal(str, str, int, int)
    finished = pyqtSignal(str, str, bool)
    error = pyqtSignal(str, str, str)


class WorkerBase(QRunnable):
    """QRunnable 壳——取消 flag、done_event、终态发射契约一处定义。

    契约:_run_impl 经 emit_finished/emit_error 恰好发射一个终态信号;
    壳只保证 done_event 兜底;若 _run_impl 未发射即抛异常,壳补发 error
    (避免双发)。子类只写策略(#6A 决策)。
    """

    def __init__(self, task_id: str, file_path: str):
        super().__init__()
        self.task_id = task_id
        self.file_path = file_path
        self.signals = WorkerSignals()
        self._cancelled = False
        self._terminal_emitted = False
        self.done_event = threading.Event()

    # ---- 壳:run 骨架 ----

    def run(self):
        """执行任务;终态发射由 _run_impl 负责,壳兜底异常与 done_event。"""
        if self._cancelled:
            self.done_event.set()
            return

        try:
            self._run_impl()
        except Exception as e:
            if not self._terminal_emitted and not self._cancelled:
                self.signals.error.emit(self.task_id, self.file_path, str(e))
        finally:
            self.done_event.set()

    def cancel(self):
        """取消任务"""
        self._cancelled = True

    # ---- 终态发射契约 ----

    def emit_finished(self, success: bool) -> None:
        self._terminal_emitted = True
        self.signals.finished.emit(self.task_id, self.file_path, success)

    def emit_error(self, message: str) -> None:
        self._terminal_emitted = True
        self.signals.error.emit(self.task_id, self.file_path, message)

    def _run_impl(self) -> None:
        """粘贴到此的策略主体:恰发一个终态信号;异常交给壳兜底。"""
        raise NotImplementedError


class DownloadWorker(WorkerBase):
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
        super().__init__(task_id, file_info.path)
        self.file_info = file_info
        self.downloader = downloader
        self.model_id = model_id
        self.revision = revision
        self.local_path = Path(local_path)

    def _run_impl(self):
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
            self.emit_finished(True)
        else:
            self.emit_error("下载失败")


class VerifyWorker(WorkerBase):
    """校验工作线程——按源校验和做全文件哈希比对。

    只算不写(Q5B):结果经 result 属性暴露,由 TaskManager 回写数据库;
    哈希不匹配时删除损坏文件(恢复逻辑按大小跳过,坏文件不得滞留)。
    """

    def __init__(
        self,
        task_id: str,
        file_path: str,
        local_path: Path,
        expected_hash: str,
        hash_algorithm: str = "sha256",
    ):
        super().__init__(task_id, file_path)
        self.local_path = Path(local_path)
        self.expected_hash = expected_hash
        self.hash_algorithm = hash_algorithm
        self.actual_hash: Optional[str] = None

    def _run_impl(self):
        try:
            size = self.local_path.stat().st_size if self.local_path.exists() else 0
            self.actual_hash = FileVerifier.compute_hash(
                self.local_path, self.hash_algorithm
            )
        except FileNotFoundError:
            self.emit_error("文件不存在，无法校验")
            return

        if self._cancelled:
            return

        verified = self.actual_hash.lower() == self.expected_hash.lower()
        if verified:
            self.signals.progress.emit(
                self.task_id,
                self.file_path,
                size,
                size,
            )
            self.emit_finished(True)
        else:
            # 删除损坏缓存,避免恢复按大小跳过使坏文件永久滞留
            try:
                self.local_path.unlink(missing_ok=True)
            except OSError:
                pass
            self.emit_error("校验失败：哈希值不匹配,已删除损坏文件")


class TransferWorker(WorkerBase):
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
        super().__init__(task_id, file_path)
        self.transfer = transfer
        self.local_path = Path(local_path)
        self.remote_path = remote_path
        self.expected_hash = expected_hash
        self.hash_algorithm = hash_algorithm

    def _run_impl(self):
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

        if not success:
            self.emit_error("传输失败")
            return

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
            self.emit_error(f"远程校验错误: {str(e)}")
            return

        if remote_ok:
            self.emit_finished(True)
        else:
            # 远端校验失败:本地文件完好,任务失败,远端残件保留(rsync 可续传)
            self.emit_error("远程校验失败：远端哈希与期望不符")
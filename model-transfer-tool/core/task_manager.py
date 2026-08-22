from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool, QRunnable

from core.database import Database
from core.task_config import TaskConfig, TaskType, TaskState, TaskFile
from core.interfaces import FileInfo
from core.downloaders.hf_downloader import HuggingFaceDownloader
from core.downloaders.local_strategy import LocalDirStrategy
from core.downloaders.ms_downloader import ModelScopeDownloader
from core.verifier import FileVerifier
from core.workers import DownloadWorker, TransferWorker
from core.server_profile import find as find_profile
from core.transfers.rsync_transfer import RsyncTransfer


class StageRunnable(QRunnable):
    def __init__(self, task_manager: 'TaskManager', task_id: str, stage_method: Callable[[str], None]):
        super().__init__()
        self._task_manager = task_manager
        self._task_id = task_id
        self._stage_method = stage_method

    def run(self):
        self._stage_method(self._task_id)


class TaskManager(QObject):
    task_state_changed = pyqtSignal(str, str)
    task_progress = pyqtSignal(str, str, int, int)
    task_error = pyqtSignal(str, str, str)
    task_warning = pyqtSignal(str, str, str)
    task_completed = pyqtSignal(str)

    MAX_CONCURRENT_TASKS = 2

    def __init__(self, db: Database):
        super().__init__()
        self._db = db
        self._task_queue: list[str] = []
        self._active_tasks: set[str] = set()
        self._download_pool = QThreadPool()
        self._verify_pool = QThreadPool()
        self._transfer_pool = QThreadPool()

        # 跟踪活跃的文件 workers
        self._active_download_workers: dict[str, dict[str, DownloadWorker]] = {}
        self._active_transfer_workers: dict[str, dict[str, TransferWorker]] = {}

        # 跟踪文件完成状态
        self._task_file_completed: dict[str, set[str]] = {}
        self._task_file_failed: dict[str, set[str]] = {}
        self._task_file_total: dict[str, int] = {}

    def create_task(self, config: TaskConfig) -> str:
        task_id = self._db.create_task(
            task_type=config.task_type.value,
            model_source=config.model_source,
            model_id=config.model_id,
            local_cache_dir=str(config.local_cache_dir),
            revision=config.revision,
            remote_host=config.remote_host,
            remote_path=config.remote_path,
            file_filter=config.file_filter
        )

        for task_file in config.files:
            self._db.add_task_file(
                task_id=task_id,
                file_path=task_file.file_path,
                file_size=task_file.file_size,
                expected_hash=task_file.expected_hash,
                hash_algorithm=task_file.hash_algorithm
            )

        self._task_queue.append(task_id)
        self._try_schedule_next()

        return task_id

    def _try_schedule_next(self) -> None:
        while len(self._active_tasks) < self.MAX_CONCURRENT_TASKS and self._task_queue:
            task_id = self._task_queue.pop(0)
            self._active_tasks.add(task_id)
            self._start_task(task_id)

    def _start_task(self, task_id: str) -> None:
        task = self._db.get_task(task_id)
        if task is None:
            if task_id in self._active_tasks:
                self._active_tasks.remove(task_id)
            return

        task_type = TaskType(task.task_type)

        if task_type == TaskType.DOWNLOAD_ONLY:
            runnable = StageRunnable(self, task_id, self._execute_download_stage)
            self._download_pool.start(runnable)
        elif task_type == TaskType.TRANSFER_ONLY:
            runnable = StageRunnable(self, task_id, self._execute_transfer_stage)
            self._transfer_pool.start(runnable)
        elif task_type == TaskType.FULL_PIPELINE:
            runnable = StageRunnable(self, task_id, self._execute_download_stage)
            self._download_pool.start(runnable)

    def _create_downloader(self, model_source: str):
        """根据模型源创建下载器，自动应用代理设置"""
        # 从数据库读取代理设置
        proxy = None
        enable_proxy = self._db.get_setting("enable_proxy", "false")
        if enable_proxy.lower() == "true":
            http_proxy = self._db.get_setting("proxy_http", "")
            https_proxy = self._db.get_setting("proxy_https", "")
            proxy = https_proxy or http_proxy or None
        
        if model_source == "huggingface":
            return HuggingFaceDownloader(proxy=proxy)
        elif model_source == "modelscope":
            return ModelScopeDownloader(proxy=proxy)
        elif model_source == "local":
            return LocalDirStrategy()
        else:
            raise ValueError(f"不支持的模型源: {model_source}")

    def _execute_download_stage(self, task_id: str) -> None:
        self._db.update_task_state(task_id, TaskState.DOWNLOADING.value)
        self.task_state_changed.emit(task_id, TaskState.DOWNLOADING.value)

        task = self._db.get_task(task_id)
        files = self._db.get_task_files(task_id)

        if not files:
            self._on_download_stage_complete(task_id)
            return

        # 初始化文件跟踪状态
        self._active_download_workers[task_id] = {}
        self._task_file_completed[task_id] = set()
        self._task_file_failed[task_id] = set()
        self._task_file_total[task_id] = len(files)

        downloader = self._create_downloader(task.model_source)

        for file_dict in files:
            file_info = FileInfo(
                path=file_dict['file_path'],
                size=file_dict['file_size'],
                url=file_dict.get('remote_url')
            )
            local_path = Path(task.local_cache_dir) / file_dict['file_path']

            worker = DownloadWorker(
                task_id=task_id,
                file_info=file_info,
                downloader=downloader,
                model_id=task.model_id,
                revision=task.revision,
                local_path=local_path,
            )

            worker.signals.progress.connect(self._on_download_progress)
            worker.signals.finished.connect(self._on_download_file_finished)
            worker.signals.error.connect(self._on_download_file_error)

            self._download_pool.start(worker)
            self._active_download_workers[task_id][file_dict['file_path']] = worker

    def _on_download_progress(self, task_id: str, file_path: str, current: int, total: int):
        """处理下载进度信号"""
        self.task_progress.emit(task_id, file_path, current, total)

    def _on_download_file_finished(self, task_id: str, file_path: str, success: bool):
        """处理单个文件下载完成"""
        if task_id not in self._task_file_total:
            return

        # 从活跃 workers 中移除
        if task_id in self._active_download_workers:
            if file_path in self._active_download_workers[task_id]:
                del self._active_download_workers[task_id][file_path]

        if success:
            self._task_file_completed[task_id].add(file_path)
        else:
            self._task_file_failed[task_id].add(file_path)

        # 检查是否所有文件都处理完成
        self._check_download_complete(task_id)

    def _on_download_file_error(self, task_id: str, file_path: str, error: str):
        """处理单个文件下载错误"""
        self.task_error.emit(task_id, file_path, error)

        if task_id not in self._task_file_total:
            return

        # 从活跃 workers 中移除
        if task_id in self._active_download_workers:
            if file_path in self._active_download_workers[task_id]:
                del self._active_download_workers[task_id][file_path]

        self._task_file_failed[task_id].add(file_path)

        # 检查是否所有文件都处理完成
        self._check_download_complete(task_id)

    def _check_download_complete(self, task_id: str):
        """检查下载阶段是否全部完成"""
        total = self._task_file_total.get(task_id, 0)
        completed = len(self._task_file_completed.get(task_id, set()))
        failed = len(self._task_file_failed.get(task_id, set()))

        if completed + failed >= total:
            self._on_download_stage_complete(task_id)

    def _on_download_stage_complete(self, task_id: str):
        """下载阶段完成后的处理"""
        # 清理下载状态
        if task_id in self._active_download_workers:
            del self._active_download_workers[task_id]
        if task_id in self._task_file_completed:
            del self._task_file_completed[task_id]
        if task_id in self._task_file_failed:
            del self._task_file_failed[task_id]
        if task_id in self._task_file_total:
            del self._task_file_total[task_id]

        task = self._db.get_task(task_id)
        if task is None:
            return

        task_type = TaskType(task.task_type)

        if task_type == TaskType.DOWNLOAD_ONLY:
            self._complete_task(task_id)
        else:
            # FULL_PIPELINE 进入验证阶段
            runnable = StageRunnable(self, task_id, self._execute_verify_stage)
            self._verify_pool.start(runnable)

    def _execute_verify_stage(self, task_id: str) -> None:
        """执行校验阶段"""
        self._db.update_task_state(task_id, TaskState.VERIFYING.value)
        self.task_state_changed.emit(task_id, TaskState.VERIFYING.value)

        task = self._db.get_task(task_id)
        files = self._db.get_task_files(task_id)

        if not files:
            self._on_verify_stage_complete(task_id)
            return

        all_verified = True
        for file_dict in files:
            local_path = Path(task.local_cache_dir) / file_dict['file_path']

            if not local_path.exists():
                self.task_error.emit(
                    task_id,
                    file_dict['file_path'],
                    "文件不存在，无法校验"
                )
                all_verified = False
                continue

            expected_hash = file_dict.get('expected_hash')
            hash_algorithm = file_dict.get('hash_algorithm', 'sha256')

            if expected_hash and hash_algorithm:
                try:
                    verified = FileVerifier.verify(
                        file_path=local_path,
                        expected_hash=expected_hash,
                        algorithm=hash_algorithm,
                    )
                    if verified:
                        self.task_progress.emit(
                            task_id,
                            file_dict['file_path'],
                            file_dict['file_size'],
                            file_dict['file_size']
                        )
                    else:
                        self.task_error.emit(
                            task_id,
                            file_dict['file_path'],
                            "校验失败：哈希值不匹配"
                        )
                        all_verified = False
                except Exception as e:
                    self.task_error.emit(
                        task_id,
                        file_dict['file_path'],
                        f"校验错误: {str(e)}"
                    )
                    all_verified = False

        self._on_verify_stage_complete(task_id)

    def _on_verify_stage_complete(self, task_id: str):
        """验证阶段完成后的处理"""
        task = self._db.get_task(task_id)
        if task is None:
            return

        task_type = TaskType(task.task_type)

        if task_type == TaskType.FULL_PIPELINE:
            runnable = StageRunnable(self, task_id, self._execute_transfer_stage)
            self._transfer_pool.start(runnable)
        else:
            self._complete_task(task_id)

    def _build_transfer(self, task, profile=None) -> RsyncTransfer:
        """按任务引用的 Server profile 构造传输器。

        remote_host 为 profile name(自然键);空或查不到时回退默认
        主机/用户,兼容未配置服务器与旧任务。profile 可由调用方预解析
        并传入,避免 stage 内重复查询产生不一致快照。
        """
        server_name = task.remote_host or ""
        if profile is None and server_name:
            profile = find_profile(self._db, server_name)
        if profile is not None:
            return profile.to_transfer()
        return RsyncTransfer(host="localhost", username="user")

    def _execute_transfer_stage(self, task_id: str) -> None:
        """执行传输阶段"""
        self._db.update_task_state(task_id, TaskState.TRANSFERRING.value)
        self.task_state_changed.emit(task_id, TaskState.TRANSFERRING.value)

        task = self._db.get_task(task_id)
        files = self._db.get_task_files(task_id)

        if not files:
            self._on_transfer_stage_complete(task_id)
            return

        # 初始化文件跟踪状态
        self._active_transfer_workers[task_id] = {}
        self._task_file_completed[task_id] = set()
        self._task_file_failed[task_id] = set()
        self._task_file_total[task_id] = len(files)

        # 创建传输器:按任务引用的 Server profile 解析真实连接参数
        server_name = task.remote_host or ""
        profile = find_profile(self._db, server_name) if server_name else None
        transfer = self._build_transfer(task, profile=profile)
        if server_name and profile is None:
            self.task_warning.emit(
                task_id,
                "server",
                f"未找到服务器配置 {server_name!r},使用默认传输设置",
            )

        for file_dict in files:
            local_path = Path(task.local_cache_dir) / file_dict['file_path']
            remote_path = f"{task.remote_path or ''}/{file_dict['file_path']}"

            worker = TransferWorker(
                task_id=task_id,
                file_path=file_dict['file_path'],
                transfer=transfer,
                local_path=local_path,
                remote_path=remote_path,
            )

            worker.signals.progress.connect(self._on_transfer_progress)
            worker.signals.finished.connect(self._on_transfer_file_finished)
            worker.signals.error.connect(self._on_transfer_file_error)

            self._transfer_pool.start(worker)
            self._active_transfer_workers[task_id][file_dict['file_path']] = worker

    def _on_transfer_progress(self, task_id: str, file_path: str, current: int, total: int):
        """处理传输进度信号"""
        self.task_progress.emit(task_id, file_path, current, total)

    def _on_transfer_file_finished(self, task_id: str, file_path: str, success: bool):
        """处理单个文件传输完成"""
        if task_id not in self._task_file_total:
            return

        # 从活跃 workers 中移除
        if task_id in self._active_transfer_workers:
            if file_path in self._active_transfer_workers[task_id]:
                del self._active_transfer_workers[task_id][file_path]

        if success:
            self._task_file_completed[task_id].add(file_path)
        else:
            self._task_file_failed[task_id].add(file_path)

        # 检查是否所有文件都处理完成
        self._check_transfer_complete(task_id)

    def _on_transfer_file_error(self, task_id: str, file_path: str, error: str):
        """处理单个文件传输错误"""
        self.task_error.emit(task_id, file_path, error)

        if task_id not in self._task_file_total:
            return

        # 从活跃 workers 中移除
        if task_id in self._active_transfer_workers:
            if file_path in self._active_transfer_workers[task_id]:
                del self._active_transfer_workers[task_id][file_path]

        self._task_file_failed[task_id].add(file_path)

        # 检查是否所有文件都处理完成
        self._check_transfer_complete(task_id)

    def _check_transfer_complete(self, task_id: str):
        """检查传输阶段是否全部完成"""
        total = self._task_file_total.get(task_id, 0)
        completed = len(self._task_file_completed.get(task_id, set()))
        failed = len(self._task_file_failed.get(task_id, set()))

        if completed + failed >= total:
            self._on_transfer_stage_complete(task_id)

    def _on_transfer_stage_complete(self, task_id: str):
        """传输阶段完成后的处理"""
        # 清理传输状态
        if task_id in self._active_transfer_workers:
            del self._active_transfer_workers[task_id]
        if task_id in self._task_file_completed:
            del self._task_file_completed[task_id]
        if task_id in self._task_file_failed:
            del self._task_file_failed[task_id]
        if task_id in self._task_file_total:
            del self._task_file_total[task_id]

        self._complete_task(task_id)

    def _complete_task(self, task_id: str):
        """完成任务"""
        self._db.update_task_state(task_id, TaskState.COMPLETED.value)
        self.task_state_changed.emit(task_id, TaskState.COMPLETED.value)
        self.task_completed.emit(task_id)

        if task_id in self._active_tasks:
            self._active_tasks.remove(task_id)
        self._try_schedule_next()

import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

from modelscope.hub.api import HubApi
from modelscope.hub.file_download import model_file_download

from core.interfaces import DownloadStrategy, FileInfo


class ModelScopeDownloader(DownloadStrategy):
    def __init__(self, token: Optional[str] = None, cache_dir: Optional[Path] = None, proxy: Optional[str] = None):
        self.api = HubApi()
        if token:
            self.api.login(token)
        self.cache_dir = cache_dir
        self.proxy = proxy

    def list_files(self, model_id: str, revision: str) -> list[FileInfo]:
        try:
            files = self.api.get_model_files(
                model_id=model_id,
                revision=revision,
                recursive=True,
            )
        except Exception as e:
            raise ValueError(f"Failed to list files for {model_id}: {e}")

        file_infos = []
        for file_info in files:
            if file_info.get("Type") == "tree":
                continue
            path = file_info.get("Path", "")
            size = file_info.get("Size", 0)
            file_infos.append(FileInfo(path=path, size=size, url=None))

        return file_infos

    def download_file(
        self,
        model_id: str,
        revision: str,
        file_info: FileInfo,
        local_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        local_path = Path(local_path)
        temp_dir = None

        try:
            # 创建临时目录
            temp_dir = Path(tempfile.mkdtemp(prefix="ms_download_"))

            # 初始化进度
            if progress_callback:
                progress_callback(0, file_info.size)

            # 设置进度监控
            stop_event = threading.Event()
            monitor_thread = None

            if progress_callback and file_info.size > 0:
                def _monitor():
                    while not stop_event.is_set():
                        total_current = 0
                        try:
                            for f in temp_dir.rglob("*"):
                                if f.is_file():
                                    total_current += f.stat().st_size
                        except OSError:
                            pass

                        progress_callback(min(total_current, file_info.size), file_info.size)
                        time.sleep(0.5)

                monitor_thread = threading.Thread(target=_monitor, daemon=True)
                monitor_thread.start()

            try:
                # 设置代理环境变量（如果配置了）
                if self.proxy:
                    os.environ['HTTP_PROXY'] = self.proxy
                    os.environ['HTTPS_PROXY'] = self.proxy
                
                cache_dir = str(self.cache_dir) if self.cache_dir else None
                downloaded_path = model_file_download(
                    model_id=model_id,
                    file_path=file_info.path,
                    revision=revision,
                    cache_dir=cache_dir,
                    local_dir=str(temp_dir),
                )
            finally:
                stop_event.set()
                if monitor_thread:
                    monitor_thread.join(timeout=2)
                # 清理代理环境变量
                if self.proxy:
                    os.environ.pop('HTTP_PROXY', None)
                    os.environ.pop('HTTPS_PROXY', None)

            if downloaded_path is None:
                return False

            downloaded_path = Path(downloaded_path)

            if not downloaded_path.exists():
                return False

            # 确保目标目录存在
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # 如果路径相同，无需操作
            if downloaded_path.resolve() == local_path.resolve():
                return True

            # 如果在临时目录中，移动；否则从缓存复制
            if str(temp_dir) in str(downloaded_path):
                shutil.move(str(downloaded_path), str(local_path))
            else:
                shutil.copy2(str(downloaded_path), str(local_path))

            # 最终进度
            if progress_callback:
                progress_callback(file_info.size, file_info.size)

            return True

        except Exception:
            return False
        finally:
            if temp_dir is not None:
                try:
                    if temp_dir.exists():
                        shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

    def get_checksum(
        self, model_id: str, revision: str, file_path: str
    ) -> Optional[Tuple[str, str]]:
        return None

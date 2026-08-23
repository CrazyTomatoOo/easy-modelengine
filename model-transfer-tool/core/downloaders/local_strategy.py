"""本地目录作为下载来源的策略适配器——『列表』=扫描目录,『下载』=复制。"""

import os
import shutil
from pathlib import Path
from typing import Callable, Optional

from core.interfaces import DownloadStrategy, FileInfo


class LocalDirStrategy(DownloadStrategy):
    """把本地目录当作模型来源:list_files 产出相对路径文件列表,download_file 复制到目标。"""

    def list_files(self, model_id: str, revision: str) -> list[FileInfo]:
        base = Path(model_id)
        files = []
        for root, _dirs, names in os.walk(base):
            for name in names:
                full = Path(root) / name
                rel = full.relative_to(base).as_posix()
                files.append(FileInfo(path=rel, size=full.stat().st_size))
        return files

    def download_file(
        self,
        model_id: str,
        revision: str,
        file_info: FileInfo,
        local_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """复制文件到目标;失败按策略契约返回 False 而非抛异常。"""
        try:
            dest = Path(local_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(model_id) / file_info.path, dest)
        except OSError:
            return False
        if progress_callback:
            progress_callback(file_info.size, file_info.size)
        return True

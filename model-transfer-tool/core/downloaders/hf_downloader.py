import os
from pathlib import Path
from typing import Callable, Optional

import requests
from huggingface_hub import HfApi
from huggingface_hub.utils import RepositoryNotFoundError

from core.interfaces import DownloadStrategy, FileInfo


class HuggingFaceDownloader(DownloadStrategy):
    def __init__(
        self,
        token: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        proxy: Optional[str] = None,
    ):
        self.api = HfApi(token=token)
        self.cache_dir = cache_dir
        self.proxy = proxy
        self.session = requests.Session()
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    def list_files(self, model_id: str, revision: str) -> list[FileInfo]:
        try:
            files = self.api.list_repo_files(repo_id=model_id, revision=revision)
        except RepositoryNotFoundError:
            raise ValueError(f"Repository not found: {model_id}")

        file_infos = []
        for file_path in files:
            file_info = self.api.file_metadata(
                repo_id=model_id, filename=file_path, revision=revision
            )
            size = getattr(file_info, "size", 0)
            lfs_sha256 = getattr(getattr(file_info, "lfs", None), "sha256", None)
            file_infos.append(FileInfo(path=file_path, size=size, expected_hash=lfs_sha256))

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
        tmp_path = local_path.with_suffix(local_path.suffix + ".tmp")

        headers = {}
        resume_byte_pos = 0

        if tmp_path.exists():
            resume_byte_pos = tmp_path.stat().st_size
            headers["Range"] = f"bytes={resume_byte_pos}-"

        url = self.api.hf_hub_url(repo_id=model_id, filename=file_info.path, revision=revision)

        try:
            with self.session.get(url, headers=headers, stream=True, timeout=30) as response:
                response.raise_for_status()

                total_size = int(response.headers.get("content-length", 0))
                if resume_byte_pos > 0 and response.status_code == 206:
                    total_size += resume_byte_pos
                elif resume_byte_pos > 0:
                    resume_byte_pos = 0
                    tmp_path.unlink(missing_ok=True)

                mode = "ab" if resume_byte_pos > 0 else "wb"
                with open(tmp_path, mode) as f:
                    downloaded = resume_byte_pos
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback:
                                progress_callback(downloaded, total_size)

            tmp_path.rename(local_path)
            return True

        except Exception:
            return False

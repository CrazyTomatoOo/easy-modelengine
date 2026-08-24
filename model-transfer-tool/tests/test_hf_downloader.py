"""HuggingFaceDownloader.list_files 回归测试 —— 必须经 get_paths_info(expand=True)
拿到真实大小与 LFS sha256(旧 file_metadata API 在 huggingface_hub>=1.0 已移除)。"""

from types import SimpleNamespace

import pytest
import requests
from huggingface_hub.utils import RepositoryNotFoundError

from core.downloaders.hf_downloader import HuggingFaceDownloader


class _FakeApi:
    def __init__(self, repo_files, infos):
        self._repo_files = repo_files
        self._infos = infos
        self.paths_info_calls = []
        self.repo_files_calls = []

    def list_repo_files(self, repo_id, revision):
        self.repo_files_calls.append((repo_id, revision))
        return self._repo_files

    def get_paths_info(self, repo_id, paths, *, expand, revision=None, repo_type=None, token=None):
        self.paths_info_calls.append((repo_id, list(paths), revision, expand))
        return self._infos


def _repo_file(path, size, sha256=None):
    return SimpleNamespace(path=path, size=size, lfs=SimpleNamespace(sha256=sha256) if sha256 else None)


class TestListFiles:
    def test_carries_expanded_size_and_lfs_sha256(self):
        d = HuggingFaceDownloader()
        d.api = _FakeApi(
            ["model.safetensors", "config.json"],
            [
                _repo_file("model.safetensors", 2_271_145_830, "a" * 64),
                _repo_file("config.json", 687),
            ],
        )

        files = d.list_files("BAAI/bge-m3", "main")

        assert d.api.repo_files_calls == [("BAAI/bge-m3", "main")]
        # expand=True 必须传递:拿真实字节数而非 LFS 指针大小
        assert d.api.paths_info_calls == [
            ("BAAI/bge-m3", ["model.safetensors", "config.json"], "main", True)
        ]
        assert files[0].path == "model.safetensors"
        assert files[0].size == 2_271_145_830
        assert files[0].expected_hash == "a" * 64
        assert files[1].expected_hash is None

    def test_not_found_becomes_value_error(self):
        d = HuggingFaceDownloader()
        d.api = _FakeApi([], [])
        d.api.list_repo_files = _not_found

        with pytest.raises(ValueError, match="not found"):
            d.list_files("nope/nonexistent", "main")


def _not_found(repo_id, revision):
    resp = requests.Response()
    resp.status_code = 404
    raise RepositoryNotFoundError(f"{repo_id} not found", response=resp)
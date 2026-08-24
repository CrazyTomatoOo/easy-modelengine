"""ModelScope 策略 revision 语义测试——HF 语义的 main 映射为 MS 默认分支 master。

回归:ModelScope 仓库默认分支是 master(无 main);向导版本下拉默认 main,
get_model_files(revision="main") 静默返回空,曾把存在的仓库误报为「仓库为空」。
"""

from pathlib import Path

from core.downloaders.ms_downloader import ModelScopeDownloader
from core.interfaces import FileInfo


class TestRevisionMapping:
    def test_resolve_main_to_master(self):
        """main→master;显式传入的其他分支原样保留。"""
        d = ModelScopeDownloader()
        assert d._resolve_revision("main") == "master"
        assert d._resolve_revision("master") == "master"
        assert d._resolve_revision("dev") == "dev"

    def test_list_files_passes_resolved_revision(self, monkeypatch):
        """list_files 收到 main 时,get_model_files 必须用 master。"""
        import core.downloaders.ms_downloader as ms_mod

        seen = {}

        def fake_get_model_files(self, model_id, revision, recursive):
            seen["revision"] = revision
            return [
                {"Path": "config.json", "Size": 1, "Type": "blob", "Sha256": None},
            ]

        monkeypatch.setattr(ms_mod.HubApi, "get_model_files", fake_get_model_files)

        d = ModelScopeDownloader()
        files = d.list_files("Qwen/Qwen3.5-0.8B", "main")

        assert seen["revision"] == "master"
        assert [f.path for f in files] == ["config.json"]

    def test_download_file_passes_resolved_revision(self, monkeypatch, tmp_path):
        """download_file 收到 main 时,SDK 调用必须用 master。"""
        import core.downloaders.ms_downloader as ms_mod

        seen = {}

        def fake_download(model_id, file_path, revision, cache_dir, local_dir):
            seen["revision"] = revision
            dest = Path(local_dir) / file_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"x")
            return str(dest)

        monkeypatch.setattr(ms_mod, "model_file_download", fake_download)

        d = ModelScopeDownloader()
        ok = d.download_file(
            "Qwen/Qwen3.5-0.8B",
            "main",
            FileInfo(path="config.json", size=1),
            tmp_path / "config.json",
        )

        assert ok
        assert seen["revision"] == "master"
        assert (tmp_path / "config.json").exists()
"""ModelScope 代理锁测试——spec 定义的 seam:T3 竞态串行化。"""

import os
import threading
import time
from pathlib import Path

import pytest

from core.downloaders.ms_downloader import ModelScopeDownloader, _MS_PROXY_LOCK
from core.interfaces import FileInfo


class TestProxySerialization:
    def test_noproxy_download_never_sees_proxy_env(self, monkeypatch, tmp_path):
        """确定性并发:代理窗口保持期间启动无代理下载,其观测 env 必须干净。"""
        import core.downloaders.ms_downloader as ms_mod

        records = []
        rec_lock = threading.Lock()
        proxy_window_started = threading.Event()
        release_window = threading.Event()

        def fake(model_id, file_path, revision, cache_dir, local_dir):
            env = os.environ.get("HTTP_PROXY")
            with rec_lock:
                records.append((threading.get_ident(), env))
            if env:
                # 带代理调用:维持 env 窗口,直到主线程放行
                proxy_window_started.set()
                release_window.wait(5)
            dest = Path(local_dir) / file_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"x")
            return str(dest)

        monkeypatch.setattr(ms_mod, "model_file_download", fake)

        outcomes = []
        proxied = ModelScopeDownloader(proxy="http://p:8080")
        clean = ModelScopeDownloader()

        def run_proxy():
            outcomes.append(proxied.download_file("m", "main", FileInfo(path="a.bin", size=1), tmp_path / "a" / "a.bin"))

        def run_clean():
            outcomes.append(clean.download_file("m", "main", FileInfo(path="b.bin", size=1), tmp_path / "b" / "b.bin"))

        ta = threading.Thread(target=run_proxy)
        ta.start()
        assert proxy_window_started.wait(5), "proxy window never opened"

        tb = threading.Thread(target=run_clean)
        tb.start()
        tb.join(5)
        release_window.set()
        ta.join(5)

        assert all(outcomes)
        clean_records = [env for ident, env in records if ident == tb.ident]
        assert clean_records, "no-proxy thread never ran download"
        assert all(env is None for env in clean_records), f"无代理下载观测到代理 env: {clean_records}"

    def test_concurrent_downloads_never_overlap_env(self, monkeypatch, tmp_path):
        """两个并发 ms 下载使用不同代理时,env 窗口不得交替(锁生效)。"""
        import core.downloaders.ms_downloader as ms_mod

        seen = []
        observed = threading.Lock()

        def fake_download(model_id, file_path, revision, cache_dir, local_dir):
            with observed:
                seen.append(os.environ.get("HTTP_PROXY"))
            time.sleep(0.05)
            # 临界区退出点再观测一次:无锁实现会让第二线程在此窗口内进入
            with observed:
                seen.append(os.environ.get("HTTP_PROXY"))
            dest = Path(local_dir) / file_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"data")
            return str(dest)

        monkeypatch.setattr(ms_mod, "model_file_download", fake_download)

        file_info = FileInfo(path="model.bin", size=4)
        results = []
        errors = []

        def run(proxy):
            downloader = ModelScopeDownloader(proxy=proxy)
            try:
                results.append(downloader.download_file("m", "main", file_info, tmp_path / ("out-" + proxy[-1]) / "model.bin"))
            except Exception as e:  # noqa: BLE001 - 测试记录
                errors.append(e)

        threads = [threading.Thread(target=run, args=("http://proxy-1:8080",)), threading.Thread(target=run, args=("http://proxy-2:8080",))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(results)
        # env 观测序列必须分块(锁内全程):p1 段 + p2 段(或相反),不允许交替
        blocks = [v for i, v in enumerate(seen) if i == 0 or v != seen[i - 1]]
        assert len(blocks) <= 2, f"env 窗口交替: {seen}"

    def test_env_restored_after_download(self, monkeypatch, tmp_path):
        import core.downloaders.ms_downloader as ms_mod

        def fake_download(model_id, file_path, revision, cache_dir, local_dir):
            dest = Path(local_dir) / file_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"data")
            return str(dest)

        monkeypatch.setattr(ms_mod, "model_file_download", fake_download)

        # 模拟 ambient env:进入前已存在,结束后必须恢复而非删除
        monkeypatch.setenv("HTTP_PROXY", "http://ambient:3128")
        monkeypatch.setenv("HTTPS_PROXY", "http://ambient-ssl:3129")

        downloader = ModelScopeDownloader(proxy="http://p:8080")
        file_info = FileInfo(path="model.bin", size=4)
        result = downloader.download_file("m", "main", file_info, tmp_path / "out" / "model.bin")

        assert result is True
        assert os.environ.get("HTTP_PROXY") == "http://ambient:3128"
        assert os.environ.get("HTTPS_PROXY") == "http://ambient-ssl:3129"

    def test_env_removed_when_absent_before(self, monkeypatch, tmp_path):
        import core.downloaders.ms_downloader as ms_mod

        monkeypatch.delenv("HTTP_PROXY", raising=False)
        monkeypatch.delenv("HTTPS_PROXY", raising=False)

        def fake_download(model_id, file_path, revision, cache_dir, local_dir):
            dest = Path(local_dir) / file_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"data")
            return str(dest)

        monkeypatch.setattr(ms_mod, "model_file_download", fake_download)

        downloader = ModelScopeDownloader(proxy="http://p:8080")
        file_info = FileInfo(path="model.bin", size=4)
        downloader.download_file("m", "main", file_info, tmp_path / "out" / "model.bin")

        assert os.environ.get("HTTP_PROXY") is None
        assert os.environ.get("HTTPS_PROXY") is None

    def test_exception_still_clears_env(self, monkeypatch, tmp_path):
        import core.downloaders.ms_downloader as ms_mod

        monkeypatch.delenv("HTTP_PROXY", raising=False)
        monkeypatch.delenv("HTTPS_PROXY", raising=False)

        def boom(model_id, file_path, revision, cache_dir, local_dir):
            raise RuntimeError("network down")

        monkeypatch.setattr(ms_mod, "model_file_download", boom)

        downloader = ModelScopeDownloader(proxy="http://p:8080")
        file_info = FileInfo(path="model.bin", size=4)
        result = downloader.download_file("m", "main", file_info, tmp_path / "out" / "model.bin")

        assert result is False
        assert os.environ.get("HTTP_PROXY") is None
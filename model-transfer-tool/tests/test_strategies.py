"""策略统一构造测试——spec 定义的 seam 2:create_strategies(proxy) 与 _create_downloader 一致性。"""

import os
import tempfile

import pytest

from core.database import Database
from core.proxy_config import ProxyConfig
from core.task_intake import create_strategies, build, TaskDraft
from core.task_manager import TaskManager
from core.downloaders.hf_downloader import HuggingFaceDownloader
from core.downloaders.local_strategy import LocalDirStrategy


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    db.init_schema()
    yield db
    db.close()
    os.unlink(db_path)


class TestCreateStrategies:
    def test_no_proxy_defaults(self):
        strategies = create_strategies()
        assert set(strategies) == {"huggingface", "modelscope", "local"}
        assert isinstance(strategies["huggingface"], HuggingFaceDownloader)
        assert isinstance(strategies["local"], LocalDirStrategy)
        assert strategies["huggingface"].session.proxies == {}

    def test_proxy_applied_to_remote_sources(self):
        strategies = create_strategies(ProxyConfig(enable=True, http="http://p:8080", https="https://p:8443"))
        assert strategies["huggingface"].session.proxies == {"http": "https://p:8443", "https": "https://p:8443"}
        assert strategies["modelscope"].proxy == "https://p:8443"

    def test_disabled_proxy_no_proxy(self):
        strategies = create_strategies(ProxyConfig(enable=False, http="http://p:8080"))
        assert strategies["huggingface"].session.proxies == {}
        assert strategies["modelscope"].proxy is None


class TestCreateDownloaderConsistency:
    def test_manager_honors_saved_proxy(self, temp_db):
        temp_db.set_setting("enable_proxy", "true")
        temp_db.set_setting("proxy_http", "http://p:8080")
        manager = TaskManager(temp_db)
        hf = manager._create_downloader("huggingface")
        assert hf.session.proxies == {"http": "http://p:8080", "https": "http://p:8080"}

    def test_manager_no_proxy_by_default(self, temp_db):
        manager = TaskManager(temp_db)
        assert manager._create_downloader("huggingface").session.proxies == {}

    def test_manager_local_and_unknown(self, temp_db):
        manager = TaskManager(temp_db)
        assert isinstance(manager._create_downloader("local"), LocalDirStrategy)
        with pytest.raises(ValueError):
            manager._create_downloader("s3")


class TestListConsistency:
    def test_list_strategies_match_download_manager(self, temp_db):
        temp_db.set_setting("enable_proxy", "true")
        temp_db.set_setting("proxy_https", "https://p:8443")
        from core.proxy_config import load as load_proxy

        # 列表阶段策略(调用方经 create_strategies(load_proxy(db)) 传入 build)
        list_proxy = create_strategies(load_proxy(temp_db))["huggingface"].session.proxies
        # 下载阶段经 _create_downloader 同源构造
        manager = TaskManager(temp_db)
        download_proxy = manager._create_downloader("huggingface").session.proxies

        assert list_proxy == download_proxy == {"http": "https://p:8443", "https": "https://p:8443"}
"""ProxyConfig 模块测试——spec 定义的 seam 1:app_settings ↔ 类型化配置 + 校验。"""

import os
import tempfile

import pytest

from core.database import Database
from core.proxy_config import ProxyConfig, ProxyValidationError, load, save


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    db.init_schema()
    yield db
    db.close()
    os.unlink(db_path)


class TestLoadSave:
    def test_load_defaults_disabled(self, temp_db):
        config = load(temp_db)
        assert config.enable is False
        assert config.http == ""
        assert config.https == ""

    def test_round_trip(self, temp_db):
        save(temp_db, ProxyConfig(enable=True, http="http://p:8080", https="https://p:8443"))
        config = load(temp_db)
        assert config.enable is True
        assert config.http == "http://p:8080"
        assert config.https == "https://p:8443"

    def test_load_reads_legacy_app_settings(self, temp_db):
        temp_db.set_setting("enable_proxy", "true")
        temp_db.set_setting("proxy_http", "socks5://s:1080")
        config = load(temp_db)
        assert config.enable is True
        assert config.http == "socks5://s:1080"


class TestProxyUrl:
    def test_disabled_returns_none(self):
        assert ProxyConfig(enable=False, http="http://p:1").proxy_url() is None

    def test_http_when_no_https(self):
        assert ProxyConfig(enable=True, http="http://p:1").proxy_url() == "http://p:1"

    def test_https_preferred(self):
        config = ProxyConfig(enable=True, http="http://p:1", https="https://p:2")
        assert config.proxy_url() == "https://p:2"

    def test_enabled_but_empty_returns_none(self):
        assert ProxyConfig(enable=True).proxy_url() is None


class TestValidate:
    def test_valid_prefixes_pass(self):
        ProxyConfig(enable=True, http="http://a:1", https="socks5://b:2").validate()

    def test_invalid_http_rejected_with_field(self):
        with pytest.raises(ProxyValidationError) as exc:
            ProxyConfig(enable=True, http="proxy.company.com:8080").validate()
        assert exc.value.field == "http"

    def test_invalid_https_rejected(self):
        with pytest.raises(ProxyValidationError):
            ProxyConfig(enable=True, http="http://a:1", https="ftp://bad").validate()

    def test_empty_values_pass(self):
        ProxyConfig(enable=True).validate()

    def test_disabled_skips_validation(self):
        ProxyConfig(enable=False, http="not-a-url").validate()
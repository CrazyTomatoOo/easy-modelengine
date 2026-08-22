"""ProxyConfig —— 代理配置的类型化模块(CONTEXT.md:Proxy)。

列表与下载阶段的策略构造共用它;镜像源配置已删除(从未有消费者)。
"""

from dataclasses import dataclass
from typing import Optional

from core.database import Database

KEY_ENABLE_PROXY = "enable_proxy"
KEY_PROXY_HTTP = "proxy_http"
KEY_PROXY_HTTPS = "proxy_https"

_PROXY_PREFIXES = ("http://", "https://", "socks5://")


class ProxyValidationError(ValueError):
    """代理配置非法。"""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


@dataclass
class ProxyConfig:
    """代理配置值对象。"""

    enable: bool = False
    http: str = ""
    https: str = ""

    def proxy_url(self) -> Optional[str]:
        """下载器使用的代理地址:https 优先(现状语义);未启用返回 None。"""
        if not self.enable:
            return None
        return self.https or self.http or None

    def validate(self) -> None:
        """校验代理地址;非法抛 ProxyValidationError(带字段名),空值合法。"""
        if not self.enable:
            return
        for field, value in (("http", self.http), ("https", self.https)):
            if value and not value.startswith(_PROXY_PREFIXES):
                raise ProxyValidationError(field, f"{field} 代理地址格式不正确")


def load(db: Database) -> ProxyConfig:
    """从 app_settings 读取代理配置。"""
    return ProxyConfig(
        enable=db.get_setting(KEY_ENABLE_PROXY, "false").lower() == "true",
        http=db.get_setting(KEY_PROXY_HTTP, ""),
        https=db.get_setting(KEY_PROXY_HTTPS, ""),
    )


def save(db: Database, config: ProxyConfig) -> None:
    """写回代理配置到 app_settings。"""
    db.set_setting(KEY_ENABLE_PROXY, "true" if config.enable else "false")
    db.set_setting(KEY_PROXY_HTTP, config.http.strip())
    db.set_setting(KEY_PROXY_HTTPS, config.https.strip())
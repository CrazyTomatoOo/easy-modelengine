"""ServerProfile —— 服务器连接配置的类型化读取层(CONTEXT.md:Server profile)。

wizard 下拉与 Task 传输阶段按 name 引用它;SSH 密钥认证可用,密码通道留候选 6。
"""

from dataclasses import dataclass
from typing import Optional

from core.database import Database
from core.transfers.rsync_transfer import RsyncTransfer
from utils.crypto import SecureStorage


@dataclass(frozen=True)
class ServerProfile:
    """一条 server_configs 行的类型化视图。"""

    id: int
    name: str
    host: str
    port: int
    username: str
    auth_type: str  # password | ssh_key
    encrypted_auth: bytes  # nonce + ciphertext
    auth_salt: bytes

    @classmethod
    def from_row(cls, row: dict) -> "ServerProfile":
        return cls(
            id=row["id"],
            name=row["name"],
            host=row["host"],
            port=row["port"],
            username=row["username"],
            auth_type=row["auth_type"],
            encrypted_auth=bytes(row["encrypted_auth"]),
            auth_salt=bytes(row["auth_salt"]),
        )

    def ssh_key_path(self) -> Optional[str]:
        """ssh_key 认证时解密密钥文件路径;password 认证或解密失败返回 None。"""
        if self.auth_type != "ssh_key":
            return None
        try:
            nonce = self.encrypted_auth[: SecureStorage.NONCE_LENGTH]
            ciphertext = self.encrypted_auth[SecureStorage.NONCE_LENGTH:]
            return SecureStorage.decrypt(ciphertext, nonce, self.auth_salt)
        except Exception:
            return None

    def to_transfer(self) -> RsyncTransfer:
        """按本配置构造传输器(key 认证带解密密钥路径;password 认证无密钥)。"""
        return RsyncTransfer(
            host=self.host,
            username=self.username,
            port=self.port,
            ssh_key=self.ssh_key_path() if self.auth_type == "ssh_key" else None,
        )


def load_all(db: Database) -> list[ServerProfile]:
    """读取全部服务器配置。"""
    return [ServerProfile.from_row(row) for row in db.get_server_configs()]


def find(db: Database, name: str) -> Optional[ServerProfile]:
    """按 name(自然键)查找;未命中返回 None。"""
    for profile in load_all(db):
        if profile.name == name:
            return profile
    return None
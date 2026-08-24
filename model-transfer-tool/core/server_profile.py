"""ServerProfile —— 服务器连接配置的类型化读取层(CONTEXT.md:Server profile)。

wizard 下拉与 Task 传输阶段按 name 引用它;SSH 密钥认证走 rsync,
密码认证走 SFTP 适配器(paramiko)。
"""

from dataclasses import dataclass
from typing import Optional

from core.database import Database
from core.interfaces import TransferStrategy
from core.transfers.rsync_transfer import RsyncTransfer
from utils.credentials import unpack_credential


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

    def _decrypt_secret(self) -> Optional[str]:
        """解密加密凭据(拆包协议在 utils/credentials 单一实现);失败返回 None。"""
        try:
            return unpack_credential(self.encrypted_auth, self.auth_salt)
        except Exception:
            return None

    def ssh_key_path(self) -> Optional[str]:
        """ssh_key 认证时解密密钥文件路径;password 认证或解密失败返回 None。"""
        if self.auth_type != "ssh_key":
            return None
        return self._decrypt_secret()

    def password(self) -> Optional[str]:
        """password 认证时解密密码;ssh_key 认证或解密失败返回 None。"""
        if self.auth_type != "password":
            return None
        return self._decrypt_secret()

    def to_transfer(self) -> TransferStrategy:
        """按认证类型构造传输器:password → SftpTransfer,ssh_key → RsyncTransfer。"""
        if self.auth_type == "password":
            from core.transfers.sftp_transfer import SftpTransfer

            return SftpTransfer(
                host=self.host,
                username=self.username,
                port=self.port,
                password=self.password(),
            )
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
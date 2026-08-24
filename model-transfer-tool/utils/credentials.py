"""凭据信封 —— SecureStorage 之上的单一打包/拆包实现。

存储协议:encrypted_auth = nonce + ciphertext(nonce 12B 前缀),auth_salt
独立列保存。协议只在这里定义一次(Q1A 决策):ServerConfigDialog 的保存/
载入与 ServerProfile 的解密全部消费本模块,硬编码 nonce 长度消失。
SecureStorage 保持裸原语不动——存量行格式不变、可直接解,零迁移。
"""

from utils.crypto import SecureStorage


def pack_credential(plaintext: str) -> tuple[bytes, bytes]:
    """加密并打包成 (envelope, salt);envelope = nonce + ciphertext。"""
    ciphertext, nonce, salt = SecureStorage.encrypt(plaintext)
    return nonce + ciphertext, salt


def unpack_credential(envelope: bytes, salt: bytes) -> str:
    """拆包并解密;解密失败抛 ValueError(凭据可能被篡改或密钥不正确)。"""
    nonce = envelope[: SecureStorage.NONCE_LENGTH]
    ciphertext = envelope[SecureStorage.NONCE_LENGTH:]
    return SecureStorage.decrypt(ciphertext, nonce, salt)
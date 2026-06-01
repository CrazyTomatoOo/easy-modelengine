import os
import base64
import keyring
from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


class SecureStorage:
    """安全的凭据存储（AES-256-GCM）
    
    设计原则:
    1. 主密钥存储在系统钥匙串（Windows Credential / macOS Keychain / Linux Secret Service）
    2. 数据库中存储的是加密后的凭据 + nonce + 盐值
    3. 使用 AES-256-GCM 提供认证加密（同时保证机密性和完整性）
    4. 即使数据库文件泄露，没有系统钥匙串的主密钥也无法解密
    """
    
    SERVICE_NAME = "model-transfer-tool"
    MASTER_KEY_ID = "master_key"
    SALT_LENGTH = 16
    NONCE_LENGTH = 12
    KEY_LENGTH = 32
    ITERATIONS = 100000
    
    @classmethod
    def _get_or_create_master_key(cls) -> bytes:
        """获取或创建主密钥（256-bit）"""
        key_b64 = keyring.get_password(cls.SERVICE_NAME, cls.MASTER_KEY_ID)
        if key_b64 is None:
            key = os.urandom(cls.KEY_LENGTH)  # 256-bit
            key_b64 = base64.urlsafe_b64encode(key).decode()
            keyring.set_password(cls.SERVICE_NAME, cls.MASTER_KEY_ID, key_b64)
        return base64.urlsafe_b64decode(key_b64)
    
    @classmethod
    def _derive_key(cls, master_key: bytes, salt: bytes) -> bytes:
        """使用 PBKDF2HMAC 派生加密密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=cls.KEY_LENGTH,
            salt=salt,
            iterations=cls.ITERATIONS,
        )
        return kdf.derive(master_key)
    
    @classmethod
    def encrypt(cls, plaintext: str) -> Tuple[bytes, bytes, bytes]:
        """加密凭据，返回 (加密数据, nonce, 盐值)"""
        master_key = cls._get_or_create_master_key()
        salt = os.urandom(cls.SALT_LENGTH)
        nonce = os.urandom(cls.NONCE_LENGTH)
        
        key = cls._derive_key(master_key, salt)
        aesgcm = AESGCM(key)
        
        plaintext_bytes = plaintext.encode('utf-8')
        ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
        
        return ciphertext, nonce, salt
    
    @classmethod
    def decrypt(cls, ciphertext: bytes, nonce: bytes, salt: bytes) -> str:
        """解密凭据"""
        try:
            master_key = cls._get_or_create_master_key()
            key = cls._derive_key(master_key, salt)
            aesgcm = AESGCM(key)
            
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError("解密失败: 凭据可能已被篡改或密钥不正确") from e
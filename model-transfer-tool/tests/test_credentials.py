"""凭据信封测试——pack/unpack 单一实现:协议结构、回环、容错(fake keyring)。"""

import pytest

from utils.credentials import pack_credential, unpack_credential
from utils.crypto import SecureStorage


@pytest.fixture(autouse=True)
def _fake_keyring(monkeypatch):
    """真实 AES 往返:keyring 换成确定性假件(主密钥直接生成,不碰系统钥匙串)。"""
    import utils.crypto as crypto_mod

    class _FakeKeyring:
        """内存键存储:get 不到才生成,set 后同测试内可复用(与 test_crypto 同语义)。"""

        def __init__(self):
            self._store = {}

        def get_password(self, service, user):
            return self._store.get((service, user))

        def set_password(self, service, user, password):
            self._store[(service, user)] = password

    monkeypatch.setattr(crypto_mod, "keyring", _FakeKeyring())


class TestPackUnpack:
    def test_round_trip(self):
        envelope, salt = pack_credential("s3cret")
        assert unpack_credential(envelope, salt) == "s3cret"

    def test_envelope_is_nonce_prefixed(self):
        """存储协议:envelope = nonce(12B)+ ciphertext,与存量行格式一致。"""
        envelope, salt = pack_credential("v")
        # 协议断言:按 NONCE_LENGTH 切开可手动解开
        nonce = envelope[: SecureStorage.NONCE_LENGTH]
        ciphertext = envelope[SecureStorage.NONCE_LENGTH:]
        assert len(nonce) == 12
        assert SecureStorage.decrypt(ciphertext, nonce, salt) == "v"

    def test_each_pack_is_fresh(self):
        e1, _ = pack_credential("same")
        e2, _ = pack_credential("same")
        assert e1 != e2  # 随机 nonce/salt:同一明文两次打包不同

    def test_empty_string(self):
        envelope, salt = pack_credential("")
        assert unpack_credential(envelope, salt) == ""

    def test_unicode(self):
        value = "密码 ünïcode ✓"
        envelope, salt = pack_credential(value)
        assert unpack_credential(envelope, salt) == value

    def test_tampered_envelope_raises(self):
        envelope, salt = pack_credential("secret")
        tampered = envelope[:-1] + bytes([envelope[-1] ^ 0xFF])
        with pytest.raises(ValueError):
            unpack_credential(tampered, salt)

    def test_short_envelope_uses_nonce_length(self):
        """拆包按 NONCE_LENGTH 切分——非 12B 前缀也不越界崩溃,交给解密判定。"""
        with pytest.raises(ValueError):
            unpack_credential(b"\x00" * 5, b"\x00" * 16)
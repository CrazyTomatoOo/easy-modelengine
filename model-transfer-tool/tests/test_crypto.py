import pytest
from unittest.mock import patch, MagicMock

# Import the SecureStorage class (will fail initially)
try:
    from utils.crypto import SecureStorage
except ImportError:
    SecureStorage = None


class TestSecureStorage:
    """Tests for the SecureStorage class using AES-256-GCM."""

    def test_class_exists(self):
        """SecureStorage class should exist with required constants."""
        assert SecureStorage is not None
        if SecureStorage is not None:
            assert hasattr(SecureStorage, 'SERVICE_NAME')
            assert hasattr(SecureStorage, 'MASTER_KEY_ID')
            assert SecureStorage.SERVICE_NAME == "model-transfer-tool"
            assert SecureStorage.MASTER_KEY_ID == "master_key"

    @patch('utils.crypto.keyring')
    def test_get_or_create_master_key(self, mock_keyring):
        """Should get or create a 256-bit master key."""
        if SecureStorage is None:
            pytest.skip("SecureStorage not implemented yet")

        # Setup: no existing key
        mock_keyring.get_password.return_value = None
        mock_keyring.set_password = MagicMock()

        key = SecureStorage._get_or_create_master_key()

        assert key is not None
        assert isinstance(key, bytes)
        assert len(key) == 32  # 256 bits
        mock_keyring.set_password.assert_called_once()

    @patch('utils.crypto.keyring')
    def test_encrypt_decrypt(self, mock_keyring):
        """Encrypt then decrypt should return original plaintext."""
        if SecureStorage is None:
            pytest.skip("SecureStorage not implemented yet")

        # Setup: mock keyring to return a known key
        test_key = b'\x00' * 32
        mock_keyring.get_password.return_value = test_key.decode()

        plaintext = "my-secret-password-123"
        ciphertext, nonce, salt = SecureStorage.encrypt(plaintext)

        # Verify encrypted data is bytes
        assert isinstance(ciphertext, bytes)
        assert isinstance(nonce, bytes)
        assert isinstance(salt, bytes)
        assert len(nonce) == 12  # GCM recommended nonce size
        assert len(salt) == 16  # 16 bytes salt

        # Decrypt and verify
        decrypted = SecureStorage.decrypt(ciphertext, nonce, salt)
        assert decrypted == plaintext

    @patch('utils.crypto.keyring')
    def test_different_encryption_produces_different_ciphertext(self, mock_keyring):
        """Encrypting same plaintext twice should produce different ciphertext."""
        if SecureStorage is None:
            pytest.skip("SecureStorage not implemented yet")

        test_key = b'\x00' * 32
        mock_keyring.get_password.return_value = test_key.decode()

        plaintext = "same-secret"
        ciphertext1, nonce1, salt1 = SecureStorage.encrypt(plaintext)
        ciphertext2, nonce2, salt2 = SecureStorage.encrypt(plaintext)

        # Should produce different ciphertext, nonce, and salt
        assert ciphertext1 != ciphertext2
        assert nonce1 != nonce2
        assert salt1 != salt2

    @patch('utils.crypto.keyring')
    def test_decrypt_with_wrong_nonce(self, mock_keyring):
        """Decrypt with wrong nonce should raise exception."""
        if SecureStorage is None:
            pytest.skip("SecureStorage not implemented yet")

        test_key = b'\x00' * 32
        mock_keyring.get_password.return_value = test_key.decode()

        plaintext = "secret-data"
        ciphertext, nonce, salt = SecureStorage.encrypt(plaintext)

        # Tamper with nonce
        wrong_nonce = b'\xff' * 12

        with pytest.raises(Exception):
            SecureStorage.decrypt(ciphertext, wrong_nonce, salt)

    @patch('utils.crypto.keyring')
    def test_decrypt_with_wrong_salt(self, mock_keyring):
        """Decrypt with wrong salt should raise exception."""
        if SecureStorage is None:
            pytest.skip("SecureStorage not implemented yet")

        test_key = b'\x00' * 32
        mock_keyring.get_password.return_value = test_key.decode()

        plaintext = "secret-data"
        ciphertext, nonce, salt = SecureStorage.encrypt(plaintext)

        # Tamper with salt
        wrong_salt = b'\xff' * 16

        with pytest.raises(Exception):
            SecureStorage.decrypt(ciphertext, nonce, wrong_salt)

    @patch('utils.crypto.keyring')
    def test_decrypt_with_tampered_ciphertext(self, mock_keyring):
        """Decrypt with tampered ciphertext should raise exception."""
        if SecureStorage is None:
            pytest.skip("SecureStorage not implemented yet")

        test_key = b'\x00' * 32
        mock_keyring.get_password.return_value = test_key.decode()

        plaintext = "secret-data"
        ciphertext, nonce, salt = SecureStorage.encrypt(plaintext)

        # Tamper with ciphertext
        tampered = ciphertext[:-1] + bytes([ciphertext[-1] ^ 0xFF])

        with pytest.raises(Exception):
            SecureStorage.decrypt(tampered, nonce, salt)

    @patch('utils.crypto.keyring')
    def test_encrypt_empty_string(self, mock_keyring):
        """Should handle empty string encryption/decryption."""
        if SecureStorage is None:
            pytest.skip("SecureStorage not implemented yet")

        test_key = b'\x00' * 32
        mock_keyring.get_password.return_value = test_key.decode()

        plaintext = ""
        ciphertext, nonce, salt = SecureStorage.encrypt(plaintext)
        decrypted = SecureStorage.decrypt(ciphertext, nonce, salt)
        assert decrypted == plaintext

    @patch('utils.crypto.keyring')
    def test_encrypt_unicode(self, mock_keyring):
        """Should handle unicode characters."""
        if SecureStorage is None:
            pytest.skip("SecureStorage not implemented yet")

        test_key = b'\x00' * 32
        mock_keyring.get_password.return_value = test_key.decode()

        plaintext = "密码: p@$$w0rd! 日本語"
        ciphertext, nonce, salt = SecureStorage.encrypt(plaintext)
        decrypted = SecureStorage.decrypt(ciphertext, nonce, salt)
        assert decrypted == plaintext
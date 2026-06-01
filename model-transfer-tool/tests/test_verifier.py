import hashlib
import tempfile
from pathlib import Path

import pytest

from core.verifier import FileVerifier


class TestFileVerifier:
    def test_supported_algorithms(self):
        assert FileVerifier.SUPPORTED_ALGORITHMS == {'sha256', 'md5'}

    def test_compute_hash_sha256(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b'hello world')
            temp_path = Path(f.name)
        
        try:
            expected = hashlib.sha256(b'hello world').hexdigest()
            result = FileVerifier.compute_hash(temp_path, 'sha256')
            assert result == expected
        finally:
            temp_path.unlink()

    def test_compute_hash_md5(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b'hello world')
            temp_path = Path(f.name)
        
        try:
            expected = hashlib.md5(b'hello world').hexdigest()
            result = FileVerifier.compute_hash(temp_path, 'md5')
            assert result == expected
        finally:
            temp_path.unlink()

    def test_compute_hash_default_algorithm(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b'hello world')
            temp_path = Path(f.name)
        
        try:
            expected = hashlib.sha256(b'hello world').hexdigest()
            result = FileVerifier.compute_hash(temp_path)
            assert result == expected
        finally:
            temp_path.unlink()

    def test_compute_hash_large_file_streaming(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            data = b'a' * (8192 * 3 + 100)
            f.write(data)
            temp_path = Path(f.name)
        
        try:
            expected = hashlib.sha256(data).hexdigest()
            result = FileVerifier.compute_hash(temp_path, 'sha256')
            assert result == expected
        finally:
            temp_path.unlink()

    def test_compute_hash_unsupported_algorithm(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b'hello world')
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError, match='Unsupported algorithm'):
                FileVerifier.compute_hash(temp_path, 'sha1')
        finally:
            temp_path.unlink()

    def test_verify_correct_hash(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b'hello world')
            temp_path = Path(f.name)
        
        try:
            expected_hash = hashlib.sha256(b'hello world').hexdigest()
            assert FileVerifier.verify(temp_path, expected_hash, 'sha256') is True
        finally:
            temp_path.unlink()

    def test_verify_incorrect_hash(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b'hello world')
            temp_path = Path(f.name)
        
        try:
            assert FileVerifier.verify(temp_path, 'incorrect_hash', 'sha256') is False
        finally:
            temp_path.unlink()

    def test_verify_case_insensitive(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b'hello world')
            temp_path = Path(f.name)
        
        try:
            expected_hash = hashlib.sha256(b'hello world').hexdigest().upper()
            assert FileVerifier.verify(temp_path, expected_hash, 'sha256') is True
        finally:
            temp_path.unlink()

    def test_verify_md5(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b'hello world')
            temp_path = Path(f.name)
        
        try:
            expected_hash = hashlib.md5(b'hello world').hexdigest()
            assert FileVerifier.verify(temp_path, expected_hash, 'md5') is True
        finally:
            temp_path.unlink()

    def test_verify_unsupported_algorithm(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b'hello world')
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError, match='Unsupported algorithm'):
                FileVerifier.verify(temp_path, 'some_hash', 'sha1')
        finally:
            temp_path.unlink()

    def test_verify_nonexistent_file(self):
        nonexistent_path = Path('/tmp/nonexistent_file_for_test_12345')
        with pytest.raises(FileNotFoundError):
            FileVerifier.verify(nonexistent_path, 'some_hash', 'sha256')

    def test_compute_hash_nonexistent_file(self):
        nonexistent_path = Path('/tmp/nonexistent_file_for_test_12345')
        with pytest.raises(FileNotFoundError):
            FileVerifier.compute_hash(nonexistent_path, 'sha256')

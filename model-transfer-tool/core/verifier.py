import hashlib
from pathlib import Path


class FileVerifier:
    SUPPORTED_ALGORITHMS = {'sha256', 'md5'}
    BLOCK_SIZE = 8192

    @classmethod
    def verify(cls, file_path: Path, expected_hash: str, algorithm: str = 'sha256') -> bool:
        if algorithm not in cls.SUPPORTED_ALGORITHMS:
            raise ValueError(f'Unsupported algorithm: {algorithm}')
        
        computed_hash = cls.compute_hash(file_path, algorithm)
        return computed_hash.lower() == expected_hash.lower()

    @classmethod
    def compute_hash(cls, file_path: Path, algorithm: str = 'sha256') -> str:
        if algorithm not in cls.SUPPORTED_ALGORITHMS:
            raise ValueError(f'Unsupported algorithm: {algorithm}')
        
        if not file_path.exists():
            raise FileNotFoundError(f'File not found: {file_path}')
        
        hasher = hashlib.sha256() if algorithm == 'sha256' else hashlib.md5()
        
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(cls.BLOCK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)
        
        return hasher.hexdigest()

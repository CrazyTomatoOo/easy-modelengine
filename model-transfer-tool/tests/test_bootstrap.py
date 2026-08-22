"""bootstrap 测试——spec #23 的轻量 seam:目录创建纯函数。"""

from pathlib import Path

from core.bootstrap import ensure_dirs, APP_DIRS


class TestEnsureDirs:
    def test_creates_app_dirs(self, tmp_path):
        created = ensure_dirs(tmp_path)
        assert [p.name for p in created] == list(APP_DIRS)
        for name in APP_DIRS:
            assert (tmp_path / name).is_dir()

    def test_idempotent(self, tmp_path):
        ensure_dirs(tmp_path)
        ensure_dirs(tmp_path)  # 不抛

    def test_nested_base_created(self, tmp_path):
        base = tmp_path / "a" / "b"
        ensure_dirs(base)
        assert (base / "data").is_dir()
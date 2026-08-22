"""向导服务器下拉测试——spec 定义的 seam 3:combo 数据源 = ServerProfile.load_all。"""

import os
import tempfile

import pytest

from core.database import Database
from gui.wizard_panel import WizardPanel
from utils.crypto import SecureStorage


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    db.init_schema()
    yield db
    db.close()
    os.unlink(db_path)


def _save(db, name, host):
    db.save_server_config(
        name=name,
        host=host,
        username="ubuntu",
        auth_type="ssh_key",
        encrypted_auth=b"\x00" * (SecureStorage.NONCE_LENGTH + 4),
        auth_salt=b"\x01" * SecureStorage.SALT_LENGTH,
        port=22,
    )


class TestWizardServerCombo:
    def test_populated_from_profiles(self, qtbot, temp_db):
        _save(temp_db, "prod", "10.0.0.9")
        _save(temp_db, "staging", "10.0.0.10")

        panel = WizardPanel(database=temp_db)
        qtbot.addWidget(panel)

        items = [panel.server_combo.itemText(i) for i in range(panel.server_combo.count())]
        assert items == ["prod", "staging"]

    def test_empty_when_no_profiles(self, qtbot, temp_db):
        panel = WizardPanel(database=temp_db)
        qtbot.addWidget(panel)
        assert panel.server_combo.count() == 0

    def test_no_hardcoded_names(self, qtbot, temp_db):
        _save(temp_db, "prod", "10.0.0.9")
        panel = WizardPanel(database=temp_db)
        qtbot.addWidget(panel)
        items = [panel.server_combo.itemText(i) for i in range(panel.server_combo.count())]
        assert all("服务器" not in name for name in items)
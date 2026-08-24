"""MainWindow 接线回归——向导步骤推进、侧栏命名、任务提交异步边界。

这三个契约此前都出过真实 bug:
- next/prev 被 WizardPanel 自连后又遭 MainWindow 重复连接,一步点击推进两档(步骤1直达3);
- 侧栏第二项命名「上传任务管理」,语义应为「任务管理」;
- 提交任务时联网的 build(list_files)曾在 UI 线程同步执行,冻结界面。
"""

import threading
import time

import pytest

from PyQt6.QtCore import QThreadPool
from PyQt6.QtWidgets import QApplication

import gui.main_window as mw


_QT_APP = None


@pytest.fixture
def qapp():
    global _QT_APP
    if QApplication.instance() is None:
        _QT_APP = QApplication([])
    return QApplication.instance()


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    """构造真实 MainWindow:数据库重定向到临时文件,消息框打桩防 headless 阻塞。"""
    real_db = mw.Database

    def db_in_tmp(_path):
        return real_db(str(tmp_path / "tasks.db"))

    monkeypatch.setattr(mw, "Database", db_in_tmp)
    monkeypatch.setattr(mw.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: None)

    window = mw.MainWindow()
    yield window
    window.db.close()


def _fill_step1(panel):
    panel.model_id_input.setText("bert-base-chinese")
    panel.version_combo.setCurrentText("main")
    panel.cache_input.setText("/tmp/test-cache")


def test_wizard_next_click_advances_exactly_one_step(win):
    """回归:next 双重连接曾使一次点击推进两档(第一步直接跳到第三步)。"""
    panel = win.wizard_panel
    _fill_step1(panel)

    # 点一次进一档;三次点击应依次落在步骤 2/3/4(索引 1/2/3)
    for expected_index in (1, 2, 3):
        panel.next_btn.click()
        assert panel.current_step == expected_index
        assert panel.step_label.text() == f"步骤 {expected_index + 1}/4"

    # 步骤4再点不越界
    panel.next_btn.click()
    assert panel.current_step == 3


def test_wizard_prev_click_advances_exactly_one_step(win):
    """回归:prev 同样曾被重复连接,一次点击后退两档。"""
    panel = win.wizard_panel
    _fill_step1(panel)
    for _ in range(3):
        panel.next_btn.click()
    assert panel.current_step == 3

    panel.prev_btn.click()
    assert panel.current_step == 2


def test_nav_second_item_named_task_management(win):
    """回归:侧栏任务项应叫「任务管理」(曾叫「上传任务管理」)。"""
    assert win.nav_list.item(1).text() == "🗂️ 任务管理"


def test_task_submission_build_runs_off_ui_thread(win, monkeypatch):
    """回归:提交任务时联网的 build 必须在后台线程执行,UI 线程不得同步等待。"""
    build_threads = []
    build_done = threading.Event()

    def fake_build(draft, strategies=None):
        build_threads.append(threading.get_ident())
        time.sleep(0.2)
        build_done.set()
        return None

    monkeypatch.setattr(mw, "build", fake_build)

    draft = mw.TaskDraft(
        source="huggingface", model_id="some/model", revision="main",
        task_type_name="download_only", cache_dir="/tmp/test-cache",
    )
    win._on_task_created(draft)

    ui_thread = threading.get_ident()
    assert not build_done.is_set(), "build 在提交返回前已完成 → 同步执行"
    assert not build_threads or build_threads[0] != ui_thread, "build 跑在了 UI 线程"

    QThreadPool.globalInstance().waitForDone(5000)
    assert build_done.is_set(), "后台 worker 未在池中执行"
    assert build_threads and build_threads[0] != ui_thread, "build 未脱离 UI 线程"
#!/usr/bin/env python3
"""
GUI 主窗口模块
"""

import time
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStatusBar,
    QMessageBox, QPushButton, QDialog, QListWidget, QListWidgetItem,
    QStackedWidget,
)
from PyQt6.QtCore import Qt, QObject, QRunnable, pyqtSignal, QThreadPool, QSize
from PyQt6.QtGui import QAction

from core.database import Database
from core.proxy_config import load as load_proxy
from core.task_manager import TaskManager
from core.task_intake import TaskDraft, build, create_strategies


class TaskCreateWorker(QRunnable):
    """后台构建任务配置:build 会联网 list_files,主线程执行会冻结 UI。"""

    class _Signals(QObject):
        created = pyqtSignal(object)  # TaskConfig
        failed = pyqtSignal(str)

    def __init__(self, draft: TaskDraft, strategies):
        super().__init__()
        self.draft = draft
        self.strategies = strategies
        self.signals = self._Signals()

    def run(self):
        try:
            config = build(self.draft, strategies=self.strategies)
            self.signals.created.emit(config)
        except Exception as e:
            self.signals.failed.emit(str(e))
from gui.wizard_panel import WizardPanel
from gui.task_panel import TaskPanel
from gui.log_panel import LogPanel
from gui.theme import ThemeManager
from gui.server_config_dialog import ServerConfigDialog, ServerConfigPage
from gui.proxy_dialog import ProxyDialog
from gui.task_details_dialog import TaskDetailsDialog
from gui.state_labels import Presentation, TASK_STATE_PRESENTATION


class MainWindow(QMainWindow):
    """应用主窗口"""

    def __init__(self, app=None, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("模型下载与远程传输工具")
        self.setMinimumSize(1024, 700)
        self._progress_log_ts: dict = {}
        self._setup_backend()
        self._setup_ui()
        self._connect_signals()
        self.log_panel.append_info("应用已启动")

    def _setup_ui(self):
        # 创建中心部件
        central = QWidget()
        self.setCentralWidget(central)

        # 左侧导航 + 右侧内容栈:模型下载/任务管理/服务器管理/日志信息分列,不再平铺
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navList")
        self.nav_list.setFixedWidth(180)
        for label in ("📥 模型下载", "🗂️ 任务管理", "🖥️ 服务器管理", "📋 日志信息"):
            item = QListWidgetItem(label)
            item.setSizeHint(QSize(180, 44))
            self.nav_list.addItem(item)

        self.content_stack = QStackedWidget()
        self.wizard_panel = WizardPanel(database=self.db)
        self.task_panel = TaskPanel()
        self.server_page = ServerConfigPage(database=self.db)
        self.log_panel = LogPanel()
        for page in (self.wizard_panel, self.task_panel, self.server_page, self.log_panel):
            self.content_stack.addWidget(page)
        self.nav_list.currentRowChanged.connect(self.content_stack.setCurrentIndex)
        # 连接后再设默认行,保证内容栈与高亮一致(默认进模型下载页)
        self.nav_list.setCurrentRow(0)
        self.content_stack.setCurrentIndex(0)

        root.addWidget(self.nav_list)
        root.addWidget(self.content_stack, 1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        # 主题切换按钮
        self.theme_btn = QPushButton("🌙 深色模式")
        self.theme_btn.setCheckable(True)
        self.theme_btn.setChecked(False)
        self.theme_btn.setStyleSheet("""
            QPushButton {
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:checked {
                background-color: #2196F3;
                color: white;
            }
            QPushButton:checked:hover {
                background-color: #1976D2;
            }
        """)
        self.theme_btn.toggled.connect(self._toggle_theme)
        self.status_bar.addPermanentWidget(self.theme_btn)

        # 创建菜单栏
        self._setup_menu()

    def _setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()

        # 设置菜单
        settings_menu = menubar.addMenu("设置")

        # 服务器配置
        server_action = QAction("服务器配置", self)
        server_action.triggered.connect(self._open_server_config)
        settings_menu.addAction(server_action)

        # 代理配置
        proxy_action = QAction("代理配置", self)
        proxy_action.triggered.connect(self._open_proxy_config)
        settings_menu.addAction(proxy_action)

    def _toggle_theme(self, checked):
        """切换主题"""
        if checked:
            self.theme_btn.setText("☀️ 浅色模式")
            self.theme_manager = ThemeManager(dark_mode=True)
            self.log_panel.append_info("切换到深色模式")
        else:
            self.theme_btn.setText("🌙 深色模式")
            self.theme_manager = ThemeManager(dark_mode=False)
            self.log_panel.append_info("切换到浅色模式")
        if self.app:
            self.theme_manager.apply_theme(self.app)

    def _open_server_config(self):
        """打开服务器配置对话框"""
        self.log_panel.append_info("打开服务器配置对话框")
        dialog = ServerConfigDialog(parent=self, database=self.db)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            self.log_panel.append_success("服务器配置已保存")
        else:
            self.log_panel.append_info("服务器配置已取消")

    def _open_proxy_config(self):
        """打开代理配置对话框"""
        self.log_panel.append_info("打开代理配置对话框")
        dialog = ProxyDialog(self.db, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.get_proxy_settings()
            enable = settings.get("enable_proxy", False)
            http = settings.get("proxy_http", "")
            https = settings.get("proxy_https", "")

            self.log_panel.append_success("代理设置已保存")
            if enable:
                self.log_panel.append_info(f"代理已启用 - HTTP: {http or '未设置'}, HTTPS: {https or '未设置'}")
            else:
                self.log_panel.append_info("代理已禁用")
        else:
            self.log_panel.append_info("代理配置已取消")

    def _setup_backend(self):
        """初始化后端组件(bootstrap 已保证目录存在)"""
        db_path = Path(__file__).parent.parent / "data" / "tasks.db"

        self.db = Database(str(db_path))
        """初始化后端组件"""
        db_path = Path(__file__).parent.parent / "data" / "tasks.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db = Database(str(db_path))
        self.db.init_schema()

        self.task_manager = TaskManager(self.db)

    def _connect_signals(self):
        """连接信号槽"""
        # 向导面板按钮(WizardPanel 内部已自连 prev/next;此间只连跨组件信号)
        self.log_panel.clear_btn.clicked.connect(self.log_panel.log_edit.clear)

        # TaskManager 信号到 GUI
        self.task_manager.task_state_changed.connect(self._on_task_state_changed)
        self.task_manager.task_progress.connect(self._on_task_progress)
        self.task_manager.task_error.connect(self._on_task_error)
        self.task_manager.task_warning.connect(self._on_task_warning)
        self.task_manager.task_completed.connect(self._on_task_completed)

        # WizardPanel 任务创建信号
        self.wizard_panel.task_created.connect(self._on_task_created)
        self.wizard_panel.log_signal.connect(self._on_wizard_log)

        # TaskPanel 信号
        self.task_panel.pause_task.connect(self._on_pause_task)
        self.task_panel.resume_task.connect(self._on_resume_task)
        self.task_panel.cancel_task.connect(self._on_cancel_task)
        self.task_panel.view_details.connect(self._on_view_details)
        self.task_panel.retry_task.connect(self._on_retry_task)

        # 向导 step4 控制按钮 → TaskManager(此前是死按钮,只写日志)
        self.wizard_panel.task_control.connect(self._on_wizard_task_control)

    def _on_view_details(self, task_id: str):
        """打开任务详情对话框——文件级校验状态"""
        dialog = TaskDetailsDialog(self.db, task_id, self)
        dialog.exec()

    def _on_task_state_changed(self, task_id: str, state: str):
        """处理任务状态变化"""
        pres = TASK_STATE_PRESENTATION.get(state, Presentation(state, "#666666"))
        self.task_panel.update_task_status(task_id, state)  # key 驱动,显示查注册表
        self.log_panel.append_info(f"任务 {task_id[:8]}... 状态变更为: {pres.label}")

    def _on_task_progress(self, task_id: str, file_path: str, current: int, total: int):
        """处理任务进度更新——进度条即时刷新,日志按文件每 5 秒节流(2GB 文件
        每 chunk 一条会刷爆日志面板)。"""
        if total > 0:
            percent = int(current / total * 100)
            self.task_panel.update_task_progress(task_id, percent)

        now = time.monotonic()
        key = (task_id, file_path)
        last = self._progress_log_ts.get(key, 0)
        if now - last >= 5.0 and (total == 0 or current < total):
            self._progress_log_ts[key] = now
            if total > 0:
                message = f"任务 {task_id[:8]}… 文件 {file_path}: {percent}% ({current}/{total} bytes)"
            else:
                message = f"任务 {task_id[:8]}… 文件 {file_path}: {current} bytes"
            self.log_panel.append_log(message, "INFO")

    def _on_task_error(self, task_id: str, file_path: str, error: str):
        """处理任务错误——错误消息带下一步指引,不只复述问题。"""
        hint = ""
        lowered = error.lower()
        if any(k in lowered for k in ("connection", "timeout", "refused", "网络", "下载失败")):
            hint = " 请检查网络/代理设置后重试。"
        elif any(k in lowered for k in ("校验", "哈希", "sha256")):
            hint = " 文件损坏已被删除,重新下载即可恢复。"
        message = f"任务 {task_id[:8]}… 文件 {file_path}: {error}{hint}"
        self.log_panel.append_error(message)
        self.status_bar.showMessage(f"错误: {message}", 5000)

    def _on_task_warning(self, task_id: str, file_path: str, message: str):
        """处理任务警告"""
        self.log_panel.append_warning(f"任务 {task_id[:8]}… {file_path}: {message}")

    def _on_task_completed(self, task_id: str):
        """处理任务完成——日志与状态栏反馈,不弹模态框打断连续多任务。"""
        message = f"任务 {task_id[:8]}… 已完成"
        self.log_panel.append_success(message)
        self.status_bar.showMessage(message, 3000)

    def _on_retry_task(self, task_id: str):
        """重试失败/已取消任务(任务面板右键菜单)。"""
        self.task_manager.retry_task(task_id)

    def _on_wizard_task_control(self, action: str, task_id: str):
        """向导 step4 控制按钮 → TaskManager(此前是死按钮)。"""
        handler = {"pause": "pause", "resume": "resume", "cancel": "cancel", "retry": "retry"}.get(action)
        if handler and task_id:
            getattr(self.task_manager, f"{handler}_task")(task_id)

    def _on_task_created(self, draft: TaskDraft):
        """创建任务异步化:build 会联网 list_files,放后台避免 UI 冻结。"""
        strategies = create_strategies(load_proxy(self.db))
        worker = TaskCreateWorker(draft, strategies)
        worker.signals.created.connect(self._on_task_config_ready)
        worker.signals.failed.connect(self._on_task_create_failed)
        self.log_panel.append_info("正在获取文件列表…")
        QThreadPool.globalInstance().start(worker)

    def _on_task_config_ready(self, config):
        """文件列表就绪(主线程):建任务、入面板、登记向导当前任务。"""
        try:
            task_id = self.task_manager.create_task(config)
        except Exception as e:
            self._on_task_create_failed(str(e))
            return
        self.task_panel.add_task(task_id, config.model_id or "未知模型", task_type=config.task_type.value)
        self.wizard_panel.set_current_task(task_id)
        self.log_panel.append_success(f"任务已创建: {task_id[:8]}…")

    def _on_task_create_failed(self, error: str):
        """创建失败(主线程):如实报错并给下一步。"""
        self.log_panel.append_error(f"创建任务失败: {error}")
        QMessageBox.critical(
            self, "错误",
            f"创建任务失败:\n{error}\n请检查模型 ID、网络与代理设置后重试。",
        )

    def _on_pause_task(self, task_id: str):
        """暂停任务"""
        self.log_panel.append_info(f"暂停任务: {task_id[:8]}...")
        self.task_manager.pause_task(task_id)

    def _on_resume_task(self, task_id: str):
        """恢复任务"""
        self.log_panel.append_info(f"恢复任务: {task_id[:8]}...")
        self.task_manager.resume_task(task_id)

    def _on_cancel_task(self, task_id: str):
        """取消任务"""
        self.log_panel.append_info(f"取消任务: {task_id[:8]}...")
        self.task_manager.cancel_task(task_id)

    def _on_wizard_log(self, message: str, level: str):
        """处理向导面板的日志信号"""
        level = level.upper()
        if level == "ERROR":
            self.log_panel.append_error(message)
        elif level == "WARNING":
            self.log_panel.append_warning(message)
        elif level == "SUCCESS":
            self.log_panel.append_success(message)
        else:
            self.log_panel.append_info(message)
    def closeEvent(self, event):
        """关闭事件处理——有进行中的任务时先确认(退出会中断下载/传输)。"""
        if self.task_panel.get_active_task_count() > 0:
            reply = QMessageBox.question(
                self, "确认退出",
                "仍有进行中的任务,退出将中断它们。确认退出吗?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.log_panel.append_info("应用即将关闭")
        self.db.close()
        event.accept()

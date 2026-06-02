#!/usr/bin/env python3
"""
GUI 主窗口模块
"""

from pathlib import Path

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter, QStatusBar,
    QMessageBox, QPushButton, QDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from core.database import Database
from core.task_manager import TaskManager
from core.task_config import TaskConfig, TaskType, TaskFile
from core.interfaces import FileInfo
from core.downloaders.hf_downloader import HuggingFaceDownloader
from core.downloaders.ms_downloader import ModelScopeDownloader
from gui.wizard_panel import WizardPanel
from gui.task_panel import TaskPanel
from gui.log_panel import LogPanel
from gui.theme import ThemeManager
from gui.server_config_dialog import ServerConfigDialog
from gui.proxy_dialog import ProxyDialog


class MainWindow(QMainWindow):
    """应用主窗口"""

    def __init__(self, app=None, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("模型下载与远程传输工具")
        self.setMinimumSize(1200, 800)
        self._setup_ui()
        self._setup_backend()
        self._connect_signals()
        self.log_panel.append_info("应用已启动")

    def _setup_ui(self):
        # 创建中心部件
        central = QWidget()
        self.setCentralWidget(central)

        # 使用 QSplitter 创建三栏布局
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧面板 - WizardPanel (500px)
        self.wizard_panel = WizardPanel(database=self.db)
        self.wizard_panel = WizardPanel()
        self.wizard_panel.setMinimumWidth(300)
        splitter.addWidget(self.wizard_panel)

        # 中间面板 - TaskPanel (300px)
        self.task_panel = TaskPanel()
        self.task_panel.setMinimumWidth(200)
        splitter.addWidget(self.task_panel)

        # 右侧面板 - LogPanel (400px)
        self.log_panel = LogPanel()
        self.log_panel.setMinimumWidth(200)
        splitter.addWidget(self.log_panel)

        # 设置初始宽度
        splitter.setSizes([500, 300, 400])

        # 添加到布局
        layout = QHBoxLayout(central)
        layout.addWidget(splitter)

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
            hf_mirror = settings.get("mirror_hf", "")
            ms_mirror = settings.get("mirror_ms", "")
            
            self.log_panel.append_success("代理设置已保存")
            if enable:
                self.log_panel.append_info(f"代理已启用 - HTTP: {http or '未设置'}, HTTPS: {https or '未设置'}")
            else:
                self.log_panel.append_info("代理已禁用")
            if hf_mirror:
                self.log_panel.append_info(f"HuggingFace 镜像: {hf_mirror}")
            if ms_mirror:
                self.log_panel.append_info(f"ModelScope 镜像: {ms_mirror}")
        else:
            self.log_panel.append_info("代理配置已取消")

    def _setup_backend(self):
        """初始化后端组件"""
        db_path = Path(__file__).parent.parent / "data" / "tasks.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db = Database(str(db_path))
        self.db.init_schema()

        self.task_manager = TaskManager(self.db)

    def _connect_signals(self):
        """连接信号槽"""
        # 向导面板按钮
        self.wizard_panel.prev_btn.clicked.connect(self.wizard_panel.go_prev)
        self.wizard_panel.next_btn.clicked.connect(self.wizard_panel.go_next)
        self.log_panel.clear_btn.clicked.connect(self.log_panel.log_edit.clear)

        # TaskManager 信号到 GUI
        self.task_manager.task_state_changed.connect(self._on_task_state_changed)
        self.task_manager.task_progress.connect(self._on_task_progress)
        self.task_manager.task_error.connect(self._on_task_error)
        self.task_manager.task_completed.connect(self._on_task_completed)

        # WizardPanel 任务创建信号
        self.wizard_panel.task_created.connect(self._on_task_created)
        self.wizard_panel.log_signal.connect(self._on_wizard_log)

        # TaskPanel 信号
        self.task_panel.pause_task.connect(self._on_pause_task)
        self.task_panel.resume_task.connect(self._on_resume_task)
        self.task_panel.cancel_task.connect(self._on_cancel_task)
        self.wizard_panel.task_created.connect(self._on_task_created)

        # TaskPanel 信号
        self.task_panel.pause_task.connect(self._on_pause_task)
        self.task_panel.resume_task.connect(self._on_resume_task)
        self.task_panel.cancel_task.connect(self._on_cancel_task)

    def _on_task_state_changed(self, task_id: str, state: str):
        """处理任务状态变化"""
        state_map = {
            "pending": "等待中",
            "downloading": "下载中",
            "paused_dl": "已暂停",
            "verifying": "校验中",
            "transferring": "传输中",
            "paused_tx": "已暂停",
            "completed": "已完成",
            "failed": "失败",
            "cancelled": "已取消",
        }
        status_text = state_map.get(state, state)
        self.task_panel.update_task_status(task_id, status_text)
        self.log_panel.append_info(f"任务 {task_id[:8]}... 状态变更为: {status_text}")

    def _on_task_progress(self, task_id: str, file_path: str, current: int, total: int):
        """处理任务进度更新"""
        if total > 0:
            percent = int(current / total * 100)
            message = f"任务 {task_id[:8]}... 文件 {file_path}: {percent}% ({current}/{total} bytes)"
        else:
            message = f"任务 {task_id[:8]}... 文件 {file_path}: {current} bytes"
        self.log_panel.append_log(message, "INFO")

        # 更新任务面板进度
        if total > 0:
            percent = int(current / total * 100)
            self.task_panel.update_task_progress(task_id, percent)

    def _on_task_error(self, task_id: str, file_path: str, error: str):
        """处理任务错误"""
        message = f"任务 {task_id[:8]}... 文件 {file_path}: {error}"
        self.log_panel.append_error(message)
        self.status_bar.showMessage(f"错误: {message}", 5000)

    def _on_task_completed(self, task_id: str):
        """处理任务完成"""
        message = f"任务 {task_id[:8]}... 已完成"
        self.log_panel.append_success(message)
        self.status_bar.showMessage(message, 3000)
        QMessageBox.information(self, "任务完成", f"任务 {task_id[:8]}... 已成功完成")

    def _on_task_created(self, task_data: dict):
        """处理向导创建的任务"""
        try:
            # 转换任务类型
            task_type_map = {
                "download_only": TaskType.DOWNLOAD_ONLY,
                "download_transfer": TaskType.FULL_PIPELINE,
                "transfer_local": TaskType.TRANSFER_ONLY,
            }
            task_type = task_type_map.get(task_data.get("task_type"), TaskType.DOWNLOAD_ONLY)

            # 获取文件列表
            task_files = []
            model_source = task_data.get("source", "huggingface")
            model_id = task_data.get("model_id", "")
            revision = task_data.get("version", "main")

            self.log_panel.append_info(f"正在创建任务 - 模型: {model_id}, 版本: {revision}, 来源: {model_source}")

            if model_source == "local":
                # 本地模型 - 扫描目录
                local_path = Path(model_id)
                if local_path.exists():
                    self.log_panel.append_info(f"扫描本地模型目录: {local_path}")
                    for root, dirs, files in os.walk(local_path):
                        for file in files:
                            file_path = Path(root) / file
                            rel_path = file_path.relative_to(local_path)
                            size = file_path.stat().st_size
                            task_files.append(TaskFile(
                                file_path=str(rel_path),
                                file_size=size,
                            ))
                    self.log_panel.append_info(f"扫描到 {len(task_files)} 个本地文件")
                else:
                    self.log_panel.append_error(f"本地模型目录不存在: {local_path}")
            elif model_id and task_type != TaskType.TRANSFER_ONLY:
                try:
                    if model_source == "huggingface":
                        downloader = HuggingFaceDownloader()
                    else:
                        downloader = ModelScopeDownloader()

                    files = downloader.list_files(model_id, revision)
                    task_files = [
                        TaskFile(
                            file_path=f.path,
                            file_size=f.size,
                        )
                        for f in files
                    ]
                    self.log_panel.append_info(f"获取到 {len(files)} 个文件")
                except Exception as e:
                    self.log_panel.append_error(f"获取文件列表失败: {str(e)}")

            # 创建任务配置
            cache_dir = task_data.get("cache_dir")
            config = TaskConfig(
                task_type=task_type,
                model_source=model_source,
                model_id=model_id,
                revision=revision,
                local_cache_dir=Path(cache_dir) if cache_dir else Path("cache"),
                file_filter=task_data.get("filter") or None,
                remote_host=task_data.get("server"),
                remote_path=task_data.get("target_dir"),
                files=task_files,
            )

            # 创建任务
            task_id = self.task_manager.create_task(config)
            self.task_panel.add_task(task_id, model_id or "未知模型")
            self.log_panel.append_success(f"任务已创建: {task_id[:8]}...")

        except Exception as e:
            self.log_panel.append_error(f"创建任务失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"创建任务失败: {str(e)}")
        """处理向导创建的任务"""
        try:
            # 转换任务类型
            task_type_map = {
                "download_only": TaskType.DOWNLOAD_ONLY,
                "download_transfer": TaskType.FULL_PIPELINE,
                "transfer_local": TaskType.TRANSFER_ONLY,
            }
            task_type = task_type_map.get(task_data.get("task_type"), TaskType.DOWNLOAD_ONLY)

            # 获取文件列表
            task_files = []
            model_source = task_data.get("source", "huggingface")
            model_id = task_data.get("model_id", "")
            revision = task_data.get("version", "main")

            self.log_panel.append_info(f"正在创建任务 - 模型: {model_id}, 版本: {revision}, 来源: {model_source}")

            if model_id and task_type != TaskType.TRANSFER_ONLY:
                try:
                    if model_source == "huggingface":
                        downloader = HuggingFaceDownloader()
                    else:
                        downloader = ModelScopeDownloader()

                    files = downloader.list_files(model_id, revision)
                    task_files = [
                        TaskFile(
                            file_path=f.path,
                            file_size=f.size,
                        )
                        for f in files
                    ]
                    self.log_panel.append_info(f"获取到 {len(files)} 个文件")
                except Exception as e:
                    self.log_panel.append_error(f"获取文件列表失败: {str(e)}")

            # 创建任务配置
            cache_dir = task_data.get("cache_dir")
            config = TaskConfig(
                task_type=task_type,
                model_source=model_source,
                model_id=model_id,
                revision=revision,
                local_cache_dir=Path(cache_dir) if cache_dir else Path("cache"),
                file_filter=task_data.get("filter") or None,
                remote_host=task_data.get("server"),
                remote_path=task_data.get("target_dir"),
                files=task_files,
            )

            # 创建任务
            task_id = self.task_manager.create_task(config)
            self.task_panel.add_task(task_id, model_id or "未知模型")
            self.log_panel.append_success(f"任务已创建: {task_id[:8]}...")

        except Exception as e:
            self.log_panel.append_error(f"创建任务失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"创建任务失败: {str(e)}")

    def _on_pause_task(self, task_id: str):
        """暂停任务"""
        self.log_panel.append_info(f"暂停任务: {task_id[:8]}...")

    def _on_resume_task(self, task_id: str):
        """恢复任务"""
        self.log_panel.append_info(f"恢复任务: {task_id[:8]}...")

    def _on_cancel_task(self, task_id: str):
        """取消任务"""
        self.log_panel.append_info(f"取消任务: {task_id[:8]}...")

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
        """关闭事件处理"""
        self.log_panel.append_info("应用即将关闭")
        self.db.close()
        event.accept()

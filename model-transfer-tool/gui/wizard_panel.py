#!/usr/bin/env python3
"""
向导面板模块 - 4步模型下载向导
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QPushButton, QRadioButton, QLineEdit, QComboBox,
    QGroupBox, QFormLayout, QCheckBox, QTreeWidget, QTreeWidgetItem,
    QProgressBar, QListWidget, QListWidgetItem, QTextEdit,
    QButtonGroup, QFileDialog, QMessageBox, QSplitter,
    QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool, QRunnable, QObject
import shutil
import os
from pathlib import Path
from PyQt6.QtGui import QFont

from core.server_profile import load_all
from core.task_intake import TaskDraft, validate, DraftValidationError, resolve_strategy


class VersionFetchWorker(QRunnable):
    """后台获取版本列表的 Worker——经信号回 UI 线程,不直接碰界面。"""

    class _Signals(QObject):
        fetched = pyqtSignal(list, int)  # versions, file_count
        failed = pyqtSignal(str)

    def __init__(self, model_id: str, is_hf: bool):
        super().__init__()
        self.model_id = model_id
        self.is_hf = is_hf
        self.signals = self._Signals()

    def run(self):
        try:
            source = "huggingface" if self.is_hf else "modelscope"
            downloader = resolve_strategy(source)
            files = downloader.list_files(self.model_id, "main")

            # 真实分支/标签(HF 专用 API;其他源降级为主分支)
            versions = ["main"]
            if self.is_hf:
                try:
                    from huggingface_hub import HfApi

                    refs = HfApi().list_repo_refs(self.model_id)
                    versions = [b.name for b in refs.branches] + [t.name for t in refs.tags]
                    if not versions:
                        versions = ["main"]
                    elif "main" not in versions:
                        versions.insert(0, "main")
                except Exception:
                    pass  # refs 不可用(私有/限流)时以 main 兜底,文件列表已足够

            self.signals.fetched.emit(versions, len(files))
        except Exception as e:
            self.signals.failed.emit(str(e))


class WizardPanel(QWidget):
    """4步向导面板"""

    task_created = pyqtSignal(object)  # TaskDraft
    log_signal = pyqtSignal(str, str)  # message, level
    task_control = pyqtSignal(str, str)  # action(pause|resume|cancel|retry), task_id

    def __init__(self, parent=None, database=None):
        super().__init__(parent)
        self.db = database
        self.current_step = 0
        self._current_task_id: str = None
        self._setup_ui()
        self._connect_signals()
        self._load_server_profiles()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 步骤指示器
        self.step_label = QLabel("步骤 1/4")
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.step_label.setFont(font)
        layout.addWidget(self.step_label)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #ccc;")
        line.setFixedHeight(1)
        layout.addWidget(line)

        # QStackedWidget 用于切换步骤
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # 创建4个步骤页面
        self._setup_step1()
        self._setup_step2()
        self._setup_step3()
        self._setup_step4()

        # 按钮区域
        btn_layout = QHBoxLayout()
        self.prev_btn = QPushButton("上一步")
        self.next_btn = QPushButton("下一步")
        self.finish_btn = QPushButton("完成")
        self.finish_btn.hide()

        btn_layout.addWidget(self.prev_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.next_btn)
        btn_layout.addWidget(self.finish_btn)
        layout.addLayout(btn_layout)

        self._update_ui()

    def _setup_step1(self):
        """Step 1: 选择模型"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        # 标题
        title = QLabel("选择模型")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # 模型源选择
        source_group = QGroupBox("模型来源")
        source_layout = QHBoxLayout(source_group)
        self.hf_radio = QRadioButton("HuggingFace")
        self.ms_radio = QRadioButton("ModelScope")
        self.local_radio = QRadioButton("本地模型")
        self.hf_radio.setChecked(True)
        self.source_btn_group = QButtonGroup(self)
        self.source_btn_group.addButton(self.hf_radio, 0)
        self.source_btn_group.addButton(self.ms_radio, 1)
        self.source_btn_group.addButton(self.local_radio, 2)
        source_layout.addWidget(self.hf_radio)
        source_layout.addWidget(self.ms_radio)
        source_layout.addWidget(self.local_radio)
        source_layout.addStretch()
        layout.addWidget(source_group)

        # 远程模型输入区域
        self.remote_model_widget = QWidget()
        remote_layout = QVBoxLayout(self.remote_model_widget)
        remote_layout.setContentsMargins(0, 0, 12, 0)

        # 模型 ID
        model_layout = QFormLayout()
        model_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)  # macOS 默认标签右对齐,统一钉死左对齐
        self.model_id_input = QLineEdit()
        self.model_id_input.setPlaceholderText("bert-base-chinese")
        self.model_id_input.setMinimumWidth(160)
        model_layout.addRow("模型 ID:", self.model_id_input)
        remote_layout.addLayout(model_layout)

        # 版本选择 + 获取按钮（水平布局）——并入 model_layout 同一 QFormLayout:
        # 标签列与「模型 ID:」严格同列对齐(独立 HBox 会让标签起点错位 ~146px)
        version_row = QHBoxLayout()
        version_row.setSpacing(8)

        self.version_combo = QComboBox()
        self.version_combo.setEditable(True)
        self.version_combo.setPlaceholderText("输入或选择版本")
        self.version_combo.addItems(["main", "master", "latest"])
        self.version_combo.setCurrentText("main")
        version_row.addWidget(self.version_combo, stretch=1)

        self.fetch_version_btn = QPushButton("获取")
        self.fetch_version_btn.setMinimumWidth(64)
        self.fetch_version_btn.setToolTip("获取远程仓库的版本/分支列表")
        self.fetch_version_btn.clicked.connect(self._fetch_versions)
        version_row.addWidget(self.fetch_version_btn)

        model_layout.addRow("版本/分支:", version_row)

        # 文件过滤(并入同一 form,三行标签严格同列)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("*.bin, *.safetensors")
        self.filter_input.setMinimumWidth(160)
        model_layout.addRow("文件过滤:", self.filter_input)

        layout.addWidget(self.remote_model_widget)

        # 本地模型输入区域（默认隐藏）
        self.local_model_widget = QWidget()
        local_model_layout = QHBoxLayout(self.local_model_widget)
        local_model_layout.setContentsMargins(0, 0, 0, 0)

        self.local_path_input = QLineEdit()
        self.local_path_input.setPlaceholderText("选择本地模型目录")
        self.local_path_input.setReadOnly(True)
        self.local_browse_btn = QPushButton("浏览…")
        self.local_browse_btn.clicked.connect(self._browse_local_model)
        local_model_layout.addWidget(QLabel("本地路径:"))
        local_model_layout.addWidget(self.local_path_input, stretch=1)
        local_model_layout.addWidget(self.local_browse_btn)

        self.local_model_widget.hide()
        layout.addWidget(self.local_model_widget)

        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        self.stack.addWidget(scroll)

    def _setup_step2(self):
        """Step 2: 配置参数"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        # 标题
        title = QLabel("配置参数")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # 任务类型
        task_group = QGroupBox("任务类型")
        task_layout = QVBoxLayout(task_group)
        self.task_group_btn = QButtonGroup(self)

        self.download_only_radio = QRadioButton("仅下载到本地")
        self.download_transfer_radio = QRadioButton("下载并传输到服务器")
        self.transfer_local_radio = QRadioButton("仅传输本地已有文件")
        self.download_only_radio.setChecked(True)

        # 添加禁用时的样式
        disabled_style = """
            QRadioButton:disabled {
                color: #999999;
            }
        """
        self.download_only_radio.setStyleSheet(disabled_style)
        self.download_transfer_radio.setStyleSheet(disabled_style)
        self.transfer_local_radio.setStyleSheet(disabled_style)

        self.task_group_btn.addButton(self.download_only_radio, 0)
        self.task_group_btn.addButton(self.download_transfer_radio, 1)
        self.task_group_btn.addButton(self.transfer_local_radio, 2)

        task_layout.addWidget(self.download_only_radio)
        task_layout.addWidget(self.download_transfer_radio)
        task_layout.addWidget(self.transfer_local_radio)
        layout.addWidget(task_group)

        # 本地缓存目录
        self.cache_widget = QWidget()
        cache_layout = QHBoxLayout(self.cache_widget)
        cache_layout.setContentsMargins(0, 0, 0, 0)
        self.cache_input = QLineEdit()
        self.cache_input.setPlaceholderText("本地缓存目录路径")
        self.cache_btn = QPushButton("浏览…")
        cache_layout.addWidget(QLabel("本地缓存:"))
        cache_layout.addWidget(self.cache_input)
        cache_layout.addWidget(self.cache_btn)
        layout.addWidget(self.cache_widget)

        # 传输设置（仅当选择传输时显示）
        self.transfer_group = QGroupBox("传输设置")
        self.transfer_group.setVisible(False)
        transfer_layout = QFormLayout(self.transfer_group)

        self.server_combo = QComboBox()
        self.server_combo.setEditable(True)
        self.server_combo.setPlaceholderText("选择已保存的服务器")
        transfer_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        transfer_layout.addRow("目标服务器:", self.server_combo)

        self.target_dir_input = QLineEdit()
        self.target_dir_input.setPlaceholderText("目标服务器上的目录路径")
        self.target_dir_input.setMinimumWidth(160)
        transfer_layout.addRow("目标目录:", self.target_dir_input)

        layout.addWidget(self.transfer_group)

        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        self.stack.addWidget(scroll)

    def _setup_step3(self):
        """Step 3: 确认信息"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        # 标题
        title = QLabel("确认信息")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # 信息摘要
        summary_group = QGroupBox("任务摘要")
        summary_layout = QFormLayout(summary_group)

        self.summary_source = QLabel("-")
        self.summary_model = QLabel("-")
        self.summary_version = QLabel("-")
        self.summary_task = QLabel("-")
        self.summary_target = QLabel("-")
        self.summary_files = QLabel("-")

        summary_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        summary_layout.addRow("模型来源:", self.summary_source)
        summary_layout.addRow("模型 ID:", self.summary_model)
        summary_layout.addRow("版本:", self.summary_version)
        summary_layout.addRow("任务类型:", self.summary_task)
        summary_layout.addRow("目标位置:", self.summary_target)
        summary_layout.addRow("文件数量:", self.summary_files)

        layout.addWidget(summary_group)

        # 文件列表预览
        files_group = QGroupBox("文件列表")
        files_layout = QVBoxLayout(files_group)

        self.files_tree = QTreeWidget()
        self.files_tree.setHeaderLabels(["文件名", "大小", "状态"])
        self.files_tree.setColumnWidth(0, 200)
        self.files_tree.setColumnWidth(1, 100)
        files_layout.addWidget(self.files_tree)

        layout.addWidget(files_group)

        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        self.stack.addWidget(scroll)

    def _setup_step4(self):
        """Step 4: 执行进度"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        # 标题
        title = QLabel("执行进度")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # 总体进度
        progress_group = QGroupBox("总体进度")
        progress_layout = QVBoxLayout(progress_group)

        self.total_progress = QProgressBar()
        self.total_progress.setRange(0, 100)
        self.total_progress.setValue(0)
        progress_layout.addWidget(self.total_progress)

        # 速度和预计时间
        info_layout = QHBoxLayout()
        self.speed_label = QLabel("速度: -")
        self.eta_label = QLabel("预计剩余时间: -")
        info_layout.addWidget(self.speed_label)
        info_layout.addStretch()
        info_layout.addWidget(self.eta_label)
        progress_layout.addLayout(info_layout)

        layout.addWidget(progress_group)

        # 状态列表
        status_group = QGroupBox("执行状态")
        status_layout = QVBoxLayout(status_group)

        self.status_list = QListWidget()
        status_layout.addWidget(self.status_list)

        layout.addWidget(status_group)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.pause_btn = QPushButton("暂停")
        self.resume_btn = QPushButton("恢复")
        self.resume_btn.setEnabled(False)
        self.cancel_btn = QPushButton("取消")
        self.retry_btn = QPushButton("重试")
        self.retry_btn.hide()
        self.export_btn = QPushButton("导出日志")
        self.export_btn.hide()

        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.resume_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.retry_btn)
        btn_layout.addWidget(self.export_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        self.stack.addWidget(scroll)

    def _connect_signals(self):
        """连接信号"""
        self.prev_btn.clicked.connect(self.go_prev)
        self.next_btn.clicked.connect(self.go_next)
        self.finish_btn.clicked.connect(self._on_finish)

        self.hf_radio.toggled.connect(self._on_source_changed)
        self.ms_radio.toggled.connect(self._on_source_changed)
        self.local_radio.toggled.connect(self._on_source_changed)

        self.cache_btn.clicked.connect(self._browse_cache_dir)
        self.download_transfer_radio.toggled.connect(self._on_task_type_changed)
        self.transfer_local_radio.toggled.connect(self._on_task_type_changed)

        self.pause_btn.clicked.connect(self._on_pause)
        self.resume_btn.clicked.connect(self._on_resume)
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.retry_btn.clicked.connect(self._on_retry)
        self.export_btn.clicked.connect(self._on_export)

    def _load_server_profiles(self):
        """从数据库加载 Server profiles 填充服务器下拉"""
        names = []
        if self.db:
            try:
                names = [p.name for p in load_all(self.db)]
            except Exception as e:
                self.log_signal.emit(f"加载服务器配置失败: {str(e)}", "WARNING")
        self._server_profile_names = names
        self.server_combo.clear()
        self.server_combo.addItems(names)

    def _load_settings(self):
        """从数据库加载设置"""
        if not self.db:
            return

        try:
            # 加载模型来源
            source = self.db.get_setting("wizard_source", "huggingface")
            if source == "modelscope":
                self.ms_radio.setChecked(True)
            elif source == "local":
                self.local_radio.setChecked(True)
            else:
                self.hf_radio.setChecked(True)

            # 加载缓存目录
            cache_dir = self.db.get_setting("wizard_cache_dir", "")
            if cache_dir:
                self.cache_input.setText(cache_dir)

            # 加载服务器选择(仅当该服务器仍是已保存的 profile)
            server = self.db.get_setting("wizard_server", "")
            if server and server in getattr(self, "_server_profile_names", []):
                self.server_combo.setCurrentText(server)

            # 加载目标目录
            target_dir = self.db.get_setting("wizard_target_dir", "")
            if target_dir:
                self.target_dir_input.setText(target_dir)

            # 加载本地模型路径
            local_path = self.db.get_setting("wizard_local_path", "")
            if local_path:
                self.local_path_input.setText(local_path)
        except Exception as e:
            self.log_signal.emit(f"加载设置失败: {str(e)}", "WARNING")

    def _save_settings(self):
        """保存设置到数据库"""
        if not self.db:
            return

        try:
            # 保存模型来源
            if self.hf_radio.isChecked():
                source = "huggingface"
            elif self.ms_radio.isChecked():
                source = "modelscope"
            else:
                source = "local"
            self.db.set_setting("wizard_source", source)

            # 保存缓存目录
            self.db.set_setting("wizard_cache_dir", self.cache_input.text())

            # 保存服务器选择
            self.db.set_setting("wizard_server", self.server_combo.currentText())

            # 保存目标目录
            self.db.set_setting("wizard_target_dir", self.target_dir_input.text())

            # 保存本地模型路径
            self.db.set_setting("wizard_local_path", self.local_path_input.text())
        except Exception as e:
            self.log_signal.emit(f"保存设置失败: {str(e)}", "WARNING")

    def _on_source_changed(self):
        """模型来源切换"""
        is_local = self.local_radio.isChecked()
        self.remote_model_widget.setVisible(not is_local)
        self.local_model_widget.setVisible(is_local)

        if is_local:
            self.log_signal.emit("切换到本地模型模式", "INFO")
            # 自动选择传输任务
            self.transfer_local_radio.setChecked(True)
            # 禁用其他任务类型
            self.download_only_radio.setEnabled(False)
            self.download_transfer_radio.setEnabled(False)
        else:
            source = "HuggingFace" if self.hf_radio.isChecked() else "ModelScope"
            self.log_signal.emit(f"切换到远程模型模式: {source}", "INFO")
            # 启用所有任务类型
            self.download_only_radio.setEnabled(True)
            self.download_transfer_radio.setEnabled(True)

        # 保存设置
        self._save_settings()

    def _on_task_type_changed(self):
        """任务类型改变"""
        show_transfer = self.download_transfer_radio.isChecked() or self.transfer_local_radio.isChecked()
        self.transfer_group.setVisible(show_transfer)

        # 仅传输本地文件时，不需要缓存目录
        show_cache = not self.transfer_local_radio.isChecked()
        self.cache_widget.setVisible(show_cache)

    def _browse_cache_dir(self):
        """浏览缓存目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择缓存目录")
        if dir_path:
            self.cache_input.setText(dir_path)
            self._save_settings()

    def _browse_local_model(self):
        """浏览本地模型目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择本地模型目录")
        if dir_path:
            self.local_path_input.setText(dir_path)
            self.log_signal.emit(f"已选择本地模型目录: {dir_path}", "INFO")
            # 扫描目录中的文件
            self._scan_local_files(dir_path)
            self._save_settings()

    def _scan_local_files(self, dir_path):
        """扫描本地模型目录中的文件"""
        try:
            self.files_tree.clear()
            file_count = 0
            total_size = 0

            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, dir_path)
                    size = os.path.getsize(file_path)
                    total_size += size
                    size_str = self._format_size(size)
                    item = QTreeWidgetItem([rel_path, size_str, "待传输"])
                    self.files_tree.addTopLevelItem(item)
                    file_count += 1

            self.log_signal.emit(f"扫描到 {file_count} 个文件, 总大小: {self._format_size(total_size)}", "INFO")
        except Exception as e:
            self.log_signal.emit(f"扫描本地文件失败: {str(e)}", "ERROR")

    def _update_ui(self):
        """更新UI状态"""
        self.step_label.setText(f"步骤 {self.current_step + 1}/4")
        self.stack.setCurrentIndex(self.current_step)

        # 更新按钮状态
        self.prev_btn.setEnabled(self.current_step > 0)
        self.next_btn.setVisible(self.current_step < 3)
        self.finish_btn.setVisible(self.current_step == 3)

        # 更新摘要信息
        if self.current_step == 2:
            self._update_summary()

    def _update_summary(self):
        """更新任务摘要"""
        if self.local_radio.isChecked():
            self.summary_source.setText("本地模型")
            self.summary_model.setText(self.local_path_input.text() or "-")
            self.summary_version.setText("-")
        elif self.hf_radio.isChecked():
            self.summary_source.setText("HuggingFace")
            self.summary_model.setText(self.model_id_input.text() or "-")
            self.summary_version.setText(self.version_combo.currentText())
        else:
            self.summary_source.setText("ModelScope")
            self.summary_model.setText(self.model_id_input.text() or "-")
            self.summary_version.setText(self.version_combo.currentText())

        # 任务类型
        task_id = self.task_group_btn.checkedId()
        if task_id == 0:
            self.summary_task.setText("仅下载到本地")
            self.summary_target.setText(self.cache_input.text() or "-")
        elif task_id == 1:
            self.summary_task.setText("下载并传输到服务器")
            self.summary_target.setText(
                f"{self.server_combo.currentText()}:{self.target_dir_input.text() or '-'}"
            )
        else:
            self.summary_task.setText("仅传输本地已有文件")
            self.summary_target.setText(
                f"{self.server_combo.currentText()}:{self.target_dir_input.text() or '-'}"
            )

        # 更新存储空间提示（实际检查）
        self._check_storage_space()

    def _fetch_versions(self):
        """获取版本列表（异步）"""
        model_id = self.model_id_input.text().strip()
        if not model_id:
            QMessageBox.warning(self, "警告", "请先输入模型ID")
            return

        self.fetch_version_btn.setEnabled(False)
        self.fetch_version_btn.setText("…")
        self.version_combo.clear()
        self.version_combo.setPlaceholderText("获取中…")

        self.log_signal.emit(f"正在获取模型 {model_id} 的版本列表…", "INFO")

        worker = VersionFetchWorker(model_id, self.hf_radio.isChecked())
        worker.signals.fetched.connect(self._on_versions_fetched)
        worker.signals.failed.connect(self._on_versions_fetch_error)
        QThreadPool.globalInstance().start(worker)

    def _on_versions_fetched(self, versions, file_count):
        """版本列表获取成功的回调（在主线程执行）"""
        self.version_combo.clear()
        self.version_combo.addItems(versions)
        self.version_combo.setCurrentText("main")
        self.fetch_version_btn.setEnabled(True)
        self.fetch_version_btn.setText("获取")
        self.log_signal.emit(f"成功获取版本列表，找到 {file_count} 个文件", "SUCCESS")

    def _on_versions_fetch_error(self, error_msg):
        """获取失败:如实报错,保留原有版本选择,不伪装成功。"""
        self.fetch_version_btn.setEnabled(True)
        self.fetch_version_btn.setText("获取")
        self.log_signal.emit(f"获取版本列表失败: {error_msg}", "ERROR")
        QMessageBox.warning(
            self, "获取失败",
            f"无法获取版本列表:\n{error_msg}\n可手动输入版本/分支。",
        )

    def _format_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(size_bytes) < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

    def _check_storage_space(self):
        """检查缓存目录可用空间——仅本地模式(files_tree 有真实清单)时评估。

        远程任务未取文件清单,无法计算准确所需空间,虚报比不报更糟。
        """
        if self.files_tree.topLevelItemCount() == 0:
            return

        cache_dir = self.cache_input.text().strip()
        if not cache_dir:
            cache_dir = str(Path.home() / ".cache" / "model-transfer")

        try:
            _total, _used, free = shutil.disk_usage(cache_dir)
            required = sum(
                self._parse_size(self.files_tree.topLevelItem(i).text(1))
                for i in range(self.files_tree.topLevelItemCount())
            )
            free_gb = free / (1024**3)
            required_gb = required / (1024**3)

            if required_gb > 0 and free_gb < required_gb:
                self.log_signal.emit(
                    f"存储空间不足: 需要 {required_gb:.1f} GB, 可用 {free_gb:.1f} GB",
                    "WARNING"
                )
        except OSError as e:
            self.log_signal.emit(f"存储空间检查失败: {e}", "WARNING")

    def _parse_size(self, size_str):
        """解析大小字符串为字节数"""
        try:
            parts = size_str.split()
            if len(parts) != 2:
                return 0
            value = float(parts[0])
            unit = parts[1].upper()
            multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
            return value * multipliers.get(unit, 1)
        except Exception:
            return 0

    def _on_finish(self):
        """完成按钮点击——先同步校验,通过才发射并重置"""
        draft = self._build_draft()
        try:
            validate(draft)
        except DraftValidationError as e:
            self.log_signal.emit(f"创建任务失败: {str(e)}", "ERROR")
            QMessageBox.warning(self, "无法创建任务", str(e))
            return

        self.task_created.emit(draft)
        self.log_signal.emit("任务已提交", "SUCCESS")

        # 重置向导
        self.reset()

    def _build_draft(self):
        """收集向导各步骤的原始选择,构造 TaskDraft(CONTEXT.md:TaskDraft 原始快照)"""
        task_id = self.task_group_btn.checkedId()
        task_type_name = ["download_only", "download_transfer", "transfer_local"][task_id]

        if self.local_radio.isChecked():
            return TaskDraft(
                source="local",
                model_id=self.local_path_input.text(),
                revision="local",
                task_type_name=task_type_name,
                cache_dir=self.local_path_input.text(),
                file_filter=self.filter_input.text(),
                server=self.server_combo.currentText() if task_id in [1, 2] else None,
                target_dir=self.target_dir_input.text() if task_id in [1, 2] else None,
            )

        return TaskDraft(
            source="huggingface" if self.hf_radio.isChecked() else "modelscope",
            model_id=self.model_id_input.text(),
            revision=self.version_combo.currentText(),
            task_type_name=task_type_name,
            cache_dir=self.cache_input.text(),
            file_filter=self.filter_input.text(),
            server=self.server_combo.currentText() if task_id in [1, 2] else None,
            target_dir=self.target_dir_input.text() if task_id in [1, 2] else None,
        )

    def set_current_task(self, task_id: str) -> None:
        """记录向导当前操作的任务(由 MainWindow 在创建后注入)。"""
        self._current_task_id = task_id
        self.pause_btn.setEnabled(task_id is not None)
        self.cancel_btn.setEnabled(task_id is not None)

    def _on_pause(self):
        """暂停——提交 TaskManager 执行,按钮反馈避免重复点击。"""
        if self._current_task_id:
            self.task_control.emit("pause", self._current_task_id)
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(True)
        self.log_signal.emit("已请求暂停", "INFO")

    def _on_resume(self):
        """恢复"""
        if self._current_task_id:
            self.task_control.emit("resume", self._current_task_id)
            self.pause_btn.setEnabled(True)
            self.resume_btn.setEnabled(False)
        self.log_signal.emit("已请求恢复", "INFO")

    def _on_cancel(self):
        """取消——破坏性操作,确认后提交 TaskManager(任务仍保留在面板)。"""
        if not self._current_task_id:
            return
        reply = QMessageBox.question(
            self, "确认取消", "确定要取消当前任务吗?已下载的部分会保留。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.task_control.emit("cancel", self._current_task_id)
            self.log_signal.emit("已请求取消", "WARNING")

    def _on_retry(self):
        """重试失败项"""
        if self._current_task_id:
            self.task_control.emit("retry", self._current_task_id)
        self.log_signal.emit("已请求重试", "INFO")

    def _on_export(self):
        """导出日志"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", "task_log.txt", "文本文件 (*.txt)"
        )
        if file_path:
            self.log_signal.emit(f"日志已导出到: {file_path}", "SUCCESS")

    def go_next(self):
        """下一步"""
        if self.current_step == 0:
            # Step 1 验证
            if self.local_radio.isChecked():
                local_path = self.local_path_input.text().strip()
                if not local_path:
                    QMessageBox.warning(self, "警告", "请选择本地模型目录")
                    return
                if not os.path.exists(local_path):
                    QMessageBox.warning(self, "警告", "所选目录不存在")
                    return
                self.log_signal.emit(f"步骤1完成 - 本地模型: {local_path}", "INFO")
            else:
                model_id = self.model_id_input.text().strip()
                if not model_id:
                    QMessageBox.warning(self, "警告", "请输入模型ID")
                    return

                version = self.version_combo.currentText().strip()
                if not version:
                    QMessageBox.warning(self, "警告", "请输入或选择版本/分支")
                    return

                self.log_signal.emit(f"步骤1完成 - 模型: {model_id}, 版本: {version}", "INFO")

        elif self.current_step == 1:
            # Step 2 验证
            task_id = self.task_group_btn.checkedId()
            cache_dir = self.cache_input.text().strip()

            if not self.transfer_local_radio.isChecked():
                if not cache_dir:
                    QMessageBox.warning(self, "警告", "请设置本地缓存目录")
                    return

            if task_id in [1, 2]:  # 需要传输
                target_dir = self.target_dir_input.text().strip()
                if not target_dir:
                    QMessageBox.warning(self, "警告", "请输入目标目录")
                    return

            self.log_signal.emit("步骤2完成 - 参数配置完成", "INFO")

        elif self.current_step == 2:
            # Step 3 确认
            self.log_signal.emit("步骤3完成 - 任务确认", "INFO")

        if self.current_step < 3:
            self.current_step += 1
            self._update_ui()

    def go_prev(self):
        """上一步"""
        if self.current_step > 0:
            self.current_step -= 1
            self._update_ui()
            self.log_signal.emit(f"返回到步骤 {self.current_step + 1}", "INFO")

    def reset(self):
        """重置向导"""
        self.current_step = 0
        self.model_id_input.clear()
        self.version_combo.setCurrentText("main")
        self.local_path_input.clear()
        self.filter_input.clear()
        self.hf_radio.setChecked(True)
        self.download_only_radio.setChecked(True)
        self.cache_input.clear()
        self.server_combo.setCurrentIndex(0)
        self.target_dir_input.clear()
        self.total_progress.setValue(0)
        self.speed_label.setText("速度: -")
        self.eta_label.setText("预计剩余时间: -")
        self.status_list.clear()
        self.files_tree.clear()
        self._update_ui()
        self.log_signal.emit("向导已重置", "INFO")

    def update_progress(self, progress, speed="", eta=""):
        """更新进度"""
        self.total_progress.setValue(progress)
        if speed:
            self.speed_label.setText(f"速度: {speed}")
        if eta:
            self.eta_label.setText(f"预计剩余时间: {eta}")

    def add_status_item(self, message, item_type="info"):
        """添加状态项"""
        item = QListWidgetItem(message)
        if item_type == "error":
            item.setForeground(Qt.GlobalColor.red)
        elif item_type == "success":
            item.setForeground(Qt.GlobalColor.green)
        self.status_list.addItem(item)

    def set_completed(self, success=True):
        """设置完成状态"""
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)

        if success:
            self.total_progress.setValue(100)
            self.add_status_item("任务完成！", "success")
            self.log_signal.emit("任务执行完成", "SUCCESS")

        self.retry_btn.show()
        self.export_btn.show()
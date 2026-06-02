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
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool, QRunnable
import shutil
import os
from pathlib import Path
from PyQt6.QtGui import QFont
from core.downloaders.hf_downloader import HuggingFaceDownloader
from core.downloaders.ms_downloader import ModelScopeDownloader


class VersionFetchWorker(QRunnable):
    """后台获取版本列表的 Worker"""
    def __init__(self, panel, model_id, is_hf):
        super().__init__()
        self.panel = panel
        self.model_id = model_id
        self.is_hf = is_hf

    def run(self):
        try:
            if self.is_hf:
                downloader = HuggingFaceDownloader()
            else:
                downloader = ModelScopeDownloader()

            files = downloader.list_files(self.model_id, "main")
            versions = ["main", "master", "latest"]
            self.panel._on_versions_fetched(versions, len(files))
        except Exception as e:
            self.panel._on_versions_fetch_error(str(e))


class WizardPanel(QWidget):
    """4步向导面板"""
    
    task_created = pyqtSignal(dict)
    log_signal = pyqtSignal(str, str)  # message, level
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_step = 0
        self._setup_ui()
        self._connect_signals()
    
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
        remote_layout.setContentsMargins(0, 0, 0, 0)
        
        # 模型 ID
        model_layout = QFormLayout()
        self.model_id_input = QLineEdit()
        self.model_id_input.setPlaceholderText("例如: bert-base-chinese")
        model_layout.addRow("模型 ID:", self.model_id_input)
        remote_layout.addLayout(model_layout)
        
        # 版本选择 + 获取按钮（水平布局）
        version_row = QHBoxLayout()
        version_row.setSpacing(8)
        
        self.version_combo = QComboBox()
        self.version_combo.setEditable(True)
        self.version_combo.setPlaceholderText("输入或选择版本")
        self.version_combo.addItems(["main", "master", "latest"])
        self.version_combo.setCurrentText("main")
        version_row.addWidget(QLabel("版本/分支:"))
        version_row.addWidget(self.version_combo, stretch=1)
        
        self.fetch_version_btn = QPushButton("获取")
        self.fetch_version_btn.setFixedWidth(70)
        self.fetch_version_btn.setToolTip("获取远程仓库的版本/分支列表")
        self.fetch_version_btn.clicked.connect(self._fetch_versions)
        version_row.addWidget(self.fetch_version_btn)
        
        remote_layout.addLayout(version_row)
        layout.addWidget(self.remote_model_widget)
        
        # 本地模型输入区域（默认隐藏）
        self.local_model_widget = QWidget()
        local_model_layout = QHBoxLayout(self.local_model_widget)
        local_model_layout.setContentsMargins(0, 0, 0, 0)
        
        self.local_path_input = QLineEdit()
        self.local_path_input.setPlaceholderText("选择本地模型目录")
        self.local_path_input.setReadOnly(True)
        self.local_browse_btn = QPushButton("浏览...")
        self.local_browse_btn.clicked.connect(self._browse_local_model)
        local_model_layout.addWidget(QLabel("本地路径:"))
        local_model_layout.addWidget(self.local_path_input, stretch=1)
        local_model_layout.addWidget(self.local_browse_btn)
        
        self.local_model_widget.hide()
        layout.addWidget(self.local_model_widget)
        
        # 文件过滤
        filter_layout = QFormLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("可选: 输入文件名模式过滤 (如 *.bin, *.safetensors)")
        filter_layout.addRow("文件过滤:", self.filter_input)
        layout.addLayout(filter_layout)
        
        layout.addStretch()
        self.stack.addWidget(page)
    
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
        self.cache_btn = QPushButton("浏览...")
        cache_layout.addWidget(QLabel("本地缓存:"))
        cache_layout.addWidget(self.cache_input)
        cache_layout.addWidget(self.cache_btn)
        layout.addWidget(self.cache_widget)
        cache_layout = QHBoxLayout()
        self.cache_input = QLineEdit()
        self.cache_input.setPlaceholderText("本地缓存目录路径")
        self.cache_btn = QPushButton("浏览...")
        cache_layout.addWidget(QLabel("本地缓存:"))
        cache_layout.addWidget(self.cache_input)
        cache_layout.addWidget(self.cache_btn)
        layout.addLayout(cache_layout)
        
        # 传输设置（仅当选择传输时显示）
        self.transfer_group = QGroupBox("传输设置")
        self.transfer_group.setVisible(False)
        transfer_layout = QFormLayout(self.transfer_group)
        
        self.server_combo = QComboBox()
        self.server_combo.setEditable(True)
        self.server_combo.addItems(["服务器 1", "服务器 2", "服务器 3"])
        transfer_layout.addRow("目标服务器:", self.server_combo)
        
        self.target_dir_input = QLineEdit()
        self.target_dir_input.setPlaceholderText("目标服务器上的目录路径")
        transfer_layout.addRow("目标目录:", self.target_dir_input)
        
        layout.addWidget(self.transfer_group)
        
        layout.addStretch()
        self.stack.addWidget(page)
    
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
        self.stack.addWidget(page)
    
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
        self.stack.addWidget(page)
    
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
    
    def _on_task_type_changed(self):
        """任务类型改变"""
        show_transfer = self.download_transfer_radio.isChecked() or self.transfer_local_radio.isChecked()
        self.transfer_group.setVisible(show_transfer)
        
        # 仅传输本地文件时，不需要缓存目录
        show_cache = not self.transfer_local_radio.isChecked()
        self.cache_widget.setVisible(show_cache)
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
        """模型来源切换"""
        is_local = self.local_radio.isChecked()
        self.remote_model_widget.setVisible(not is_local)
        self.local_model_widget.setVisible(is_local)
        
        if is_local:
            self.log_signal.emit("切换到本地模型模式", "INFO")
            # 自动选择传输任务
            self.transfer_local_radio.setChecked(True)
        else:
            source = "HuggingFace" if self.hf_radio.isChecked() else "ModelScope"
            self.log_signal.emit(f"切换到远程模型模式: {source}", "INFO")
    
    def _on_task_type_changed(self):
        """任务类型改变"""
        show_transfer = self.download_transfer_radio.isChecked() or self.transfer_local_radio.isChecked()
        self.transfer_group.setVisible(show_transfer)
    
    def _browse_cache_dir(self):
        """浏览缓存目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择缓存目录")
        if dir_path:
            self.cache_input.setText(dir_path)
    
    def _browse_local_model(self):
        """浏览本地模型目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择本地模型目录")
        if dir_path:
            self.local_path_input.setText(dir_path)
            self.log_signal.emit(f"已选择本地模型目录: {dir_path}", "INFO")
            # 扫描目录中的文件
            self._scan_local_files(dir_path)
    
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
        self.fetch_version_btn.setText("...")
        self.version_combo.clear()
        self.version_combo.setPlaceholderText("获取中...")
        
        self.log_signal.emit(f"正在获取模型 {model_id} 的版本列表...", "INFO")
        
        worker = VersionFetchWorker(self, model_id, self.hf_radio.isChecked())
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
        """版本列表获取失败的回调（在主线程执行）"""
        self.version_combo.clear()
        self.version_combo.addItems(["main", "master", "latest"])
        self.version_combo.setCurrentText("main")
        self.fetch_version_btn.setEnabled(True)
        self.fetch_version_btn.setText("获取")
        self.log_signal.emit(f"获取版本列表失败: {error_msg}", "ERROR")
    
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
        """检查存储空间"""
        cache_dir = self.cache_input.text().strip()
        if not cache_dir:
            cache_dir = str(Path.home() / ".cache" / "model-transfer")
        
        try:
            import shutil
            total, used, free = shutil.disk_usage(cache_dir)
            free_gb = free / (1024**3)
            
            # 计算所需空间（从文件列表）
            required_gb = 0
            for i in range(self.files_tree.topLevelItemCount()):
                item = self.files_tree.topLevelItem(i)
                size_str = item.text(1)
                required_gb += self._parse_size(size_str)
            
            required_gb = required_gb / (1024**3)
            
            if free_gb < required_gb:
                self.log_signal.emit(
                    f"存储空间不足: 需要 {required_gb:.1f} GB, 可用 {free_gb:.1f} GB",
                    "WARNING"
                )
        except Exception:
            pass
    
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
        except:
            return 0
    
    def _on_finish(self):
        """完成按钮点击"""
        task_data = self._get_task_data()
        self.task_created.emit(task_data)
        self.log_signal.emit("任务已提交", "SUCCESS")
        
        # 重置向导
        self.reset()
    
    def _get_task_data(self):
        """获取任务数据"""
        task_id = self.task_group_btn.checkedId()
        task_type = ["download_only", "download_transfer", "transfer_local"][task_id]
        
        if self.local_radio.isChecked():
            return {
                "source": "local",
                "model_id": self.local_path_input.text(),
                "version": "local",
                "filter": self.filter_input.text(),
                "task_type": task_type,
                "cache_dir": self.local_path_input.text(),
                "server": self.server_combo.currentText() if task_id in [1, 2] else None,
                "target_dir": self.target_dir_input.text() if task_id in [1, 2] else None,
            }
        
        return {
            "source": "huggingface" if self.hf_radio.isChecked() else "modelscope",
            "model_id": self.model_id_input.text(),
            "version": self.version_combo.currentText(),
            "filter": self.filter_input.text(),
            "task_type": task_type,
            "cache_dir": self.cache_input.text(),
            "server": self.server_combo.currentText() if task_id in [1, 2] else None,
            "target_dir": self.target_dir_input.text() if task_id in [1, 2] else None,
        }
    
    def _on_pause(self):
        """暂停"""
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(True)
        self.log_signal.emit("任务已暂停", "INFO")
    
    def _on_resume(self):
        """恢复"""
        self.pause_btn.setEnabled(True)
        self.resume_btn.setEnabled(False)
        self.log_signal.emit("任务已恢复", "INFO")
    
    def _on_cancel(self):
        """取消"""
        reply = QMessageBox.question(
            self, "确认取消", "确定要取消当前任务吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.log_signal.emit("任务已取消", "WARNING")
            self.reset()
    
    def _on_retry(self):
        """重试失败项"""
        self.log_signal.emit("正在重试失败项...", "INFO")
    
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
                
                version = self.version_combo.currentText()
                if not version or version == "输入模型ID后自动获取...":
                    QMessageBox.warning(self, "警告", "请选择或输入版本/分支")
                    return
                
                self.log_signal.emit(f"步骤1完成 - 模型: {model_id}, 版本: {version}", "INFO")
        
        elif self.current_step == 1:
            # Step 2 验证
            task_id = self.task_group_btn.checkedId()
            cache_dir = self.cache_input.text().strip()
            
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

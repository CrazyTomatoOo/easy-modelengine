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
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont


class WizardPanel(QWidget):
    """4步向导面板"""
    
    task_created = pyqtSignal(dict)
    
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
        self.hf_radio.setChecked(True)
        source_layout.addWidget(self.hf_radio)
        source_layout.addWidget(self.ms_radio)
        source_layout.addStretch()
        layout.addWidget(source_group)
        
        # 模型 ID
        model_layout = QFormLayout()
        self.model_id_input = QLineEdit()
        self.model_id_input.setPlaceholderText("例如: bert-base-chinese")
        model_layout.addRow("模型 ID:", self.model_id_input)
        layout.addLayout(model_layout)
        
        # 版本选择
        version_layout = QFormLayout()
        self.version_combo = QComboBox()
        self.version_combo.setEditable(True)
        self.version_combo.addItems(["main", "master", "latest"])
        self.version_combo.setCurrentText("main")
        version_layout.addRow("版本/分支:", self.version_combo)
        layout.addLayout(version_layout)
        
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
        
        # 代理设置（可折叠）
        self.proxy_checkbox = QCheckBox("使用代理")
        layout.addWidget(self.proxy_checkbox)
        
        self.proxy_group = QGroupBox("代理设置")
        self.proxy_group.setVisible(False)
        proxy_layout = QFormLayout(self.proxy_group)
        
        self.proxy_url_input = QLineEdit()
        self.proxy_url_input.setPlaceholderText("http://proxy.example.com:8080")
        proxy_layout.addRow("代理地址:", self.proxy_url_input)
        
        self.proxy_username_input = QLineEdit()
        proxy_layout.addRow("用户名:", self.proxy_username_input)
        
        self.proxy_password_input = QLineEdit()
        self.proxy_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        proxy_layout.addRow("密码:", self.proxy_password_input)
        
        layout.addWidget(self.proxy_group)
        
        layout.addStretch()
        self.stack.addWidget(page)
    
    def _setup_step3(self):
        """Step 3: 确认执行"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("确认执行")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        
        # 任务摘要
        summary_group = QGroupBox("任务摘要")
        summary_layout = QFormLayout(summary_group)
        self.summary_source = QLabel("-")
        self.summary_model = QLabel("-")
        self.summary_version = QLabel("-")
        self.summary_task = QLabel("-")
        self.summary_target = QLabel("-")
        
        summary_layout.addRow("模型来源:", self.summary_source)
        summary_layout.addRow("模型 ID:", self.summary_model)
        summary_layout.addRow("版本:", self.summary_version)
        summary_layout.addRow("任务类型:", self.summary_task)
        summary_layout.addRow("目标位置:", self.summary_target)
        layout.addWidget(summary_group)
        
        # 文件清单预览
        files_group = QGroupBox("文件清单预览")
        files_layout = QVBoxLayout(files_group)
        self.files_tree = QTreeWidget()
        self.files_tree.setHeaderLabels(["文件名", "大小", "状态"])
        self.files_tree.setColumnWidth(0, 300)
        files_layout.addWidget(self.files_tree)
        layout.addWidget(files_group)
        
        # 存储空间提示
        self.storage_label = QLabel("正在检查存储空间...")
        self.storage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.storage_label.setStyleSheet("color: #666;")
        layout.addWidget(self.storage_label)
        
        layout.addStretch()
        self.stack.addWidget(page)
    
    def _setup_step4(self):
        """Step 4: 执行监控"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("执行监控")
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
        
        # 速度和 ETA
        info_layout = QHBoxLayout()
        self.speed_label = QLabel("速度: -")
        self.eta_label = QLabel("预计剩余时间: -")
        info_layout.addWidget(self.speed_label)
        info_layout.addStretch()
        info_layout.addWidget(self.eta_label)
        progress_layout.addLayout(info_layout)
        
        layout.addWidget(progress_group)
        
        # 文件状态列表
        status_group = QGroupBox("文件状态")
        status_layout = QVBoxLayout(status_group)
        self.status_list = QListWidget()
        status_layout.addWidget(self.status_list)
        layout.addWidget(status_group)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.pause_btn = QPushButton("暂停")
        self.resume_btn = QPushButton("恢复")
        self.resume_btn.setEnabled(False)
        self.cancel_btn = QPushButton("取消")
        
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.resume_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.cancel_btn)
        layout.addLayout(control_layout)
        
        # 完成后按钮（初始隐藏）
        self.completed_layout = QHBoxLayout()
        self.retry_btn = QPushButton("重试失败项")
        self.export_btn = QPushButton("导出日志")
        self.completed_layout.addWidget(self.retry_btn)
        self.completed_layout.addWidget(self.export_btn)
        self.completed_layout.addStretch()
        
        self.retry_btn.hide()
        self.export_btn.hide()
        layout.addLayout(self.completed_layout)
        
        layout.addStretch()
        self.stack.addWidget(page)
    
    def _connect_signals(self):
        """连接信号"""
        self.prev_btn.clicked.connect(self.go_prev)
        self.next_btn.clicked.connect(self.go_next)
        self.finish_btn.clicked.connect(self._on_finish)
        
        # Step 2 信号
        self.task_group_btn.idClicked.connect(self._on_task_type_changed)
        self.proxy_checkbox.stateChanged.connect(self._on_proxy_toggled)
        self.cache_btn.clicked.connect(self._on_browse_cache)
        
        # Step 4 信号
        self.pause_btn.clicked.connect(self._on_pause)
        self.resume_btn.clicked.connect(self._on_resume)
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.retry_btn.clicked.connect(self._on_retry)
        self.export_btn.clicked.connect(self._on_export)
    
    def _update_ui(self):
        """更新UI状态"""
        self.step_label.setText(f"步骤 {self.current_step + 1}/4")
        self.stack.setCurrentIndex(self.current_step)
        
        # 更新按钮状态
        self.prev_btn.setEnabled(self.current_step > 0)
        
        if self.current_step == 3:
            self.next_btn.hide()
            self.finish_btn.show()
        else:
            self.next_btn.show()
            self.finish_btn.hide()
        
        # 进入步骤时的特殊处理
        if self.current_step == 2:
            self._update_summary()
    
    def _on_task_type_changed(self, task_id):
        """任务类型改变时更新UI"""
        has_transfer = task_id in [1, 2]  # 下载并传输 或 仅传输本地
        self.transfer_group.setVisible(has_transfer)
    
    def _on_proxy_toggled(self, state):
        """代理复选框切换"""
        self.proxy_group.setVisible(state == Qt.CheckState.Checked.value)
    
    def _on_browse_cache(self):
        """浏览缓存目录"""
        directory = QFileDialog.getExistingDirectory(self, "选择缓存目录")
        if directory:
            self.cache_input.setText(directory)
    
    def _update_summary(self):
        """更新任务摘要"""
        # 模型来源
        if self.hf_radio.isChecked():
            self.summary_source.setText("HuggingFace")
        else:
            self.summary_source.setText("ModelScope")
        
        # 模型信息
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
        
        # 更新文件列表（模拟）
        self.files_tree.clear()
        # 这里应该根据实际模型文件填充，现在用示例数据
        sample_files = [
            ("config.json", "1.2 KB", "待下载"),
            ("pytorch_model.bin", "440 MB", "待下载"),
            ("tokenizer.json", "2.1 MB", "待下载"),
            ("README.md", "5.6 KB", "待下载"),
        ]
        for filename, size, status in sample_files:
            item = QTreeWidgetItem([filename, size, status])
            self.files_tree.addTopLevelItem(item)
        
        # 更新存储空间提示
        self.storage_label.setText("存储空间检查: 可用空间充足 ✓")
        self.storage_label.setStyleSheet("color: green;")
    
    def _on_finish(self):
        """完成按钮点击"""
        task_data = self._get_task_data()
        self.task_created.emit(task_data)
        
        # 重置向导
        self.reset()
    
    def _get_task_data(self):
        """获取任务数据"""
        task_id = self.task_group_btn.checkedId()
        task_type = ["download_only", "download_transfer", "transfer_local"][task_id]
        
        return {
            "source": "huggingface" if self.hf_radio.isChecked() else "modelscope",
            "model_id": self.model_id_input.text(),
            "version": self.version_combo.currentText(),
            "filter": self.filter_input.text(),
            "task_type": task_type,
            "cache_dir": self.cache_input.text(),
            "server": self.server_combo.currentText() if task_id in [1, 2] else None,
            "target_dir": self.target_dir_input.text() if task_id in [1, 2] else None,
            "proxy": {
                "enabled": self.proxy_checkbox.isChecked(),
                "url": self.proxy_url_input.text(),
                "username": self.proxy_username_input.text(),
                "password": self.proxy_password_input.text(),
            } if self.proxy_checkbox.isChecked() else None,
        }
    
    def _on_pause(self):
        """暂停"""
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(True)
    
    def _on_resume(self):
        """恢复"""
        self.pause_btn.setEnabled(True)
        self.resume_btn.setEnabled(False)
    
    def _on_cancel(self):
        """取消"""
        reply = QMessageBox.question(
            self, "确认取消", "确定要取消当前任务吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.reset()
    
    def _on_retry(self):
        """重试失败项"""
        pass  # 由外部处理
    
    def _on_export(self):
        """导出日志"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", "task_log.txt", "文本文件 (*.txt)"
        )
        if file_path:
            pass  # 由外部处理日志导出
    
    def go_next(self):
        """下一步"""
        if self.current_step < 3:
            self.current_step += 1
            self._update_ui()
    
    def go_prev(self):
        """上一步"""
        if self.current_step > 0:
            self.current_step -= 1
            self._update_ui()
    
    def reset(self):
        """重置向导"""
        self.current_step = 0
        self.model_id_input.clear()
        self.version_combo.setCurrentText("main")
        self.filter_input.clear()
        self.download_only_radio.setChecked(True)
        self.cache_input.clear()
        self.server_combo.setCurrentIndex(0)
        self.target_dir_input.clear()
        self.proxy_checkbox.setChecked(False)
        self.proxy_url_input.clear()
        self.proxy_username_input.clear()
        self.proxy_password_input.clear()
        self.total_progress.setValue(0)
        self.speed_label.setText("速度: -")
        self.eta_label.setText("预计剩余时间: -")
        self.status_list.clear()
        self._update_ui()
    
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
        
        self.retry_btn.show()
        self.export_btn.show()

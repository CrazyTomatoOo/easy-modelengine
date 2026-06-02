#!/usr/bin/env python3
"""
服务器配置管理对话框模块
用于管理远程服务器连接配置
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QRadioButton, QButtonGroup, QSpinBox, QFileDialog,
    QMessageBox, QWidget, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from core.database import Database
from utils.crypto import SecureStorage
from gui.theme import ThemeManager


class ServerConfigEditDialog(QDialog):
    """服务器配置编辑对话框（新增/编辑）"""
    
    config_saved = pyqtSignal(dict)
    
    def __init__(self, parent=None, config=None, existing_names=None):
        """
        初始化编辑对话框
        
        Args:
            parent: 父窗口
            config: 现有配置字典（编辑模式），None 表示新增模式
            existing_names: 已存在的配置名称列表（用于唯一性验证）
        """
        super().__init__(parent)
        self.config = config or {}
        self.existing_names = existing_names or []
        self.original_name = self.config.get('name', '')
        self.is_edit_mode = bool(self.config.get('id'))
        self._result_config = None
        
        self.setWindowTitle("编辑服务器配置" if self.is_edit_mode else "添加服务器配置")
        self.setMinimumWidth(450)
        self.setModal(True)
        
        self._setup_ui()
        self._load_config()
    
    def _setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title = QLabel("编辑服务器配置" if self.is_edit_mode else "添加服务器配置")
        title.setObjectName("title")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #ccc;")
        line.setFixedHeight(1)
        layout.addWidget(line)
        
        # 表单
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        
        # 名称
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("输入唯一的配置名称")
        form_layout.addRow("配置名称 *:", self.name_input)
        
        # 主机
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("例如: 192.168.1.100 或 example.com")
        form_layout.addRow("主机地址 *:", self.host_input)
        
        # 端口
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(22)
        self.port_input.setFixedWidth(100)
        form_layout.addRow("SSH 端口:", self.port_input)
        
        # 用户名
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("登录用户名")
        form_layout.addRow("用户名 *:", self.username_input)
        
        # 认证类型
        auth_group = QWidget()
        auth_layout = QHBoxLayout(auth_group)
        auth_layout.setContentsMargins(0, 0, 0, 0)
        
        self.auth_group = QButtonGroup(self)
        self.password_radio = QRadioButton("密码")
        self.ssh_key_radio = QRadioButton("SSH 密钥")
        self.password_radio.setChecked(True)
        
        self.auth_group.addButton(self.password_radio, 0)
        self.auth_group.addButton(self.ssh_key_radio, 1)
        
        auth_layout.addWidget(self.password_radio)
        auth_layout.addWidget(self.ssh_key_radio)
        auth_layout.addStretch()
        
        form_layout.addRow("认证方式:", auth_group)
        
        # 认证凭据 - 密码模式
        self.password_widget = QWidget()
        password_layout = QHBoxLayout(self.password_widget)
        password_layout.setContentsMargins(0, 0, 0, 0)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("输入密码" if not self.is_edit_mode else "留空表示不修改")
        password_layout.addWidget(self.password_input)
        
        form_layout.addRow("密码:", self.password_widget)
        
        # 认证凭据 - SSH 密钥模式
        self.ssh_key_widget = QWidget()
        ssh_key_layout = QHBoxLayout(self.ssh_key_widget)
        ssh_key_layout.setContentsMargins(0, 0, 0, 0)
        
        self.ssh_key_input = QLineEdit()
        self.ssh_key_input.setPlaceholderText("选择 SSH 私钥文件路径")
        ssh_key_layout.addWidget(self.ssh_key_input)
        
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self._browse_ssh_key)
        ssh_key_layout.addWidget(self.browse_btn)
        
        form_layout.addRow("私钥路径:", self.ssh_key_widget)
        self.ssh_key_widget.hide()
        
        layout.addLayout(form_layout)
        
        # 连接认证类型切换信号
        self.password_radio.toggled.connect(self._on_auth_type_changed)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.save_btn = QPushButton("保存")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        layout.addStretch()
    
    def _on_auth_type_changed(self, checked):
        """认证类型切换"""
        if checked:
            self.password_widget.show()
            self.ssh_key_widget.hide()
        else:
            self.password_widget.hide()
            self.ssh_key_widget.show()
    
    def _browse_ssh_key(self):
        """浏览 SSH 密钥文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 SSH 私钥",
            "",
            "所有文件 (*.*)"
        )
        if file_path:
            self.ssh_key_input.setText(file_path)
    
    def _load_config(self):
        """加载现有配置（编辑模式）"""
        if not self.config:
            return
        
        self.name_input.setText(self.config.get('name', ''))
        self.host_input.setText(self.config.get('host', ''))
        self.port_input.setValue(self.config.get('port', 22))
        self.username_input.setText(self.config.get('username', ''))
        
        auth_type = self.config.get('auth_type', 'password')
        if auth_type == 'ssh_key':
            self.ssh_key_radio.setChecked(True)
            # 尝试解密并显示 SSH 密钥路径
            try:
                encrypted_auth = self.config.get('encrypted_auth', b'')
                auth_salt = self.config.get('auth_salt', b'')
                if encrypted_auth and auth_salt:
                    # encrypted_auth = nonce(12 bytes) + ciphertext
                    nonce = encrypted_auth[:12]
                    ciphertext = encrypted_auth[12:]
                    ssh_key_path = SecureStorage.decrypt(ciphertext, nonce, auth_salt)
                    self.ssh_key_input.setText(ssh_key_path)
            except Exception:
                self.ssh_key_input.setText('')
        else:
            self.password_radio.setChecked(True)
            # 编辑模式下密码留空，表示不修改
            self.password_input.clear()
    
    def _validate(self) -> bool:
        """验证表单数据"""
        name = self.name_input.text().strip()
        host = self.host_input.text().strip()
        username = self.username_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "验证失败", "配置名称不能为空")
            self.name_input.setFocus()
            return False
        
        # 检查名称唯一性
        if name != self.original_name and name in self.existing_names:
            QMessageBox.warning(self, "验证失败", f"配置名称 '{name}' 已存在")
            self.name_input.setFocus()
            return False
        
        if not host:
            QMessageBox.warning(self, "验证失败", "主机地址不能为空")
            self.host_input.setFocus()
            return False
        
        if not username:
            QMessageBox.warning(self, "验证失败", "用户名不能为空")
            self.username_input.setFocus()
            return False
        
        # 验证凭据
        if self.password_radio.isChecked():
            password = self.password_input.text()
            # 新增模式必须输入密码
            if not self.is_edit_mode and not password:
                QMessageBox.warning(self, "验证失败", "请输入密码")
                self.password_input.setFocus()
                return False
        else:
            ssh_key_path = self.ssh_key_input.text().strip()
            if not ssh_key_path:
                QMessageBox.warning(self, "验证失败", "请选择 SSH 私钥文件")
                return False
        
        return True
    
    def _on_save(self):
        """保存配置"""
        if not self._validate():
            return
        
        name = self.name_input.text().strip()
        host = self.host_input.text().strip()
        port = self.port_input.value()
        username = self.username_input.text().strip()
        
        # 处理认证凭据
        if self.password_radio.isChecked():
            auth_type = 'password'
            password = self.password_input.text()
            
            # 编辑模式下，如果密码为空，保留原有凭据
            if self.is_edit_mode and not password:
                encrypted_auth = self.config.get('encrypted_auth')
                auth_salt = self.config.get('auth_salt')
            else:
                ciphertext, nonce, salt = SecureStorage.encrypt(password)
                encrypted_auth = nonce + ciphertext
                auth_salt = salt
        else:
            auth_type = 'ssh_key'
            ssh_key_path = self.ssh_key_input.text().strip()
            
            # 编辑模式下，如果路径为空，保留原有凭据（但前面已验证不会为空）
            if self.is_edit_mode and not ssh_key_path:
                encrypted_auth = self.config.get('encrypted_auth')
                auth_salt = self.config.get('auth_salt')
            else:
                ciphertext, nonce, salt = SecureStorage.encrypt(ssh_key_path)
                encrypted_auth = nonce + ciphertext
                auth_salt = salt
        
        config_data = {
            'id': self.config.get('id'),
            'name': name,
            'host': host,
            'port': port,
            'username': username,
            'auth_type': auth_type,
            'encrypted_auth': encrypted_auth,
            'auth_salt': auth_salt,
        }
        
        self._result_config = config_data
        self.config_saved.emit(config_data)
        self.accept()
    
    def get_config(self) -> dict:
        """获取配置数据（供调用方使用）"""
        return self._result_config or {}


class ServerConfigDialog(QDialog):
    """服务器配置管理主对话框"""
    
    def __init__(self, parent=None, database: Database = None):
        """
        初始化服务器配置管理对话框
        
        Args:
            parent: 父窗口
            database: 数据库实例
        """
        super().__init__(parent)
        self.db = database
        self.configs = []
        
        self.setWindowTitle("服务器配置管理")
        self.setMinimumSize(600, 450)
        self.setModal(True)
        
        self._setup_ui()
        self._refresh_list()
    
    def _setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title = QLabel("服务器配置管理")
        title.setObjectName("title")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("管理远程服务器连接配置，用于模型权重传输")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #ccc;")
        line.setFixedHeight(1)
        layout.addWidget(line)
        
        # 配置列表
        self.config_list = QListWidget()
        self.config_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.config_list.itemDoubleClicked.connect(self._on_edit)
        self.config_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                margin: 2px 0px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background-color: #e3f2fd;
            }
        """)
        layout.addWidget(self.config_list)
        
        # 按钮区域 - 使用网格布局更清晰
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.add_btn = QPushButton("➕ 添加")
        self.add_btn.setToolTip("添加新的服务器配置")
        self.add_btn.clicked.connect(self._on_add)
        self.add_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        
        self.edit_btn = QPushButton("✏️ 编辑")
        self.edit_btn.setToolTip("编辑选中的服务器配置")
        self.edit_btn.clicked.connect(self._on_edit)
        self.edit_btn.setEnabled(False)
        self.edit_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        
        self.delete_btn = QPushButton("🗑️ 删除")
        self.delete_btn.setToolTip("删除选中的服务器配置")
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        
        self.test_btn = QPushButton("🔌 测试连接")
        self.test_btn.setToolTip("测试选中服务器的连接")
        self.test_btn.clicked.connect(self._on_test_connection)
        self.test_btn.setEnabled(False)
        self.test_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.test_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        # 底部关闭按钮
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.setObjectName("secondary")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 24px;
                background-color: #757575;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
            QPushButton:pressed {
                background-color: #424242;
            }
        """)
        close_layout.addWidget(self.close_btn)
        
        layout.addLayout(close_layout)
        
        # 连接列表选择信号
        self.config_list.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _refresh_list(self):
        """刷新配置列表"""
        self.config_list.clear()
        
        if not self.db:
            return
        
        try:
            self.configs = self.db.get_server_configs()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取服务器配置失败:\n{str(e)}")
            self.configs = []
            return
        
        for config in self.configs:
            auth_type_text = "🔑 密码" if config.get('auth_type') == 'password' else "🔐 SSH 密钥"
            display_text = (
                f"📡 {config.get('name', '未命名')}\n"
                f"   {config.get('host', '-')}:{config.get('port', 22)}  |  "
                f"👤 {config.get('username', '-')}  |  "
                f"{auth_type_text}"
            )
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, config.get('id'))
            self.config_list.addItem(item)
    
    def _get_selected_config(self) -> dict:
        """获取当前选中的配置"""
        current_item = self.config_list.currentItem()
        if not current_item:
            return {}
        
        config_id = current_item.data(Qt.ItemDataRole.UserRole)
        for config in self.configs:
            if config.get('id') == config_id:
                return config
        return {}
    
    def _on_selection_changed(self):
        """列表选择变化"""
        has_selection = self.config_list.currentItem() is not None
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.test_btn.setEnabled(has_selection)
    
    def _get_existing_names(self) -> list:
        """获取已存在的配置名称列表"""
        return [config.get('name', '') for config in self.configs]
    
    def _on_add(self):
        """添加新配置"""
        dialog = ServerConfigEditDialog(
            parent=self,
            existing_names=self._get_existing_names()
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config_data = dialog.get_config()
            self._save_to_database(config_data)
    
    def _on_edit(self):
        """编辑选中配置"""
        config = self._get_selected_config()
        if not config:
            return
        
        dialog = ServerConfigEditDialog(
            parent=self,
            config=config,
            existing_names=self._get_existing_names()
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config_data = dialog.get_config()
            self._save_to_database(config_data)
    
    def _save_to_database(self, config_data: dict):
        """保存配置到数据库"""
        if not self.db:
            QMessageBox.warning(self, "警告", "数据库未初始化")
            return
        
        try:
            self.db.save_server_config(
                name=config_data['name'],
                host=config_data['host'],
                username=config_data['username'],
                auth_type=config_data['auth_type'],
                encrypted_auth=config_data['encrypted_auth'],
                auth_salt=config_data['auth_salt'],
                port=config_data['port']
            )
            self._refresh_list()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存服务器配置失败:\n{str(e)}")
    
    def _on_delete(self):
        """删除选中配置"""
        config = self._get_selected_config()
        if not config:
            return
        
        name = config.get('name', '此配置')
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除服务器配置 '{name}' 吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                config_id = config.get('id')
                if config_id and self.db:
                    success = self.db.delete_server_config(config_id)
                    if success:
                        self._refresh_list()
                        QMessageBox.information(self, "成功", f"配置 '{name}' 已删除")
                    else:
                        QMessageBox.warning(self, "失败", "删除配置失败")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除配置失败:\n{str(e)}")
    
    def _on_test_connection(self):
        """测试连接"""
        config = self._get_selected_config()
        if not config:
            return
        
        name = config.get('name', '未知')
        host = config.get('host', '-')
        port = config.get('port', 22)
        username = config.get('username', '-')
        auth_type = config.get('auth_type', 'password')
        
        # 构建凭据信息（不显示实际密码）
        auth_text = "密码认证" if auth_type == 'password' else "SSH 密钥认证"
        
        info_text = (
            f"正在测试连接...\n\n"
            f"配置: {name}\n"
            f"主机: {host}:{port}\n"
            f"用户: {username}\n"
            f"认证: {auth_text}\n\n"
            f"注意: 连接测试功能需要安装 paramiko 库。"
        )
        
        QMessageBox.information(self, "测试连接", info_text)

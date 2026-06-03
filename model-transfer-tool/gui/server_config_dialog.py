#!/usr/bin/env python3
"""
服务器配置管理对话框模块 - 现代化设计
使用卡片式布局和分栏设计
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QRadioButton, QButtonGroup, QSpinBox, QFileDialog,
    QMessageBox, QWidget, QFrame, QScrollArea, QGridLayout,
    QSizePolicy, QSpacerItem, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon

from core.database import Database
from utils.crypto import SecureStorage


class ServerCard(QWidget):
    """服务器卡片组件"""
    
    clicked = pyqtSignal(str)  # 发送服务器ID
    
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.server_id = str(config.get('id', ''))
        self._setup_ui()
        self._apply_style()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 头部：名称 + 认证类型标签
        header = QHBoxLayout()
        
        self.name_label = QLabel(self.config.get('name', '未命名'))
        self.name_label.setObjectName("card_name")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        self.name_label.setFont(font)
        header.addWidget(self.name_label)
        
        header.addStretch()
        
        # 认证类型标签
        auth_type = self.config.get('auth_type', 'password')
        auth_text = "密码认证" if auth_type == 'password' else "SSH密钥"
        self.auth_label = QLabel(auth_text)
        self.auth_label.setObjectName("auth_badge")
        self.auth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.auth_label.setStyleSheet("""
            QLabel {
                background-color: rgba(99, 102, 241, 0.15);
                color: #6366F1;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 600;
            }
        """)
        header.addWidget(self.auth_label)
        
        layout.addLayout(header)
        
        # 主机信息
        host = self.config.get('host', '-')
        port = self.config.get('port', 22)
        self.host_label = QLabel(f"{host}:{port}")
        self.host_label.setObjectName("card_host")
        self.host_label.setStyleSheet("color: #64748B; font-size: 12px;")
        layout.addWidget(self.host_label)
        
        # 用户信息
        username = self.config.get('username', '-')
        self.user_label = QLabel(f"用户: {username}")
        self.user_label.setObjectName("card_user")
        self.user_label.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(self.user_label)
    
    def _apply_style(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border: 2px solid #E2E8F0;
                border-radius: 12px;
            }
            QWidget:hover {
                border-color: #6366F1;
                background-color: #F8FAFF;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(120)
    
    def mousePressEvent(self, event):
        self.clicked.emit(self.server_id)
    
    def set_selected(self, selected: bool):
        if selected:
            self.setStyleSheet("""
                QWidget {
                    background-color: #EEF2FF;
                    border: 2px solid #6366F1;
                    border-radius: 12px;
                }
            """)
        else:
            self._apply_style()


class EmptyStateWidget(QWidget):
    """空状态提示组件"""
    
    add_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        
        # 图标区域（使用Unicode字符作为占位）
        icon_label = QLabel("🖥️")
        icon_label.setStyleSheet("font-size: 48px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # 标题
        title = QLabel("暂无服务器配置")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #1E293B;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 描述
        desc = QLabel("添加服务器配置以开始传输模型权重到远程服务器")
        desc.setStyleSheet("font-size: 13px; color: #64748B;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # 添加按钮
        self.add_btn = QPushButton("+ 添加服务器")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366F1;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4F46E5;
            }
        """)
        self.add_btn.clicked.connect(self.add_clicked.emit)
        layout.addWidget(self.add_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addStretch()


class ServerConfigEditDialog(QDialog):
    """服务器配置编辑对话框（新增/编辑）"""
    
    config_saved = pyqtSignal(dict)
    
    def __init__(self, parent=None, config=None, existing_names=None):
        super().__init__(parent)
        self.config = config or {}
        self.existing_names = existing_names or []
        self.original_name = self.config.get('name', '')
        self.is_edit_mode = bool(self.config.get('id'))
        self._result_config = None
        
        self.setWindowTitle("编辑服务器配置" if self.is_edit_mode else "添加服务器配置")
        self.setMinimumWidth(480)
        self.setModal(True)
        
        self._setup_ui()
        self._load_config()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # 标题
        title = QLabel("编辑服务器配置" if self.is_edit_mode else "添加服务器配置")
        title.setObjectName("title")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #E2E8F0;")
        line.setFixedHeight(1)
        layout.addWidget(line)
        
        # 基本信息分组
        basic_group = QFrame()
        basic_group.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(12)
        
        # 名称
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("输入唯一的配置名称，如：生产服务器")
        basic_layout.addRow("配置名称 *", self.name_input)
        
        # 主机
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("例如: 192.168.1.100 或 example.com")
        basic_layout.addRow("主机地址 *", self.host_input)
        
        # 端口和用户名并排
        row_layout = QHBoxLayout()
        
        port_widget = QWidget()
        port_layout = QFormLayout(port_widget)
        port_layout.setContentsMargins(0, 0, 0, 0)
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(22)
        self.port_input.setFixedWidth(100)
        port_layout.addRow("SSH端口", self.port_input)
        row_layout.addWidget(port_widget)
        
        row_layout.addSpacing(20)
        
        user_widget = QWidget()
        user_layout = QFormLayout(user_widget)
        user_layout.setContentsMargins(0, 0, 0, 0)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("登录用户名")
        user_layout.addRow("用户名 *", self.username_input)
        row_layout.addWidget(user_widget)
        row_layout.addStretch()
        
        basic_layout.addRow(row_layout)
        layout.addWidget(basic_group)
        
        # 认证信息分组
        auth_group = QFrame()
        auth_group.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        auth_layout = QVBoxLayout(auth_group)
        auth_layout.setSpacing(12)
        
        # 认证类型
        auth_type_layout = QHBoxLayout()
        auth_type_label = QLabel("认证方式")
        auth_type_label.setStyleSheet("font-weight: 600;")
        auth_type_layout.addWidget(auth_type_label)
        
        self.auth_group = QButtonGroup(self)
        self.password_radio = QRadioButton("密码认证")
        self.ssh_key_radio = QRadioButton("SSH密钥")
        self.password_radio.setChecked(True)
        
        self.auth_group.addButton(self.password_radio, 0)
        self.auth_group.addButton(self.ssh_key_radio, 1)
        
        auth_type_layout.addWidget(self.password_radio)
        auth_type_layout.addWidget(self.ssh_key_radio)
        auth_type_layout.addStretch()
        auth_layout.addLayout(auth_type_layout)
        
        # 密码输入
        self.password_widget = QWidget()
        password_layout = QFormLayout(self.password_widget)
        password_layout.setContentsMargins(0, 0, 0, 0)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        placeholder = "留空表示不修改" if self.is_edit_mode else "输入密码"
        self.password_input.setPlaceholderText(placeholder)
        password_layout.addRow("密码", self.password_input)
        auth_layout.addWidget(self.password_widget)
        
        # SSH密钥输入
        self.ssh_key_widget = QWidget()
        ssh_key_layout = QHBoxLayout(self.ssh_key_widget)
        ssh_key_layout.setContentsMargins(0, 0, 0, 0)
        self.ssh_key_input = QLineEdit()
        self.ssh_key_input.setPlaceholderText("选择SSH私钥文件路径")
        ssh_key_layout.addWidget(self.ssh_key_input)
        
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self._browse_ssh_key)
        ssh_key_layout.addWidget(self.browse_btn)
        
        # 将SSH密钥输入放入表单布局
        ssh_key_form = QFormLayout()
        ssh_key_form.setContentsMargins(0, 0, 0, 0)
        ssh_key_form.addRow("私钥路径", self.ssh_key_widget)
        auth_layout.addLayout(ssh_key_form)
        
        self.ssh_key_widget.hide()
        layout.addWidget(auth_group)
        
        # 连接认证类型切换信号
        self.password_radio.toggled.connect(self._on_auth_type_changed)
        
        layout.addStretch()
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        self.save_btn = QPushButton("保存配置")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_auth_type_changed(self, checked):
        if checked:
            self.password_widget.show()
            self.ssh_key_widget.hide()
        else:
            self.password_widget.hide()
            self.ssh_key_widget.show()
    
    def _browse_ssh_key(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择SSH私钥",
            "",
            "所有文件 (*.*)"
        )
        if file_path:
            self.ssh_key_input.setText(file_path)
    
    def _load_config(self):
        if not self.config:
            return
        
        self.name_input.setText(self.config.get('name', ''))
        self.host_input.setText(self.config.get('host', ''))
        self.port_input.setValue(self.config.get('port', 22))
        self.username_input.setText(self.config.get('username', ''))
        
        auth_type = self.config.get('auth_type', 'password')
        if auth_type == 'ssh_key':
            self.ssh_key_radio.setChecked(True)
            try:
                encrypted_auth = self.config.get('encrypted_auth', b'')
                auth_salt = self.config.get('auth_salt', b'')
                if encrypted_auth and auth_salt:
                    nonce = encrypted_auth[:12]
                    ciphertext = encrypted_auth[12:]
                    ssh_key_path = SecureStorage.decrypt(ciphertext, nonce, auth_salt)
                    self.ssh_key_input.setText(ssh_key_path)
            except Exception:
                self.ssh_key_input.setText('')
        else:
            self.password_radio.setChecked(True)
            self.password_input.clear()
    
    def _validate(self) -> bool:
        name = self.name_input.text().strip()
        host = self.host_input.text().strip()
        username = self.username_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "验证失败", "配置名称不能为空")
            self.name_input.setFocus()
            return False
        
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
        
        if self.password_radio.isChecked():
            password = self.password_input.text()
            if not self.is_edit_mode and not password:
                QMessageBox.warning(self, "验证失败", "请输入密码")
                self.password_input.setFocus()
                return False
        else:
            ssh_key_path = self.ssh_key_input.text().strip()
            if not ssh_key_path:
                QMessageBox.warning(self, "验证失败", "请选择SSH私钥文件")
                return False
        
        return True
    
    def _on_save(self):
        if not self._validate():
            return
        
        name = self.name_input.text().strip()
        host = self.host_input.text().strip()
        port = self.port_input.value()
        username = self.username_input.text().strip()
        
        if self.password_radio.isChecked():
            auth_type = 'password'
            password = self.password_input.text()
            
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
        return self._result_config or {}


class ServerConfigDialog(QDialog):
    """服务器配置管理主对话框 - 现代化卡片式布局"""
    
    def __init__(self, parent=None, database: Database = None):
        super().__init__(parent)
        self.db = database
        self.configs = []
        self.selected_config_id = None
        
        self.setWindowTitle("服务器配置管理")
        self.setMinimumSize(900, 600)
        self.setModal(True)
        
        self._setup_ui()
        self._refresh_list()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 主容器使用水平分割布局
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # ===== 左侧：服务器列表 =====
        left_panel = QWidget()
        left_panel.setFixedWidth(380)
        left_panel.setStyleSheet("background-color: #F8FAFC;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(16)
        left_layout.setContentsMargins(20, 20, 20, 20)
        
        # 左侧标题
        left_title = QLabel("服务器列表")
        left_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #1E293B;")
        left_layout.addWidget(left_title)
        
        # 搜索框
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索服务器...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 2px solid #E2E8F0;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #6366F1;
            }
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)
        left_layout.addLayout(search_layout)
        
        # 添加按钮
        self.add_btn = QPushButton("+ 添加服务器")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366F1;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4F46E5;
            }
        """)
        self.add_btn.clicked.connect(self._on_add)
        left_layout.addWidget(self.add_btn)
        
        # 服务器卡片列表区域
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(12)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.addStretch()
        
        self.cards_scroll.setWidget(self.cards_container)
        left_layout.addWidget(self.cards_scroll)
        
        # 空状态（默认隐藏）
        self.empty_state = EmptyStateWidget()
        self.empty_state.add_clicked.connect(self._on_add)
        self.empty_state.hide()
        left_layout.addWidget(self.empty_state)
        
        main_layout.addWidget(left_panel)
        
        # ===== 右侧：详情面板 =====
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color: white;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(20)
        right_layout.setContentsMargins(32, 32, 32, 32)
        
        # 右侧标题
        right_title = QLabel("服务器详情")
        right_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #1E293B;")
        right_layout.addWidget(right_title)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #E2E8F0;")
        line.setFixedHeight(1)
        right_layout.addWidget(line)
        
        # 详情内容区域
        self.detail_stack = QStackedWidget()
        
        # 空详情页面
        empty_detail = QWidget()
        empty_detail_layout = QVBoxLayout(empty_detail)
        empty_detail_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_detail_label = QLabel("请选择左侧服务器查看详情")
        empty_detail_label.setStyleSheet("color: #94A3B8; font-size: 14px;")
        empty_detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_detail_layout.addWidget(empty_detail_label)
        self.detail_stack.addWidget(empty_detail)
        
        # 详情页面
        self.detail_widget = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_widget)
        self.detail_layout.setSpacing(16)
        
        # 详情信息表单
        detail_form = QFormLayout()
        detail_form.setSpacing(12)
        
        self.detail_name = QLabel()
        self.detail_name.setStyleSheet("font-size: 16px; font-weight: 700; color: #1E293B;")
        detail_form.addRow("配置名称", self.detail_name)
        
        self.detail_host = QLabel()
        self.detail_host.setStyleSheet("font-size: 13px; color: #475569;")
        detail_form.addRow("主机地址", self.detail_host)
        
        self.detail_port = QLabel()
        self.detail_port.setStyleSheet("font-size: 13px; color: #475569;")
        detail_form.addRow("SSH端口", self.detail_port)
        
        self.detail_username = QLabel()
        self.detail_username.setStyleSheet("font-size: 13px; color: #475569;")
        detail_form.addRow("用户名", self.detail_username)
        
        self.detail_auth = QLabel()
        self.detail_auth.setStyleSheet("font-size: 13px; color: #475569;")
        detail_form.addRow("认证方式", self.detail_auth)
        
        self.detail_layout.addLayout(detail_form)
        self.detail_layout.addStretch()
        
        # 操作按钮
        detail_btn_layout = QHBoxLayout()
        detail_btn_layout.addStretch()
        
        self.edit_btn = QPushButton("编辑")
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        self.edit_btn.clicked.connect(self._on_edit)
        detail_btn_layout.addWidget(self.edit_btn)
        
        self.test_btn = QPushButton("测试连接")
        self.test_btn.setStyleSheet("""
            QPushButton {
                background-color: #F59E0B;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #D97706;
            }
        """)
        self.test_btn.clicked.connect(self._on_test_connection)
        detail_btn_layout.addWidget(self.test_btn)
        
        self.delete_btn = QPushButton("删除")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #DC2626;
            }
        """)
        self.delete_btn.clicked.connect(self._on_delete)
        detail_btn_layout.addWidget(self.delete_btn)
        
        self.detail_layout.addLayout(detail_btn_layout)
        
        self.detail_stack.addWidget(self.detail_widget)
        right_layout.addWidget(self.detail_stack)
        
        # 底部关闭按钮
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        self.close_btn = QPushButton("关闭")
        self.close_btn.setObjectName("secondary")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 2px solid #E2E8F0;
                color: #475569;
                border-radius: 8px;
                padding: 8px 24px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
                border-color: #CBD5E1;
            }
        """)
        self.close_btn.clicked.connect(self.accept)
        close_layout.addWidget(self.close_btn)
        right_layout.addLayout(close_layout)
        
        main_layout.addWidget(right_panel)
        layout.addWidget(main_widget)
    
    def _refresh_list(self):
        """刷新服务器列表"""
        # 清除现有卡片
        while self.cards_layout.count() > 1:  # 保留stretch
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self.db:
            self._show_empty_state()
            return
        
        try:
            self.configs = self.db.get_server_configs()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取服务器配置失败:\n{str(e)}")
            self.configs = []
            return
        
        if not self.configs:
            self._show_empty_state()
            return
        
        self._show_cards()
        self._apply_search_filter()
    
    def _show_empty_state(self):
        """显示空状态"""
        self.cards_scroll.hide()
        self.empty_state.show()
        self.detail_stack.setCurrentIndex(0)
    
    def _show_cards(self):
        """显示服务器卡片"""
        self.empty_state.hide()
        self.cards_scroll.show()
        
        for config in self.configs:
            card = ServerCard(config)
            card.clicked.connect(self._on_card_clicked)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
            
            if str(config.get('id')) == self.selected_config_id:
                card.set_selected(True)
                self._show_detail(config)
    
    def _on_card_clicked(self, server_id: str):
        """卡片点击事件"""
        self.selected_config_id = server_id
        
        # 更新所有卡片的选中状态
        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ServerCard):
                card = item.widget()
                card.set_selected(card.server_id == server_id)
        
        # 显示详情
        config = self._get_config_by_id(server_id)
        if config:
            self._show_detail(config)
    
    def _show_detail(self, config: dict):
        """显示服务器详情"""
        self.detail_name.setText(config.get('name', '-'))
        self.detail_host.setText(config.get('host', '-'))
        self.detail_port.setText(str(config.get('port', 22)))
        self.detail_username.setText(config.get('username', '-'))
        
        auth_type = config.get('auth_type', 'password')
        auth_text = "密码认证" if auth_type == 'password' else "SSH密钥认证"
        self.detail_auth.setText(auth_text)
        
        self.detail_stack.setCurrentIndex(1)
    
    def _get_config_by_id(self, config_id: str) -> dict:
        """根据ID获取配置"""
        for config in self.configs:
            if str(config.get('id')) == config_id:
                return config
        return {}
    
    def _on_search_changed(self, text: str):
        """搜索过滤"""
        self._apply_search_filter()
    
    def _apply_search_filter(self):
        """应用搜索过滤"""
        search_text = self.search_input.text().lower()
        
        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ServerCard):
                card = item.widget()
                config = card.config
                
                # 匹配名称、主机或用户名
                match = (
                    search_text in config.get('name', '').lower() or
                    search_text in config.get('host', '').lower() or
                    search_text in config.get('username', '').lower()
                )
                
                card.setVisible(match)
    
    def _get_existing_names(self) -> list:
        return [config.get('name', '') for config in self.configs]
    
    def _on_add(self):
        dialog = ServerConfigEditDialog(
            parent=self,
            existing_names=self._get_existing_names()
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config_data = dialog.get_config()
            self._save_to_database(config_data)
    
    def _on_edit(self):
        config = self._get_config_by_id(self.selected_config_id)
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
        config = self._get_config_by_id(self.selected_config_id)
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
                        self.selected_config_id = None
                        self._refresh_list()
                        QMessageBox.information(self, "成功", f"配置 '{name}' 已删除")
                    else:
                        QMessageBox.warning(self, "失败", "删除配置失败")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除配置失败:\n{str(e)}")
    
    def _on_test_connection(self):
        config = self._get_config_by_id(self.selected_config_id)
        if not config:
            return
        
        name = config.get('name', '未知')
        host = config.get('host', '-')
        port = config.get('port', 22)
        username = config.get('username', '-')
        auth_type = config.get('auth_type', 'password')
        
        auth_text = "密码认证" if auth_type == 'password' else "SSH密钥认证"
        
        info_text = (
            f"正在测试连接...\n\n"
            f"配置: {name}\n"
            f"主机: {host}:{port}\n"
            f"用户: {username}\n"
            f"认证: {auth_text}\n\n"
            f"注意: 连接测试功能需要安装 paramiko 库。"
        )
        
        QMessageBox.information(self, "测试连接", info_text)

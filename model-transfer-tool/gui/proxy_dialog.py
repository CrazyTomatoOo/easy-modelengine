#!/usr/bin/env python3
"""
代理配置对话框模块
用于配置 HTTP/HTTPS 代理及镜像源设置
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QMessageBox, QWidget, QGroupBox
)
from PyQt6.QtCore import Qt

from core.database import Database


class ProxyDialog(QDialog):
    """代理配置对话框"""

    # 设置项的 key
    KEY_ENABLE_PROXY = "enable_proxy"
    KEY_PROXY_HTTP = "proxy_http"
    KEY_PROXY_HTTPS = "proxy_https"
    KEY_MIRROR_HF = "mirror_hf"
    KEY_MIRROR_MS = "mirror_ms"

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("代理设置")
        self.setMinimumWidth(480)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._setup_ui()
        self._load_settings()
        self._connect_signals()

    def _setup_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # 标题
        title = QLabel("网络代理配置")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 副标题
        subtitle = QLabel("配置代理服务器和镜像源，以便在受限网络环境中下载模型")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # 代理设置分组
        proxy_group = QGroupBox("代理服务器")
        proxy_layout = QFormLayout(proxy_group)
        proxy_layout.setSpacing(12)
        proxy_layout.setContentsMargins(16, 20, 16, 16)

        # 启用代理复选框
        self.enable_checkbox = QCheckBox("启用代理")
        proxy_layout.addRow(self.enable_checkbox)

        # HTTP 代理
        self.http_input = QLineEdit()
        self.http_input.setPlaceholderText("例如: http://proxy.company.com:8080")
        proxy_layout.addRow("HTTP 代理:", self.http_input)

        # HTTPS 代理
        self.https_input = QLineEdit()
        self.https_input.setPlaceholderText("例如: http://proxy.company.com:8080")
        proxy_layout.addRow("HTTPS 代理:", self.https_input)

        layout.addWidget(proxy_group)

        # 镜像源设置分组
        mirror_group = QGroupBox("镜像源")
        mirror_layout = QFormLayout(mirror_group)
        mirror_layout.setSpacing(12)
        mirror_layout.setContentsMargins(16, 20, 16, 16)

        # HuggingFace 镜像
        self.hf_mirror_input = QLineEdit()
        self.hf_mirror_input.setPlaceholderText("例如: https://hf-mirror.com")
        mirror_layout.addRow("HuggingFace 镜像:", self.hf_mirror_input)

        # ModelScope 镜像
        self.ms_mirror_input = QLineEdit()
        self.ms_mirror_input.setPlaceholderText("例如: https://modelscope.cn")
        mirror_layout.addRow("ModelScope 镜像:", self.ms_mirror_input)

        layout.addWidget(mirror_group)

        # 测试按钮
        self.test_btn = QPushButton("测试代理连接")
        self.test_btn.setObjectName("secondary")
        layout.addWidget(self.test_btn)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.save_btn = QPushButton("保存")
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("secondary")

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()

    def _connect_signals(self):
        """连接信号槽"""
        self.enable_checkbox.toggled.connect(self._on_proxy_toggled)
        self.test_btn.clicked.connect(self._test_proxy)
        self.save_btn.clicked.connect(self._save_settings)
        self.cancel_btn.clicked.connect(self.reject)

    def _on_proxy_toggled(self, enabled: bool):
        """代理启用状态切换"""
        self.http_input.setEnabled(enabled)
        self.https_input.setEnabled(enabled)

    def _load_settings(self):
        """从数据库加载设置"""
        enable_proxy = self.db.get_setting(self.KEY_ENABLE_PROXY, "false")
        self.enable_checkbox.setChecked(enable_proxy.lower() == "true")

        self.http_input.setText(self.db.get_setting(self.KEY_PROXY_HTTP, ""))
        self.https_input.setText(self.db.get_setting(self.KEY_PROXY_HTTPS, ""))
        self.hf_mirror_input.setText(self.db.get_setting(self.KEY_MIRROR_HF, ""))
        self.ms_mirror_input.setText(self.db.get_setting(self.KEY_MIRROR_MS, ""))

        # 根据启用状态更新输入框可用性
        self._on_proxy_toggled(self.enable_checkbox.isChecked())

    def _validate_inputs(self) -> bool:
        """验证输入内容"""
        if not self.enable_checkbox.isChecked():
            return True

        http_proxy = self.http_input.text().strip()
        https_proxy = self.https_input.text().strip()

        if http_proxy and not self._is_valid_proxy_url(http_proxy):
            QMessageBox.warning(self, "输入错误", "HTTP 代理地址格式不正确")
            self.http_input.setFocus()
            return False

        if https_proxy and not self._is_valid_proxy_url(https_proxy):
            QMessageBox.warning(self, "输入错误", "HTTPS 代理地址格式不正确")
            self.https_input.setFocus()
            return False

        return True

    def _is_valid_proxy_url(self, url: str) -> bool:
        """验证代理 URL 格式"""
        if not url:
            return True
        return url.startswith(("http://", "https://", "socks5://"))

    def _save_settings(self):
        """保存设置到数据库"""
        if not self._validate_inputs():
            return

        try:
            self.db.set_setting(
                self.KEY_ENABLE_PROXY,
                "true" if self.enable_checkbox.isChecked() else "false"
            )
            self.db.set_setting(self.KEY_PROXY_HTTP, self.http_input.text().strip())
            self.db.set_setting(self.KEY_PROXY_HTTPS, self.https_input.text().strip())
            self.db.set_setting(self.KEY_MIRROR_HF, self.hf_mirror_input.text().strip())
            self.db.set_setting(self.KEY_MIRROR_MS, self.ms_mirror_input.text().strip())

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存设置时出错: {str(e)}")

    def _test_proxy(self):
        """测试代理连接"""
        if not self.enable_checkbox.isChecked():
            QMessageBox.information(self, "提示", "请先启用代理")
            return

        http_proxy = self.http_input.text().strip()
        https_proxy = self.https_input.text().strip()

        if not http_proxy and not https_proxy:
            QMessageBox.information(self, "提示", "请先填写代理地址")
            return

        # TODO: 实现实际的代理测试逻辑
        info = []
        if http_proxy:
            info.append(f"HTTP 代理: {http_proxy}")
        if https_proxy:
            info.append(f"HTTPS 代理: {https_proxy}")

        QMessageBox.information(
            self,
            "代理测试",
            "代理测试功能即将上线\n\n当前配置:\n" + "\n".join(info)
        )

    def get_proxy_settings(self) -> dict:
        """获取当前代理设置"""
        return {
            "enable_proxy": self.enable_checkbox.isChecked(),
            "proxy_http": self.http_input.text().strip(),
            "proxy_https": self.https_input.text().strip(),
            "mirror_hf": self.hf_mirror_input.text().strip(),
            "mirror_ms": self.ms_mirror_input.text().strip(),
        }

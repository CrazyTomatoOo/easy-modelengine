#!/usr/bin/env python3
"""
代理配置对话框模块
用于配置 HTTP/HTTPS 代理
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QMessageBox, QWidget, QGroupBox
)
from PyQt6.QtCore import Qt

from core.database import Database
from core.proxy_config import ProxyConfig, ProxyValidationError, load, save

class ProxyDialog(QDialog):
    """代理配置对话框"""

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
        subtitle = QLabel("配置代理服务器,以便在受限网络环境中下载模型")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # 代理设置分组
        proxy_group = QGroupBox("代理服务器")
        proxy_layout = QFormLayout(proxy_group)
        proxy_layout.setSpacing(12)
        proxy_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
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
        config = load(self.db)
        self.enable_checkbox.setChecked(config.enable)
        self.http_input.setText(config.http)
        self.https_input.setText(config.https)

        # 根据启用状态更新输入框可用性
        self._on_proxy_toggled(self.enable_checkbox.isChecked())

    def _save_settings(self):
        """保存设置到数据库(校验委托 ProxyConfig)"""
        config = ProxyConfig(
            enable=self.enable_checkbox.isChecked(),
            http=self.http_input.text().strip(),
            https=self.https_input.text().strip(),
        )

        try:
            config.validate()
        except ProxyValidationError as e:
            QMessageBox.warning(self, "输入错误", str(e))
            if e.field == "http":
                self.http_input.setFocus()
            else:
                self.https_input.setFocus()
            return

        try:
            save(self.db, config)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存设置时出错: {str(e)}")

    def _test_proxy(self):
        """测试代理连通性——经代理请求 huggingface.co,如实报告成功/失败。"""
        if not self.enable_checkbox.isChecked():
            QMessageBox.information(self, "提示", "请先启用代理")
            return

        http_proxy = self.http_input.text().strip()
        https_proxy = self.https_input.text().strip()
        if not http_proxy and not https_proxy:
            QMessageBox.information(self, "提示", "请先填写代理地址")
            return

        self.test_btn.setEnabled(False)
        self.test_btn.setText("测试中…")
        info = [f"HTTP 代理: {http_proxy or '未设置'}", f"HTTPS 代理: {https_proxy or '未设置'}"]

        try:
            import requests

            proxies = {"http": http_proxy, "https": http_proxy or https_proxy}
            resp = requests.get(
                "https://huggingface.co",
                proxies=proxies,
                timeout=10,
            )
            if resp.status_code < 500:
                QMessageBox.information(
                    self, "代理测试",
                    "连接成功\n\n" + "\n".join(info) + f"\n状态码: {resp.status_code}",
                )
            else:
                QMessageBox.warning(
                    self, "代理测试失败",
                    "代理可达但目标返回异常状态\n\n" + "\n".join(info) + f"\n状态码: {resp.status_code}",
                )
        except Exception as e:
            QMessageBox.warning(
                self, "代理测试失败",
                f"经代理连接 huggingface.co 失败:\n{e}\n\n请检查代理地址、端口与认证信息。",
            )
        finally:
            self.test_btn.setEnabled(True)
            self.test_btn.setText("测试代理连接")

    def get_proxy_settings(self) -> dict:
        """获取当前代理设置"""
        return {
            "enable_proxy": self.enable_checkbox.isChecked(),
            "proxy_http": self.http_input.text().strip(),
            "proxy_https": self.https_input.text().strip(),
        }

#!/usr/bin/env python3
"""
日志面板模块
"""

from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QFileDialog, QMessageBox
)
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtCore import Qt


class LogPanel(QWidget):
    """日志显示面板"""

    LOG_COLORS = {
        "DEBUG": "#808080",
        "INFO": "#000000",
        "WARNING": "#FF8C00",
        "ERROR": "#CC0000",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 日志显示区域
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.log_edit)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.export_btn = QPushButton("导出日志")
        self.clear_btn = QPushButton("清除")

        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.clear_btn)
        layout.addLayout(btn_layout)

    def _connect_signals(self):
        """连接信号"""
        self.clear_btn.clicked.connect(self._clear_logs)
        self.export_btn.clicked.connect(self._export_logs)

    def _clear_logs(self):
        """清除日志"""
        self.log_edit.clear()

    def _export_logs(self):
        """导出日志到文件"""
        default_name = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", default_name, "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.log_edit.toPlainText())
            QMessageBox.information(self, "导出成功", f"日志已保存到:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"保存日志时出错:\n{str(e)}")

    def append_log(self, message, level="INFO"):
        """追加日志

        Args:
            message: 日志消息
            level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        """
        level = level.upper()
        color = self.LOG_COLORS.get(level, "#000000")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 创建带颜色的文本格式
        char_format = QTextCharFormat()
        char_format.setForeground(QColor(color))

        # 获取当前光标并移动到末尾
        cursor = self.log_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # 插入带格式的日志行
        cursor.setCharFormat(char_format)
        cursor.insertText(f"[{timestamp}] [{level}] {message}\n")

        # 更新光标并自动滚动
        self.log_edit.setTextCursor(cursor)
        self.log_edit.ensureCursorVisible()

    def append_debug(self, message):
        """追加 DEBUG 级别日志"""
        self.append_log(message, "DEBUG")

    def append_info(self, message):
        """追加 INFO 级别日志"""
        self.append_log(message, "INFO")

    def append_warning(self, message):
        """追加 WARNING 级别日志"""
        self.append_log(message, "WARNING")

    def append_error(self, message):
        """追加 ERROR 级别日志"""
        self.append_log(message, "ERROR")

    def get_logs(self):
        """获取所有日志文本"""
        return self.log_edit.toPlainText()

    def set_auto_scroll(self, enabled):
        """设置是否自动滚动到底部"""
        # QTextEdit 的 ensureCursorVisible 已经实现了自动滚动
        # 此方法保留以便外部控制
        pass

    def append_success(self, message):
        """追加成功日志"""
        self.append_log(message, "INFO")
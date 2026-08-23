#!/usr/bin/env python3
"""任务详情对话框——展示每个文件的校验状态(通过/未校验/失败)。"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QLabel,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from gui.state_labels import STAGE_STATE_PRESENTATION


_HINT = ("校验状态说明:通过=已按源校验和比对一致;未校验=该文件无源校验和"
         "(平台未提供哈希,不参与哈希比对);失败=哈希不匹配,损坏文件已删除。")


class TaskDetailsDialog(QDialog):
    """任务详情对话框——文件级校验状态展示。"""

    def __init__(self, db, task_id: str, parent=None):
        super().__init__(parent)
        self._db = db
        self._task_id = task_id
        self.setWindowTitle(f"任务详情 {task_id[:8]}")
        self.resize(720, 420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        hint = QLabel(_HINT)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(hint)

        files = self._db.get_task_files(self._task_id)
        table = QTableWidget(len(files), 5)
        table.setHorizontalHeaderLabels(["文件", "大小(字节)", "校验状态", "源校验和", "实际哈希"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)

        for row, f in enumerate(files):
            pres = STAGE_STATE_PRESENTATION.get(f.get("verify_state"))
            table.setItem(row, 0, QTableWidgetItem(f["file_path"]))
            table.setItem(row, 1, QTableWidgetItem(str(f.get("file_size", ""))))
            state_item = QTableWidgetItem(
                pres.label if pres else (f.get("verify_state") or "—")
            )
            if pres:
                state_item.setForeground(QColor(pres.color))
            table.setItem(row, 2, state_item)
            table.setItem(row, 3, QTableWidgetItem(f.get("expected_hash") or "—"))
            table.setItem(row, 4, QTableWidgetItem(f.get("actual_hash") or "—"))

        layout.addWidget(table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
#!/usr/bin/env python3
"""
任务队列面板模块
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QProgressBar, QLabel, QListWidgetItem, QMenu, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QAction

from gui.state_labels import TASK_STATE_PRESENTATION, Presentation


class TaskItemWidget(QWidget):
    """自定义任务项控件，显示任务信息和进度条"""

    def __init__(self, task_id, model_name, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.model_name = model_name
        self._status_key = "pending"
        self._progress = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        # 任务信息标签
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        self.id_label = QLabel(f"<b>{self.task_id[:8]}</b>")
        self.id_label.setStyleSheet("font-size: 11px;")
        info_layout.addWidget(self.id_label)

        self.model_label = QLabel(self.model_name)
        self.model_label.setStyleSheet("font-size: 12px;")
        self.model_label.setWordWrap(True)
        info_layout.addWidget(self.model_label)

        self.status_label = QLabel(f"状态: {self._status_key}")
        self.status_label.setStyleSheet("font-size: 11px; color: #666;")
        info_layout.addWidget(self.status_label)

        layout.addLayout(info_layout, stretch=2)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedWidth(120)
        layout.addWidget(self.progress_bar)

    def update_status(self, status_key):
        """按枚举 key 更新状态;标签与颜色查呈现注册表。"""
        self._status_key = status_key
        pres = TASK_STATE_PRESENTATION.get(status_key, Presentation(status_key, "#666"))
        self.status_label.setText(f"状态: {pres.label}")
        self.status_label.setStyleSheet(f"font-size: 11px; color: {pres.color};")

    def update_progress(self, progress):
        """更新进度"""
        self._progress = progress
        self.progress_bar.setValue(progress)


class TaskPanel(QWidget):
    """任务队列面板"""

    pause_task = pyqtSignal(str)
    resume_task = pyqtSignal(str)
    cancel_task = pyqtSignal(str)
    retry_task = pyqtSignal(str)
    view_details = pyqtSignal(str)

    # 键控逻辑用的状态集合:一律用枚举 key,不用译文
    _PAUSABLE_KEYS = {"pending", "downloading", "transferring", "verifying"}
    _RESUMABLE_KEYS = {"paused_dl", "paused_tx"}
    _ACTIVE_KEYS = _PAUSABLE_KEYS | {"paused_dl", "paused_tx"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks = {}
        self._filter = "全部"
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 过滤按钮区域
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        filter_layout.setContentsMargins(0, 5, 0, 5)

        self.filter_all_btn = QPushButton("全部")
        self.filter_progress_btn = QPushButton("进行中")
        self.filter_completed_btn = QPushButton("已完成")
        self.filter_failed_btn = QPushButton("失败")

        self.filter_buttons = {
            "全部": self.filter_all_btn,
            "进行中": self.filter_progress_btn,
            "已完成": self.filter_completed_btn,
            "失败": self.filter_failed_btn,
        }

        for btn in self.filter_buttons.values():
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            filter_layout.addWidget(btn)

        self.filter_all_btn.setChecked(True)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # 任务列表
        self.task_list = QListWidget()
        self.task_list.setSpacing(5)
        self.task_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.task_list)

        # 按钮区域
        btn_layout = QHBoxLayout()
        self.pause_all_btn = QPushButton("暂停全部")
        self.cancel_all_btn = QPushButton("取消全部")
        btn_layout.addWidget(self.pause_all_btn)
        btn_layout.addWidget(self.cancel_all_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _connect_signals(self):
        """连接信号"""
        self.task_list.customContextMenuRequested.connect(self._show_context_menu)

        self.filter_all_btn.clicked.connect(lambda: self._set_filter("全部"))
        self.filter_progress_btn.clicked.connect(lambda: self._set_filter("进行中"))
        self.filter_completed_btn.clicked.connect(lambda: self._set_filter("已完成"))
        self.filter_failed_btn.clicked.connect(lambda: self._set_filter("失败"))

        self.pause_all_btn.clicked.connect(self._pause_all)
        self.cancel_all_btn.clicked.connect(self._cancel_all)

    def _set_filter(self, filter_type):
        """设置过滤器"""
        self._filter = filter_type
        self._refresh_list()

    def _get_status_category(self, status_key):
        """获取状态分类(查呈现注册表,key 驱动)"""
        return TASK_STATE_PRESENTATION.get(status_key, Presentation("", "")).category

    def _refresh_list(self):
        """根据过滤器刷新列表显示"""
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget is None:
                continue

            task_id = widget.task_id
            if task_id not in self._tasks:
                continue

            status_key = self._tasks[task_id].get("status", "pending")
            category = self._get_status_category(status_key)

            if self._filter == "全部" or category == self._filter:
                item.setHidden(False)
            else:
                item.setHidden(True)

    def _show_context_menu(self, position):
        """显示右键菜单"""
        item = self.task_list.itemAt(position)
        if item is None:
            return

        widget = self.task_list.itemWidget(item)
        if widget is None:
            return

        task_id = widget.task_id
        status_key = self._tasks.get(task_id, {}).get("status", "pending")

        menu = QMenu(self)

        # 暂停/恢复
        if status_key in self._PAUSABLE_KEYS:
            pause_action = QAction("暂停", self)
            pause_action.triggered.connect(lambda: self.pause_task.emit(task_id))
            menu.addAction(pause_action)
        elif status_key in self._RESUMABLE_KEYS:
            resume_action = QAction("恢复", self)
            resume_action.triggered.connect(lambda: self.resume_task.emit(task_id))
            menu.addAction(resume_action)

        # 取消
        if status_key not in ("completed", "cancelled"):
            cancel_action = QAction("取消", self)
            cancel_action.triggered.connect(lambda: self.cancel_task.emit(task_id))
            menu.addAction(cancel_action)

        menu.addSeparator()

        # 查看详情
        details_action = QAction("查看详情", self)
        details_action.triggered.connect(lambda: self.view_details.emit(task_id))
        menu.addAction(details_action)

        # 重试失败项
        if status_key in ("failed", "cancelled"):
            retry_action = QAction("重试", self)
            retry_action.triggered.connect(lambda: self.retry_task.emit(task_id))
            menu.addAction(retry_action)

        menu.exec(self.task_list.mapToGlobal(position))

    def add_task(self, task_id, model_name):
        """添加任务"""
        self._tasks[task_id] = {
            "model_name": model_name,
            "status": "pending",
            "progress": 0,
        }

        # 创建自定义任务项
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 80))
        item.setData(Qt.ItemDataRole.UserRole, task_id)

        widget = TaskItemWidget(task_id, model_name)
        self.task_list.addItem(item)
        self.task_list.setItemWidget(item, widget)

        self._refresh_list()

    def update_task_status(self, task_id, status_key):
        """更新任务状态(入参为枚举 key,展示查呈现注册表)"""
        if task_id not in self._tasks:
            return

        self._tasks[task_id]["status"] = status_key

        # 找到对应的 widget 并更新
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget is not None and widget.task_id == task_id:
                widget.update_status(status_key)
                break

        self._refresh_list()

    def update_task_progress(self, task_id, progress):
        """更新任务进度"""
        if task_id not in self._tasks:
            return

        self._tasks[task_id]["progress"] = progress

        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget is not None and widget.task_id == task_id:
                widget.update_progress(progress)
                break

    def remove_task(self, task_id):
        """移除任务"""
        if task_id not in self._tasks:
            return

        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget is not None and widget.task_id == task_id:
                self.task_list.takeItem(i)
                break

        del self._tasks[task_id]

    def _pause_all(self):
        """暂停所有可暂停的任务"""
        for task_id, task_info in self._tasks.items():
            if task_info["status"] in self._PAUSABLE_KEYS:
                self.pause_task.emit(task_id)

    def _cancel_all(self):
        """取消所有未完成的任务"""
        reply = QMessageBox.question(
            self, "确认取消", "确定要取消所有未完成的任务吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for task_id, task_info in list(self._tasks.items()):
                if task_info["status"] not in ("completed", "cancelled"):
                    self.cancel_task.emit(task_id)

    def clear_completed(self):
        """清除已完成的任务"""
        for task_id in list(self._tasks.keys()):
            if self._tasks[task_id]["status"] == "completed":
                self.remove_task(task_id)

    def get_task_count(self):
        """获取任务总数"""
        return len(self._tasks)

    def get_active_task_count(self):
        """获取进行中任务数"""
        return sum(
            1 for task in self._tasks.values()
            if task["status"] in self._ACTIVE_KEYS
        )

    def get_failed_task_count(self):
        """获取失败任务数"""
        return sum(
            1 for task in self._tasks.values()
            if task["status"] in ("failed", "cancelled")
        )
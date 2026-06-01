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


class TaskItemWidget(QWidget):
    """自定义任务项控件，显示任务信息和进度条"""

    def __init__(self, task_id, model_name, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.model_name = model_name
        self._status = "等待中"
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

        self.status_label = QLabel(f"状态: {self._status}")
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

    def update_status(self, status):
        """更新状态"""
        self._status = status
        self.status_label.setText(f"状态: {status}")

        # 根据状态设置颜色
        color_map = {
            "等待中": "#666",
            "下载中": "#0066cc",
            "传输中": "#0066cc",
            "校验中": "#0066cc",
            "已暂停": "#ff9900",
            "已完成": "#009900",
            "失败": "#cc0000",
            "已取消": "#999",
        }
        color = color_map.get(status, "#666")
        self.status_label.setStyleSheet(f"font-size: 11px; color: {color};")

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

    def _get_status_category(self, status):
        """获取状态分类"""
        progress_statuses = ["等待中", "下载中", "传输中", "校验中", "已暂停"]
        completed_statuses = ["已完成"]
        failed_statuses = ["失败", "已取消"]

        if status in progress_statuses:
            return "进行中"
        elif status in completed_statuses:
            return "已完成"
        elif status in failed_statuses:
            return "失败"
        return "全部"

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

            status = self._tasks[task_id].get("status", "等待中")
            category = self._get_status_category(status)

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
        status = self._tasks.get(task_id, {}).get("status", "等待中")

        menu = QMenu(self)

        # 暂停/恢复
        if status in ["等待中", "下载中", "传输中", "校验中"]:
            pause_action = QAction("暂停", self)
            pause_action.triggered.connect(lambda: self.pause_task.emit(task_id))
            menu.addAction(pause_action)
        elif status == "已暂停":
            resume_action = QAction("恢复", self)
            resume_action.triggered.connect(lambda: self.resume_task.emit(task_id))
            menu.addAction(resume_action)

        # 取消
        if status not in ["已完成", "已取消"]:
            cancel_action = QAction("取消", self)
            cancel_action.triggered.connect(lambda: self.cancel_task.emit(task_id))
            menu.addAction(cancel_action)

        menu.addSeparator()

        # 查看详情
        details_action = QAction("查看详情", self)
        details_action.triggered.connect(lambda: self.view_details.emit(task_id))
        menu.addAction(details_action)

        # 重试失败项
        if status in ["失败", "已取消"]:
            retry_action = QAction("重试", self)
            retry_action.triggered.connect(lambda: self.retry_task.emit(task_id))
            menu.addAction(retry_action)

        menu.exec(self.task_list.mapToGlobal(position))

    def add_task(self, task_id, model_name):
        """添加任务"""
        self._tasks[task_id] = {
            "model_name": model_name,
            "status": "等待中",
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

    def update_task_status(self, task_id, status):
        """更新任务状态"""
        if task_id not in self._tasks:
            return

        self._tasks[task_id]["status"] = status

        # 找到对应的 widget 并更新
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget is not None and widget.task_id == task_id:
                widget.update_status(status)
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
            if task_info["status"] in ["等待中", "下载中", "传输中", "校验中"]:
                self.pause_task.emit(task_id)

    def _cancel_all(self):
        """取消所有未完成的任务"""
        reply = QMessageBox.question(
            self, "确认取消", "确定要取消所有未完成的任务吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for task_id, task_info in list(self._tasks.items()):
                if task_info["status"] not in ["已完成", "已取消"]:
                    self.cancel_task.emit(task_id)

    def clear_completed(self):
        """清除已完成的任务"""
        for task_id in list(self._tasks.keys()):
            if self._tasks[task_id]["status"] == "已完成":
                self.remove_task(task_id)

    def get_task_count(self):
        """获取任务总数"""
        return len(self._tasks)

    def get_active_task_count(self):
        """获取进行中任务数"""
        active_statuses = ["等待中", "下载中", "传输中", "校验中", "已暂停"]
        return sum(
            1 for task in self._tasks.values()
            if task["status"] in active_statuses
        )

    def get_failed_task_count(self):
        """获取失败任务数"""
        return sum(
            1 for task in self._tasks.values()
            if task["status"] in ["失败", "已取消"]
        )

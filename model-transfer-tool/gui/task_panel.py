#!/usr/bin/env python3
"""
任务队列面板模块
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QProgressBar, QLabel, QListWidgetItem, QMenu, QMessageBox, QSizePolicy,
    QStackedWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QAction

from gui.state_labels import TASK_STATE_PRESENTATION, Presentation


class TaskItemWidget(QWidget):
    """自定义任务项控件,显示任务信息、类型徽标与进度条"""

    # 任务类型徽标:文字与底色(与 state_labels 调性一致)
    BADGE_STYLE = {
        "download_only": ("下载", "#2563EB"),
        "transfer_only": ("上传", "#EA580C"),
        "full_pipeline": ("下载+上传", "#6D28D9"),
    }

    def __init__(self, task_id, model_name, task_type="download_only", parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.model_name = model_name
        self.task_type = task_type
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

        id_row = QHBoxLayout()
        id_row.setSpacing(6)
        self.id_label = QLabel(f"<b>{self.task_id[:8]}</b>")
        self.id_label.setStyleSheet("font-size: 11px;")
        id_row.addWidget(self.id_label)

        badge_text, badge_color = self.BADGE_STYLE.get(
            self.task_type, ("下载", "#2563EB"))
        self.type_badge = QLabel(badge_text)
        self.type_badge.setStyleSheet(
            f"background-color: {badge_color}; color: white; "
            "border-radius: 8px; padding: 1px 8px; font-size: 10px;"
        )
        id_row.addWidget(self.type_badge)
        id_row.addStretch()
        info_layout.addLayout(id_row)

        self.model_label = QLabel(self.model_name)
        self.model_label.setStyleSheet("font-size: 12px;")
        self.model_label.setWordWrap(True)
        self.model_label.setToolTip(self.model_name)
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
        self._type_filter = "全部类型"
        self._setup_ui()
        self._connect_signals()
        self._update_empty_state()

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
            # 紧凑 padding + 均分宽度:全局按钮样式(10px 20px)会把四个筛选按钮文字挤出面板
            btn.setStyleSheet("QPushButton { padding: 6px 8px; min-height: 28px; }")
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            filter_layout.addWidget(btn)

        self.filter_all_btn.setChecked(True)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # 类型筛选行:按任务类型(下载/上传)过滤
        type_layout = QHBoxLayout()
        type_layout.setSpacing(8)
        type_layout.setContentsMargins(0, 0, 0, 0)
        self.type_all_btn = QPushButton("全部类型")
        self.type_download_btn = QPushButton("下载")
        self.type_transfer_btn = QPushButton("上传")

        self.type_buttons = {
            "全部类型": self.type_all_btn,
            "下载": self.type_download_btn,
            "上传": self.type_transfer_btn,
        }
        for btn in self.type_buttons.values():
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setStyleSheet("QPushButton { padding: 4px 10px; min-height: 24px; }")
            type_layout.addWidget(btn)
        self.type_all_btn.setChecked(True)
        type_layout.addStretch()
        layout.addLayout(type_layout)

        # 任务列表 + 空态(无任务时给指引,不留白板)
        self.list_stack = QStackedWidget()
        self.task_list = QListWidget()
        self.task_list.setSpacing(5)
        self.task_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_stack.addWidget(self.task_list)

        self.empty_label = QLabel("暂无任务\n从左侧「模型下载」创建第一个任务")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #64748B; font-size: 13px;")
        self.list_stack.addWidget(self.empty_label)
        layout.addWidget(self.list_stack)

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

        self.type_all_btn.clicked.connect(lambda: self._set_type_filter("全部类型"))
        self.type_download_btn.clicked.connect(lambda: self._set_type_filter("下载"))
        self.type_transfer_btn.clicked.connect(lambda: self._set_type_filter("上传"))

        self.pause_all_btn.clicked.connect(self._pause_all)
        self.cancel_all_btn.clicked.connect(self._cancel_all)

    def _set_filter(self, filter_type):
        """设置状态过滤器"""
        self._filter = filter_type
        self._refresh_list()

    def _set_type_filter(self, filter_type):
        """设置类型过滤器(下载/上传)——徽标维度的筛选,状态筛选之上叠加。"""
        self._type_filter = filter_type
        self._refresh_list()

    def _type_matches(self, task_type: str) -> bool:
        if self._type_filter == "全部类型":
            return True
        if self._type_filter == "下载":
            return task_type in ("download_only", "full_pipeline")
        if self._type_filter == "上传":
            return task_type in ("transfer_only", "full_pipeline")
        return True

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

            task_type = self._tasks[task_id].get("task_type", "download_only")
            status_ok = self._filter == "全部" or category == self._filter
            type_ok = self._type_matches(task_type)
            item.setHidden(not (status_ok and type_ok))

        self._update_empty_state()

    def _update_empty_state(self):
        """无可见任务时显示空态指引(任务可存在但被过滤器隐藏)。"""
        visible = sum(
            1 for i in range(self.task_list.count())
            if not self.task_list.item(i).isHidden()
        )
        if visible == 0:
            self.empty_label.setText("暂无任务" if not self._tasks else "当前筛选下无任务")
            self.list_stack.setCurrentIndex(1)
        else:
            self.list_stack.setCurrentIndex(0)

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

        # 取消(破坏性操作,需确认)
        if status_key not in ("completed", "cancelled"):
            cancel_action = QAction("取消", self)
            cancel_action.triggered.connect(lambda: self._confirm_cancel(task_id))
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

    def _confirm_cancel(self, task_id: str) -> None:
        """取消属破坏性操作(丢弃未完成部分),必须确认——与「取消全部」一致。"""
        reply = QMessageBox.question(
            self, "确认取消", "确定要取消该任务吗?已下载的部分会保留。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.cancel_task.emit(task_id)

    def add_task(self, task_id, model_name, task_type="download_only"):
        """添加任务——task_type 为 TaskType.value,驱动类型徽标与筛选。"""
        self._tasks[task_id] = {
            "model_name": model_name,
            "status": "pending",
            "progress": 0,
            "task_type": task_type,
        }

        # 创建自定义任务项
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 80))
        item.setData(Qt.ItemDataRole.UserRole, task_id)

        widget = TaskItemWidget(task_id, model_name, task_type=task_type)
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
        self._update_empty_state()

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
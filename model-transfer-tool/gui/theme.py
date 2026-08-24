"""
现代化主题样式管理器
支持深色/浅色模式，提供统一的视觉风格
"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


class ThemeManager:
    """主题管理器"""
    
    # 配色方案
    COLORS = {
        "primary": "#6366F1",          # 靛紫色 - 主色调
        "primary_hover": "#4F46E5",    # 深靛紫 - 悬停
        "primary_light": "#E0E7FF",    # 浅靛紫 - 背景
        "success": "#10B981",          # 翠绿 - 成功
        "warning": "#F59E0B",          # 琥珀 - 警告
        "danger": "#EF4444",           # 红色 - 错误
        "info": "#3B82F6",             # 蓝色 - 信息
        
        # 深色模式背景
        "dark_bg": "#0F172A",          # 深蓝灰 - 主背景
        "dark_surface": "#1E293B",     # 表面背景
        "dark_card": "#334155",        # 卡片背景
        "dark_border": "#475569",      # 边框
        "dark_text": "#F1F5F9",        # 主文本
        "dark_text_secondary": "#94A3B8",  # 次要文本
        
        # 浅色模式背景
        "light_bg": "#F8FAFC",         # 浅灰白 - 主背景
        "light_surface": "#FFFFFF",    # 白色表面
        "light_card": "#F1F5F9",       # 卡片背景
        "light_border": "#E2E8F0",     # 边框
        "light_text": "#1E293B",       # 主文本
        "light_text_secondary": "#64748B",  # 次要文本
    }
    
    def __init__(self, dark_mode: bool = False):
        self.dark_mode = dark_mode
        self.colors = self.COLORS
    
    def get_stylesheet(self) -> str:
        """获取完整样式表"""
        if self.dark_mode:
            return self._get_dark_stylesheet()
        return self._get_light_stylesheet()
    
    def _get_dark_stylesheet(self) -> str:
        """深色模式样式"""
        c = self.colors
        return f"""
        /* 全局样式 */
        QWidget {{
            background-color: {c['dark_bg']};
            color: {c['dark_text']};
            font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            font-size: 13px;
            border: none;
        }}
        
        /* 主窗口 */
        QMainWindow {{
            background-color: {c['dark_bg']};
        }}
        
        /* 按钮样式 */
        QPushButton {{
            background-color: {c['primary']};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 6px 12px;
            font-weight: 600;
            min-height: 32px;
        }}
        
        QPushButton:hover {{
            background-color: {c['primary_hover']};
        }}
        
        QPushButton:pressed {{
            background-color: {c['primary']};
            padding: 11px 19px 9px 21px;
        }}

        QPushButton:focus {{
            background-color: {c['primary_hover']};
        }}
        
        QPushButton:disabled {{
            background-color: {c['dark_card']};
            color: {c['dark_text_secondary']};
        }}
        
        QPushButton#secondary {{
            background-color: transparent;
            border: 2px solid {c['dark_border']};
            color: {c['dark_text']};
        }}
        
        QPushButton#secondary:hover {{
            background-color: {c['dark_card']};
            border-color: {c['primary']};
        }}
        
        /* 输入框 */
        QLineEdit, QComboBox {{
            background-color: {c['dark_surface']};
            border: 2px solid {c['dark_border']};
            border-radius: 8px;
            padding: 8px 12px;
            color: {c['dark_text']};
            min-height: 20px;
        }}
        
        QLineEdit:focus, QComboBox:focus {{
            border-color: {c['primary']};
        }}
        
        QLineEdit:disabled, QComboBox:disabled {{
            background-color: {c['dark_card']};
            color: {c['dark_text_secondary']};
        }}
        
        /* 组合框下拉 */
        QComboBox::drop-down {{
            border: none;
            width: 30px;
        }}
        
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {c['dark_text_secondary']};
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {c['dark_surface']};
            border: 2px solid {c['dark_border']};
            border-radius: 8px;
            selection-background-color: {c['primary']};
        }}
        
        /* 单选/复选按钮 */
        QRadioButton, QCheckBox {{
            spacing: 8px;
            color: {c['dark_text']};
        }}
        
        QRadioButton::indicator, QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 2px solid {c['dark_border']};
            background-color: {c['dark_surface']};
        }}
        
        QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
            background-color: {c['primary']};
            border-color: {c['primary']};
        }}
        
        /* 分组框 */
        QGroupBox {{
            background-color: {c['dark_surface']};
            border: 2px solid {c['dark_border']};
            border-radius: 12px;
            margin-top: 12px;
            padding-top: 16px;
            padding: 16px;
            font-weight: 600;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 16px;
            padding: 0 8px;
            color: {c['primary']};
        }}
        
        /* 标签 */
        QLabel {{
            color: {c['dark_text']};
        }}
        
        QLabel#title {{
            font-size: 18px;
            font-weight: 700;
            color: {c['dark_text']};
        }}
        
        QLabel#subtitle {{
            font-size: 14px;
            color: {c['dark_text_secondary']};
        }}
        
        /* 进度条 */
        QProgressBar {{
            background-color: {c['dark_card']};
            border: none;
            border-radius: 6px;
            height: 12px;
            text-align: center;
        }}
        
        QProgressBar::chunk {{
            background-color: {c['primary']};
            border-radius: 6px;
        }}
        
        /* 树形控件 */
        QTreeWidget {{
            background-color: {c['dark_surface']};
            border: 2px solid {c['dark_border']};
            border-radius: 8px;
            outline: none;
        }}

        QTreeWidget:focus, QListWidget:focus {{
            border-color: {c['primary']};
        }}
        
        QTreeWidget::item {{
            padding: 6px;
            border-radius: 4px;
        }}
        
        QTreeWidget::item:selected {{
            background-color: {c['primary']};
        }}
        
        QTreeWidget::item:hover {{
            background-color: {c['dark_card']};
        }}
        
        QHeaderView::section {{
            background-color: {c['dark_card']};
            color: {c['dark_text']};
            padding: 8px;
            border: none;
            font-weight: 600;
        }}
        
        /* 列表控件 */
        QListWidget {{
            background-color: {c['dark_surface']};
            border: 2px solid {c['dark_border']};
            border-radius: 8px;
            outline: none;
        }}

        /* 侧导航栏 */
        QListWidget#navList {{
            background-color: {c['dark_surface']};
            border: none;
            border-right: 1px solid {c['dark_border']};
            border-radius: 0;
            outline: none;
        }}
        QListWidget#navList::item {{
            padding: 10px 16px;
            margin: 0;
            border: none;
            border-radius: 0;
        }}
        QListWidget#navList::item:hover {{
            background-color: {c['dark_card']};
        }}
        QListWidget#navList::item:selected {{
            background-color: {c['primary']};
            color: white;
        }}
        
        QListWidget::item {{
            padding: 8px;
            border-radius: 6px;
            margin: 2px 4px;
        }}
        
        QListWidget::item:selected {{
            background-color: {c['primary']};
        }}
        
        QListWidget::item:hover {{
            background-color: {c['dark_card']};
        }}
        
        /* 文本编辑 */
        QTextEdit {{
            background-color: {c['dark_surface']};
            border: 2px solid {c['dark_border']};
            border-radius: 8px;
            padding: 8px;
            color: {c['dark_text']};
        }}
        
        /* 状态栏 */
        QStatusBar {{
            background-color: {c['dark_surface']};
            border-top: 2px solid {c['dark_border']};
            color: {c['dark_text_secondary']};
        }}
        
        /* 分隔线 */
        QFrame[frameShape="4"] {{
            color: {c['dark_border']};
        }}
        
        /* 滚动条 */
        QScrollBar:vertical {{
            background-color: {c['dark_bg']};
            width: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {c['dark_border']};
            border-radius: 6px;
            min-height: 30px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {c['dark_text_secondary']};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        /* 消息框 */
        QMessageBox {{
            background-color: {c['dark_bg']};
        }}
        
        QMessageBox QLabel {{
            color: {c['dark_text']};
        }}
        """
    
    def _get_light_stylesheet(self) -> str:
        """浅色模式样式"""
        c = self.colors
        return f"""
        /* 全局样式 */
        QWidget {{
            background-color: {c['light_bg']};
            color: {c['light_text']};
            font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            font-size: 13px;
            border: none;
        }}
        
        QMainWindow {{
            background-color: {c['light_bg']};
        }}
        
        QPushButton {{
            background-color: {c['primary']};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 6px 12px;
            font-weight: 600;
            min-height: 32px;
        }}
        
        QPushButton:hover {{
            background-color: {c['primary_hover']};
        }}
        
        QPushButton:pressed {{
            background-color: {c['primary']};
            padding: 11px 19px 9px 21px;
        }}

        QPushButton:focus {{
            background-color: {c['primary_hover']};
        }}
        
        QPushButton:disabled {{
            background-color: {c['light_border']};
            color: {c['light_text_secondary']};
        }}
        
        QPushButton#secondary {{
            background-color: transparent;
            border: 2px solid {c['light_border']};
            color: {c['light_text']};
        }}
        
        QPushButton#secondary:hover {{
            background-color: {c['light_card']};
            border-color: {c['primary']};
        }}
        
        QLineEdit, QComboBox {{
            background-color: {c['light_surface']};
            border: 2px solid {c['light_border']};
            border-radius: 8px;
            padding: 8px 12px;
            color: {c['light_text']};
            min-height: 20px;
        }}
        
        QLineEdit:focus, QComboBox:focus {{
            border-color: {c['primary']};
        }}
        
        QLineEdit:disabled, QComboBox:disabled {{
            background-color: {c['light_card']};
            color: {c['light_text_secondary']};
        }}
        
        QComboBox::drop-down {{
            border: none;
            width: 30px;
        }}
        
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {c['light_text_secondary']};
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {c['light_surface']};
            border: 2px solid {c['light_border']};
            border-radius: 8px;
            selection-background-color: {c['primary']};
        }}
        
        QRadioButton, QCheckBox {{
            spacing: 8px;
            color: {c['light_text']};
        }}
        
        QRadioButton::indicator, QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 2px solid {c['light_border']};
            background-color: {c['light_surface']};
        }}
        
        QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
            background-color: {c['primary']};
            border-color: {c['primary']};
        }}
        
        QGroupBox {{
            background-color: {c['light_surface']};
            border: 2px solid {c['light_border']};
            border-radius: 12px;
            margin-top: 12px;
            padding-top: 16px;
            padding: 16px;
            font-weight: 600;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 16px;
            padding: 0 8px;
            color: {c['primary']};
        }}
        
        QLabel {{
            color: {c['light_text']};
        }}
        
        QLabel#title {{
            font-size: 18px;
            font-weight: 700;
            color: {c['light_text']};
        }}
        
        QLabel#subtitle {{
            font-size: 14px;
            color: {c['light_text_secondary']};
        }}
        
        QProgressBar {{
            background-color: {c['light_card']};
            border: none;
            border-radius: 6px;
            height: 12px;
            text-align: center;
        }}
        
        QProgressBar::chunk {{
            background-color: {c['primary']};
            border-radius: 6px;
        }}
        
        QTreeWidget {{
            background-color: {c['light_surface']};
            border: 2px solid {c['light_border']};
            border-radius: 8px;
            outline: none;
        }}

        QTreeWidget:focus, QListWidget:focus {{
            border-color: {c['primary']};
        }}
        
        QTreeWidget::item {{
            padding: 6px;
            border-radius: 4px;
        }}
        
        QTreeWidget::item:selected {{
            background-color: {c['primary']};
        }}
        
        QTreeWidget::item:hover {{
            background-color: {c['light_card']};
        }}
        
        QHeaderView::section {{
            background-color: {c['light_card']};
            color: {c['light_text']};
            padding: 8px;
            border: none;
            font-weight: 600;
        }}
        
        QListWidget {{
            background-color: {c['light_surface']};
            border: 2px solid {c['light_border']};
            border-radius: 8px;
            outline: none;
        }}

        /* 侧导航栏 */
        QListWidget#navList {{
            background-color: {c['light_surface']};
            border: none;
            border-right: 1px solid {c['light_border']};
            border-radius: 0;
            outline: none;
        }}
        QListWidget#navList::item {{
            padding: 10px 16px;
            margin: 0;
            border: none;
            border-radius: 0;
        }}
        QListWidget#navList::item:hover {{
            background-color: {c['light_card']};
        }}
        QListWidget#navList::item:selected {{
            background-color: {c['primary']};
            color: white;
        }}
        
        QListWidget::item {{
            padding: 8px;
            border-radius: 6px;
            margin: 2px 4px;
        }}
        
        QListWidget::item:selected {{
            background-color: {c['primary']};
        }}
        
        QListWidget::item:hover {{
            background-color: {c['light_card']};
        }}
        
        QTextEdit {{
            background-color: {c['light_surface']};
            border: 2px solid {c['light_border']};
            border-radius: 8px;
            padding: 8px;
            color: {c['light_text']};
        }}
        
        QStatusBar {{
            background-color: {c['light_surface']};
            border-top: 2px solid {c['light_border']};
            color: {c['light_text_secondary']};
        }}
        
        QFrame[frameShape="4"] {{
            color: {c['light_border']};
        }}
        
        QScrollBar:vertical {{
            background-color: {c['light_bg']};
            width: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {c['light_border']};
            border-radius: 6px;
            min-height: 30px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {c['light_text_secondary']};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        QMessageBox {{
            background-color: {c['light_bg']};
        }}
        
        QMessageBox QLabel {{
            color: {c['light_text']};
        }}
        """
    
    def apply_theme(self, app: QApplication):
        """应用主题到应用"""
        app.setStyleSheet(self.get_stylesheet())
    
    def toggle_theme(self, app: QApplication):
        """切换主题"""
        self.dark_mode = not self.dark_mode
        app.setStyleSheet(self.get_stylesheet())
        return self.dark_mode

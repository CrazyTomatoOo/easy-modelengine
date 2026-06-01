#!/usr/bin/env python3
"""
模型下载与远程传输工具
主入口文件
"""

import sys
from pathlib import Path


def setup_environment() -> None:
    """创建应用所需的目录结构"""
    base_dir = Path(__file__).parent
    dirs = ["config", "data", "cache", "logs"]
    for dir_name in dirs:
        (base_dir / dir_name).mkdir(parents=True, exist_ok=True)


def main() -> int:
    """主函数，初始化并运行应用"""
    setup_environment()
    
    try:
        from PyQt6.QtWidgets import QApplication, QWidget
        from gui.main_window import MainWindow
    except ImportError as e:
        print(f"导入错误: {e}")
        print("请确保已安装依赖: pip install -r requirements.txt")
        return 1
    
    app = QApplication(sys.argv)
    
    try:
        window = MainWindow()
    except Exception:
        window = QWidget()
        window.setWindowTitle("模型下载与远程传输工具")
        window.resize(800, 600)
    
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

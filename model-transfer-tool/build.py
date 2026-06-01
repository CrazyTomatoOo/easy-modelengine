#!/usr/bin/env python3
"""
PyInstaller 打包脚本
"""

import PyInstaller.__main__
import os


def build():
    """构建可执行文件"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(base_dir, "main.py")
    
    PyInstaller.__main__.run([
        main_script,
        "--name=模型传输工具",
        "--windowed",
        "--onefile",
        "--clean",
        f"--distpath={os.path.join(base_dir, 'dist')}",
        f"--workpath={os.path.join(base_dir, 'build')}",
        f"--specpath={base_dir}",
    ])


if __name__ == "__main__":
    build()

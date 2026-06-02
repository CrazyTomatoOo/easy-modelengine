#!/usr/bin/env python3
"""
PyInstaller 打包脚本
"""

import PyInstaller.__main__
import os
import shutil
import glob


def clean_build_artifacts():
    """清理上一次构建残留的文件和目录"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 要清理的目录
    dirs_to_clean = [
        os.path.join(base_dir, 'dist'),
        os.path.join(base_dir, 'build'),
    ]
    
    # 要清理的文件模式
    patterns_to_clean = [
        os.path.join(base_dir, '*.spec'),
        os.path.join(base_dir, '**', '__pycache__'),
        os.path.join(base_dir, '**', '*.pyc'),
        os.path.join(base_dir, '**', '*.pyo'),
    ]
    
    print("正在清理上一次构建残留...")
    
    # 清理目录
    for dir_path in dirs_to_clean:
        if os.path.exists(dir_path):
            print(f"  删除目录: {dir_path}")
            shutil.rmtree(dir_path)
    
    # 清理文件
    for pattern in patterns_to_clean:
        for file_path in glob.glob(pattern, recursive=True):
            if os.path.exists(file_path):
                if os.path.isdir(file_path):
                    print(f"  删除目录: {file_path}")
                    shutil.rmtree(file_path)
                else:
                    print(f"  删除文件: {file_path}")
                    os.remove(file_path)
    
    print("清理完成。")


def build():
    """构建可执行文件"""
    # 先清理上一次构建残留
    clean_build_artifacts()
    
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

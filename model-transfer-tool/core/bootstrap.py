"""bootstrap —— 应用启动的单一入口(spec #23)。

目录创建、主题应用、主窗口构造集中于此;启动失败不再被空白窗掩盖,
异常向上传播,由 main() 转为非零退出与清晰报错。
"""

from pathlib import Path

APP_DIRS = ("config", "data", "cache", "logs")


def ensure_dirs(base_dir: Path) -> list[Path]:
    """创建应用所需目录(幂等),返回目录列表。"""
    created = []
    for name in APP_DIRS:
        path = Path(base_dir) / name
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)
    return created


def bootstrap(base_dir: Path, app_args=None):
    """完整启动序列:目录 → Qt 应用 → 主题 → 主窗口。失败向上传播。"""
    ensure_dirs(base_dir)

    from PyQt6.QtWidgets import QApplication

    app = QApplication(app_args if app_args is not None else sys_argv())

    from gui.theme import ThemeManager

    ThemeManager(dark_mode=False).apply_theme(app)

    from gui.main_window import MainWindow

    window = MainWindow(app=app)
    window.show()
    # 防 GC:window 是局部变量,返回后引用归零会导致 C++ 窗口被销毁,
    # 进程只剩空事件循环(窗口闪现即灭)。挂到 app 上随其存活。
    app._main_window = window
    return app


def sys_argv() -> list:
    """Qt 需要的 argv;非空以避免 QApplication 拒绝空列表。"""
    import sys

    return list(sys.argv) or [""]
#!/usr/bin/env python3
"""
模型下载与远程传输工具
主入口文件
"""

import sys
from pathlib import Path

from core.bootstrap import bootstrap


def main() -> int:
    """初始化并运行应用;启动失败以非零退出 + 清晰报错结束(无空白窗否决)。"""
    try:
        app = bootstrap(Path(__file__).parent)
        return app.exec()
    except ImportError as e:
        print(f"导入错误: {e}", file=sys.stderr)
        print("请确保已安装依赖: pip install -r requirements.txt", file=sys.stderr)
        return 1
    except Exception:
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
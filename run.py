"""便捷入口 — 用法: python run.py <command> [args]"""

import sys
import os
from pathlib import Path

# 自动切换到虚拟环境（如果不是在venv中运行）
def ensure_venv():
    """确保在虚拟环境中运行"""
    if sys.prefix == sys.base_prefix:
        # 不在虚拟环境中，尝试自动激活
        venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            # 使用虚拟环境的 Python 重新执行脚本
            os.execv(str(venv_python), [str(venv_python)] + sys.argv)
        else:
            print("警告: 未找到虚拟环境，请先运行: python -m venv .venv")
            sys.exit(1)

ensure_venv()

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.cli import cli

if __name__ == "__main__":
    cli()

#!/usr/bin/env python3
"""
开发环境快速搭建脚本
用法: python scripts/setup.py [--dev]
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd, **kwargs):
    """运行命令并打印结果。"""
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=ROOT, **kwargs)
    return result.returncode == 0


def check_python():
    """检查 Python 版本。"""
    v = sys.version_info
    if v < (3, 10):
        print(f"❌ Python >= 3.10 required, got {v.major}.{v.minor}")
        return False
    print(f"✓ Python {v.major}.{v.minor}.{v.micro}")
    return True


def create_venv():
    """创建虚拟环境。"""
    venv_dir = ROOT / ".venv"
    if venv_dir.exists():
        print("✓ 虚拟环境已存在")
        return True

    print("📦 创建虚拟环境...")
    return run(f'"{sys.executable}" -m venv .venv')


def install_deps(dev=False):
    """安装依赖。"""
    if os.name == "nt":
        pip = str(ROOT / ".venv" / "Scripts" / "pip.exe")
    else:
        pip = str(ROOT / ".venv" / "bin" / "pip")

    print("📦 安装依赖...")
    if not run(f'"{pip}" install -r requirements.txt'):
        return False

    if dev:
        print("📦 安装开发依赖...")
        run(f'"{pip}" install pytest ruff')

    return True


def create_env_file():
    """创建 .env 文件（如果不存在）。"""
    env_file = ROOT / ".env"
    if env_file.exists():
        print("✓ .env 文件已存在")
        return

    print("📝 创建 .env 文件...")
    env_content = """# 环境变量配置
ANTHROPIC_AUTH_TOKEN=your_api_key_here
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=Lin
MYSQL_PASSWORD=your_password_here
"""
    env_file.write_text(env_content, encoding="utf-8")
    print("  请编辑 .env 文件填入实际配置")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="开发环境搭建")
    parser.add_argument("--dev", action="store_true", help="安装开发依赖（pytest, ruff）")
    args = parser.parse_args()

    print("🚀 个人知识库系统 — 开发环境搭建")
    print("=" * 50)
    print()

    steps = [
        ("检查 Python 版本", check_python),
        ("创建虚拟环境", create_venv),
        ("安装依赖", lambda: install_deps(args.dev)),
        ("创建 .env", create_env_file),
    ]

    for name, func in steps:
        print(f"
[{name}]")
        if not func():
            print(f"
❌ 在 "{name}" 步骤失败")
            sys.exit(1)

    print()
    print("=" * 50)
    print("✅ 环境搭建完成！")
    print()
    print("下一步:")
    print("  1. 编辑 .env 文件，填入 API Key 和 MySQL 密码")
    print("  2. 运行健康检查: python run.py check")
    print("  3. 导入文档: python run.py add your_file.pdf")


if __name__ == "__main__":
    main()

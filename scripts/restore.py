#!/usr/bin/env python3
"""
数据恢复脚本
用法: python scripts/restore.py backup/mysql_rag_meta_20260529_160000.sql
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def restore_mysql(sql_file: Path, settings) -> bool:
    """恢复 MySQL 数据库。"""
    if not sql_file.exists():
        print(f"  ✗ 文件不存在: {sql_file}")
        return False

    cmd = [
        "mysql",
        f"-h{settings.mysql.host}",
        f"-P{settings.mysql.port}",
        f"-u{settings.mysql.user}",
        f"-p{settings.mysql.password}",
        settings.mysql.database,
    ]

    try:
        with open(sql_file, "r", encoding="utf-8") as f:
            result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            print(f"  ✓ MySQL 恢复完成")
            return True
        else:
            print(f"  ✗ MySQL 恢复失败: {result.stderr}")
            return False
    except FileNotFoundError:
        print("  ✗ mysql 客户端未找到")
        return False


def restore_chromadb(backup_dir: Path, settings) -> bool:
    """恢复 ChromaDB 数据。"""
    chroma_dir = ROOT / settings.store.chroma_path
    if chroma_dir.exists():
        print(f"  ⚠ ChromaDB 目录已存在，将被覆盖")
        shutil.rmtree(chroma_dir)

    try:
        shutil.copytree(backup_dir, chroma_dir)
        print(f"  ✓ ChromaDB 恢复完成")
        return True
    except Exception as e:
        print(f"  ✗ ChromaDB 恢复失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="知识库数据恢复")
    parser.add_argument("backup_path", help="备份文件或目录路径")
    parser.add_argument("--type", choices=["mysql", "chroma", "raw"], required=True,
                       help="恢复类型")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    from src.config import load_settings
    settings = load_settings()

    backup_path = Path(args.backup_path)
    print(f"📥 开始恢复 ← {backup_path}")
    print()

    if args.type == "mysql":
        success = restore_mysql(backup_path, settings)
    elif args.type == "chroma":
        success = restore_chromadb(backup_path, settings)
    elif args.type == "raw":
        raw_dir = ROOT / settings.ingest.raw_dir
        if raw_dir.exists():
            shutil.rmtree(raw_dir)
        shutil.copytree(backup_path, raw_dir)
        print(f"  ✓ 原始文件恢复完成")
        success = True

    if success:
        print("✅ 恢复完成")
    else:
        print("❌ 恢复失败")
        sys.exit(1)


if __name__ == "__main__":
    main()

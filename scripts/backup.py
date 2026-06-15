#!/usr/bin/env python3
"""
数据库备份脚本
用法: python scripts/backup.py [--output-dir backup/]
"""

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent


def backup_mysql(output_dir: Path, settings) -> bool:
    """备份 MySQL 数据库。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sql_file = output_dir / f"mysql_{settings.mysql.database}_{timestamp}.sql"

    cmd = [
        "mysqldump",
        f"-h{settings.mysql.host}",
        f"-P{settings.mysql.port}",
        f"-u{settings.mysql.user}",
        f"-p{settings.mysql.password}",
        settings.mysql.database,
    ]

    try:
        with open(sql_file, "w", encoding="utf-8") as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            size_kb = sql_file.stat().st_size / 1024
            print(f"  ✓ MySQL 备份完成: {sql_file.name} ({size_kb:.1f} KB)")
            return True
        else:
            print(f"  ✗ MySQL 备份失败: {result.stderr}")
            return False
    except FileNotFoundError:
        print("  ✗ mysqldump 未找到，请确保 MySQL 客户端已安装")
        return False


def backup_chromadb(output_dir: Path, settings) -> bool:
    """备份 ChromaDB 数据。"""
    chroma_dir = ROOT / settings.store.chroma_path
    if not chroma_dir.exists():
        print("  ⚠ ChromaDB 目录不存在，跳过")
        return True

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = output_dir / f"chroma_{timestamp}"
    try:
        shutil.copytree(chroma_dir, dest)
        size_mb = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) / (1024 * 1024)
        print(f"  ✓ ChromaDB 备份完成: {dest.name} ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        print(f"  ✗ ChromaDB 备份失败: {e}")
        return False


def backup_raw_files(output_dir: Path, settings) -> bool:
    """备份原始文件。"""
    raw_dir = ROOT / settings.ingest.raw_dir
    if not raw_dir.exists():
        print("  ⚠ 原始文件目录不存在，跳过")
        return True

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = output_dir / f"raw_{timestamp}"
    try:
        shutil.copytree(raw_dir, dest)
        file_count = sum(1 for _ in dest.rglob("*") if _.is_file())
        print(f"  ✓ 原始文件备份完成: {dest.name} ({file_count} 个文件)")
        return True
    except Exception as e:
        print(f"  ✗ 原始文件备份失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="知识库数据备份")
    parser.add_argument("--output-dir", default="backup", help="备份输出目录")
    parser.add_argument("--mysql", action="store_true", help="仅备份 MySQL")
    parser.add_argument("--chroma", action="store_true", help="仅备份 ChromaDB")
    parser.add_argument("--raw", action="store_true", help="仅备份原始文件")
    args = parser.parse_args()

    # 加载配置
    sys.path.insert(0, str(ROOT))
    from src.config import load_settings
    settings = load_settings()

    # 创建输出目录
    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📦 开始备份 → {output_dir}")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 如果没有指定特定项，则全部备份
    backup_all = not (args.mysql or args.chroma or args.raw)

    success = True
    if backup_all or args.mysql:
        print("[1/3] MySQL 数据库")
        success &= backup_mysql(output_dir, settings)

    if backup_all or args.chroma:
        print("[2/3] ChromaDB 向量库")
        success &= backup_chromadb(output_dir, settings)

    if backup_all or args.raw:
        print("[3/3] 原始文件")
        success &= backup_raw_files(output_dir, settings)

    print()
    if success:
        print("✅ 备份完成")
    else:
        print("⚠️  部分备份失败，请检查日志")
        sys.exit(1)


if __name__ == "__main__":
    main()

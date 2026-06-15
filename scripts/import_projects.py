"""批量导入 E:\\ 盘项目文件到知识库（只导入指定项目，跳过库文件）"""

import sys
import os
from pathlib import Path

# 设置编码
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 确保项目根目录在 sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_settings
from src.store.vector import VectorStore
from src.store.metadata import MetadataStore
from src.store.embedding import EmbeddingManager
from src.ingest.pipeline import (
    ingest_pdf, ingest_word, ingest_excel, ingest_text,
    SUPPORTED_EXTENSIONS,
)

# 只导入这些项目目录
PROJECT_DIRS = [
    r"E:\AI-Library-Management-System-main",
    r"E:\library-management v2.0",
    r"E:\PythonProject",
    r"E:\PythonProject1",
    r"E:\PyQt5_01",
    r"E:\StorageProject",
    r"E:\face",
    r"E:\python",
]

# 跳过的目录
SKIP_DIRS = {
    '.git', '__pycache__', 'node_modules', '.venv', 'venv',
    '.idea', '.vscode', 'dist', 'build', '.eggs', '.tox',
}

# 最大文件大小 (MB)
MAX_SIZE_MB = 5


def scan_files(base_dir: str) -> list[Path]:
    """扫描目录下所有支持的文件"""
    files = []
    base = Path(base_dir)
    if not base.exists():
        print(f"  [跳过] 目录不存在: {base_dir}")
        return files

    for root, dirs, filenames in os.walk(base):
        # 跳过不需要的目录
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]

        for f in filenames:
            fp = Path(root) / f
            ext = fp.suffix.lower()
            if ext in SUPPORTED_EXTENSIONS:
                try:
                    size_mb = fp.stat().st_size / (1024 * 1024)
                    if 0 < size_mb <= MAX_SIZE_MB:
                        files.append(fp)
                except:
                    pass
    return files


def ingest_file(f: Path, settings, vs, ms, embedder):
    """根据文件类型分发到对应的摄取函数"""
    ext = f.suffix.lower()
    file_type = SUPPORTED_EXTENSIONS.get(ext)

    try:
        if file_type == 'pdf':
            return ingest_pdf(f, settings, vs, ms, embedder)
        elif file_type == 'word':
            return ingest_word(f, settings, vs, ms, embedder)
        elif file_type == 'excel':
            return ingest_excel(f, settings, vs, ms, embedder)
        elif file_type in ('text', 'code'):
            return ingest_text(f, settings, vs, ms, embedder)
        else:
            return None
    except Exception as e:
        return str(e)


def main():
    print("=" * 60)
    print("  批量导入 E:\\ 盘项目文件到知识库")
    print("=" * 60)

    settings = load_settings()
    embedder = EmbeddingManager(settings)
    vs = VectorStore(settings)
    ms = MetadataStore(settings)

    total_files = 0
    success = 0
    failed = 0
    skipped = 0

    for proj_path in PROJECT_DIRS:
        proj_name = Path(proj_path).name
        print(f"\n{'─' * 50}")
        print(f"项目: {proj_name}")
        files = scan_files(proj_path)
        print(f"  找到 {len(files)} 个文件")

        if not files:
            continue

        for i, f in enumerate(files, 1):
            total_files += 1
            try:
                result = ingest_file(f, settings, vs, ms, embedder)
                if result is None:
                    skipped += 1
                elif isinstance(result, str):
                    failed += 1
                    print(f"  [{i}/{len(files)}] X {f.name}: {result}")
                else:
                    success += 1
                    if i % 5 == 0 or i == len(files) or i <= 3:
                        print(f"  [{i}/{len(files)}] OK {f.name} ({result['chunks']}块)")
            except Exception as e:
                failed += 1
                print(f"  [{i}/{len(files)}] X {f.name}: {e}")

    ms.close()

    print(f"\n{'=' * 60}")
    print(f"导入完成!")
    print(f"  总文件数: {total_files}")
    print(f"  成功: {success}")
    print(f"  失败: {failed}")
    print(f"  跳过: {skipped}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

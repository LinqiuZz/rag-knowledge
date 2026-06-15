"""批量导入 E:\\ 盘所有项目文件到知识库（分批处理，跳过库文件）"""

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

# 要导入的项目目录
PROJECT_DIRS = [
    "AI-Library-Management-System-main",
    "library-management v2.0",
    "PythonProject",
    "PythonProject1",
    "PyQt5_01",
    "StorageProject",
    "face",
    "python",
    "新建文件夹",
    "HuaweiMoveData",
]

# 跳过的目录（包括库目录）
SKIP_DIRS = {
    '.git', '__pycache__', 'node_modules', '.venv', 'venv',
    '.idea', '.vscode', 'dist', 'build', '.eggs', '.tox',
    'migrations', 'vendor', 'packages', 'Lib', 'lib',
    'include', 'Scripts', 'bin', 'share', 'doc',
    'qt5', 'qt6', 'Qt', 'mingw', 'MinGW',
    'site-packages', 'cmake', 'CMake',
}

# 跳过的路径关键词（库文件特征）
SKIP_PATH_KEYWORDS = [
    'site-packages', 'node_modules', '.git',
    'qt5', 'qt6', 'Qt/Tools', 'Qt/Docs', 'Qt/Examples',
    'mingw', 'MinGW', 'MSVC', 'msvc',
    'include/qt', 'include/Qt',
    'Lib/site-packages', 'lib/python',
]

# 最大文件大小 (MB)
MAX_SIZE_MB = 5


def scan_files(base_dir: str) -> list[Path]:
    """扫描目录下所有支持的文件，跳过库文件"""
    files = []
    base = Path(base_dir)
    if not base.exists():
        print(f"  [跳过] 目录不存在: {base_dir}")
        return files

    for root, dirs, filenames in os.walk(base):
        root_path = str(root)

        # 跳过包含库路径关键词的目录
        skip = False
        for kw in SKIP_PATH_KEYWORDS:
            if kw in root_path:
                skip = True
                break
        if skip:
            dirs.clear()
            continue

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
    print("  (只导入项目源码，跳过库文件)")
    print("=" * 60)

    settings = load_settings()
    embedder = EmbeddingManager(settings)
    vs = VectorStore(settings)
    ms = MetadataStore(settings)

    total_files = 0
    success = 0
    failed = 0
    skipped = 0

    for proj in PROJECT_DIRS:
        proj_path = f"E:\\{proj}"
        print(f"\n{'─' * 50}")
        print(f"扫描项目: {proj}")
        files = scan_files(proj_path)
        print(f"  找到 {len(files)} 个项目文件")

        if not files:
            continue

        for i, f in enumerate(files, 1):
            total_files += 1
            try:
                result = ingest_file(f, settings, vs, ms, embedder)
                if result is None:
                    skipped += 1
                elif isinstance(result, str):
                    # Error message
                    failed += 1
                    print(f"  [{i}/{len(files)}] X {f.name}: {result}")
                else:
                    success += 1
                    if i % 10 == 0 or i == len(files):
                        print(f"  [{i}/{len(files)}] OK ({result['chunks']}块)")
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

"""导入 E:\\BaiduNetdiskDownload 中的PDF文件到知识库"""

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
from src.ingest.pipeline import ingest_pdf

# 源目录
SOURCE_DIR = Path(r"E:\BaiduNetdiskDownload")


def main():
    print("=" * 60)
    print("  导入百度网盘下载的PDF到知识库")
    print("=" * 60)

    # 扫描PDF文件
    pdf_files = list(SOURCE_DIR.glob("*.pdf"))
    if not pdf_files:
        print("未找到PDF文件")
        return

    print(f"\n找到 {len(pdf_files)} 个PDF文件:")
    for f in pdf_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  - {f.name} ({size_mb:.1f}MB)")

    # 加载配置并临时调大文件大小限制
    settings = load_settings()
    original_max = settings.ingest.max_file_size_mb
    settings.ingest.max_file_size_mb = 5000  # 临时调到5GB
    print(f"\n临时调整文件大小限制: {original_max}MB -> {settings.ingest.max_file_size_mb}MB")

    # 初始化组件
    print("\n初始化嵌入模型（首次可能需要下载）...")
    embedder = EmbeddingManager(settings)
    vs = VectorStore(settings)
    ms = MetadataStore(settings)

    success = 0
    failed = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n{'─' * 50}")
        print(f"[{i}/{len(pdf_files)}] 处理: {pdf_path.name}")
        try:
            result = ingest_pdf(pdf_path, settings, vs, ms, embedder)
            success += 1
            print(f"  ✓ 完成: {result['title']} ({result['chunks']}块, {result['chars']}字符)")
        except Exception as e:
            failed += 1
            print(f"  ✗ 失败: {e}")

    ms.close()

    print(f"\n{'=' * 60}")
    print(f"导入完成!")
    print(f"  成功: {success}")
    print(f"  失败: {failed}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

"""增强分块 — 已合并到 chunking.py

本模块保留为向后兼容的桥接层，
所有功能已整合到 src/ingest/chunking.py 中。
"""

# ── 向后兼容重导出 ────────────────────────────────────────────────
from .chunking import (
    split_text,
    SmallToBigChunker,
    SmallChunk,
    BigChunk,
)

__all__ = [
    "split_text",
    "SmallToBigChunker",
    "SmallChunk",
    "BigChunk",
]

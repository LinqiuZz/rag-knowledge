"""统一摄取管道 — 企业版

整合深度解析 → Small-to-Big 分块 → 嵌入 → 存储 的完整管道。

支持:
  - 多格式深度解析（排版保留）
  - Small-to-Big 分层分块
  - 自动版本管理（is_active 标记）
  - MinIO 对象存储
  - 权限继承
  - 审计日志
"""

from __future__ import annotations

import hashlib
import shutil
import traceback
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console

from .parsers import parse_document, SUPPORTED_EXTENSIONS
from .chunking import SmallToBigChunker, split_text

if TYPE_CHECKING:
    from ..config import Settings
    from ..store.vector import BaseVectorStore
    from ..store.metadata import MetadataStore
    from ..store.embedding import EmbeddingManager
    from ..store.storage import MinIOStorage

console = Console()


def _make_id(source: str, chunk_idx: int) -> str:
    """生成确定性块 ID。"""
    h = hashlib.md5(source.encode()).hexdigest()[:12]
    return f"{h}_{chunk_idx:04d}"


# ═══════════════════════════════════════════════════════════════
# 企业级文档摄取
# ═══════════════════════════════════════════════════════════════

def ingest_document(
    file_path: str | Path,
    settings: Settings,
    vector_store: BaseVectorStore,
    meta_store: MetadataStore,
    embedder: EmbeddingManager,
    storage: MinIOStorage = None,
    owner_id: int = 1,
    permission_ids: list[int] = None,
) -> dict:
    """摄取任意格式的文档（企业级管道）。

    流程:
      1. 深度解析文档（保留排版）
      2. 上传原始文件到 MinIO
      3. 创建文档 + 版本记录
      4. Small-to-Big 分块
      5. 嵌入向量化
      6. 存入向量库 + 元数据库
      7. 审计日志

    Returns:
        {
            "doc_id": int,
            "version_id": int,
            "title": str,
            "format": str,
            "chunks": int,
            "small_chunks": int,
            "big_chunks": int,
            "chars": int,
        }
    """
    path = Path(file_path).resolve()
    source = str(path)

    # 检查大小
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > settings.ingest.max_file_size_mb:
        raise ValueError(f"文件过大: {size_mb:.1f}MB > {settings.ingest.max_file_size_mb}MB")

    suffix = path.suffix.lower()
    doc_format = SUPPORTED_EXTENSIONS.get(suffix, "text")

    console.print(f"[cyan]解析文档 ({doc_format}):[/cyan] {path.name}")

    # ── 1. 深度解析 ──
    try:
        doc_structure = parse_document(path)
    except Exception as e:
        meta_store.log(source, "error", f"文档解析失败: {e}")
        raise ValueError(f"文档解析失败: {e}") from e

    if not doc_structure.full_text.strip():
        meta_store.log(source, "error", "文档未提取到任何文本内容")
        raise ValueError("文档未提取到任何文本内容")

    console.print(f"  解析完成: {doc_structure.page_count} 页, {doc_structure.char_count} 字符")

    # ── 2. 上传原始文件 ──
    object_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{path.name}"
    if storage:
        try:
            storage.upload_file(path, object_name)
        except Exception as e:
            console.print(f"  [yellow]⚠ MinIO 上传失败（使用本地路径）: {e}[/yellow]")
    else:
        # 本地回退
        raw_dir = settings.raw_dir / doc_format
        raw_dir.mkdir(parents=True, exist_ok=True)
        dest = raw_dir / path.name
        if not dest.exists():
            shutil.copy2(path, dest)
        object_name = str(dest)

    # ── 3. 创建文档 + 版本 ──
    try:
        doc_id = meta_store.add_document(
            title=doc_structure.title,
            format=doc_format,
            owner_id=owner_id,
            storage_path=object_name,
            char_count=doc_structure.char_count,
            page_count=doc_structure.page_count,
        )

        version_id = meta_store.create_version(
            doc_id=doc_id,
            storage_path=object_name,
            char_count=doc_structure.char_count,
            page_count=doc_structure.page_count,
        )
    except Exception as e:
        meta_store.log(source, "error", f"元数据创建失败: {e}")
        raise ValueError(f"元数据创建失败: {e}") from e

    # ── 4. Small-to-Big 分块 ──
    chunker = SmallToBigChunker(settings)
    permission_ids = permission_ids or []

    try:
        small_chunks, big_chunks = chunker.chunk(
            doc_structure, str(doc_id), version_id, permission_ids,
        )
    except Exception as e:
        # 回退：使用经典分块
        console.print(f"  [yellow]⚠ Small-to-Big 分块失败，回退到 sentence 分块: {e}[/yellow]")
        plain_chunks = split_text(
            doc_structure.full_text,
            settings.chunking.small_size,
            settings.chunking.small_overlap,
            strategy="sentence",
        )
        small_chunks = []
        for i, text in enumerate(plain_chunks):
            from .chunking import SmallChunk
            cid = _make_id(f"{doc_id}_v{version_id}", i)
            small_chunks.append(SmallChunk(
                chunk_id=cid,
                text=text,
                plain_text=text,
                doc_id=str(doc_id),
                version_id=version_id,
                page_number=1,
                element_type="Paragraph",
                permission_ids=permission_ids,
                is_active=True,
                order=i,
            ))
        big_chunks = []

    if not small_chunks:
        meta_store.log(source, "error", "分块结果为空")
        raise ValueError("分块结果为空")

    console.print(f"  分块完成: {len(small_chunks)} 子块 + {len(big_chunks)} 父块")

    # ── 5. 生成嵌入 ──
    console.print("  生成嵌入向量...")
    texts = [sc.text for sc in small_chunks]
    try:
        embeddings = embedder.embed_documents(texts)
    except Exception as e:
        meta_store.log(source, "error", f"嵌入生成失败: {e}")
        raise ValueError(f"嵌入生成失败: {e}") from e

    # ── 6. 存入向量库 ──
    vector_ids = [sc.chunk_id for sc in small_chunks]
    metadatas = []
    for sc in small_chunks:
        metadatas.append({
            "chunk_id": sc.chunk_id,
            "doc_id": sc.doc_id,
            "version_id": sc.version_id,
            "source": object_name,
            "title": doc_structure.title,
            "doc_type": doc_format,
            "page_number": sc.page_number,
            "slide_number": sc.slide_number,
            "element_type": sc.element_type,
            "is_active": True,
            "parent_chunk_id": sc.parent_chunk_id,
            "plain_text": sc.plain_text,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    try:
        vector_store.add(ids=vector_ids, documents=texts,
                         embeddings=embeddings, metadatas=metadatas)
    except Exception as e:
        meta_store.log(source, "error", f"向量存储失败: {e}")
        raise ValueError(f"向量存储失败: {e}") from e

    # ── 7. 记录块元数据 ──
    try:
        chunk_records = []
        for sc in small_chunks:
            chunk_records.append({
                "chunk_id": sc.chunk_id,
                "doc_id": int(sc.doc_id),
                "version_id": sc.version_id,
                "vector_id": sc.chunk_id,
                "text": sc.plain_text,
                "metadata_json": {
                    "enriched_text": sc.text,
                    "element_type": sc.element_type,
                    "style": sc.style,
                    "level": sc.level,
                    "parent_chunk_id": sc.parent_chunk_id,
                },
                "page_number": sc.page_number,
                "slide_number": sc.slide_number,
                "element_type": sc.element_type,
                "permission_ids": sc.permission_ids,
            })
        meta_store.add_chunks(chunk_records)

        # 父块
        for bc in big_chunks:
            meta_store.add_chunks([{
                "chunk_id": bc.chunk_id,
                "doc_id": int(sc.doc_id) if small_chunks else doc_id,
                "version_id": version_id,
                "text": bc.text,
                "metadata_json": {
                    "type": "parent_chunk",
                    "child_ids": bc.child_ids,
                    "page_range": list(bc.page_range),
                    "section_title": bc.section_title,
                },
                "page_number": bc.page_range[0] if bc.page_range else 1,
                "slide_number": 0,
                "element_type": "ParentChunk",
                "permission_ids": permission_ids,
            }])
    except Exception as e:
        console.print(f"  [yellow]⚠ 块元数据记录失败（向量已入库）: {e}[/yellow]")
        meta_store.log(source, "warning", f"块元数据记录失败: {e}")

    # ── 8. 审计日志 ──
    try:
        meta_store.audit(
            owner_id, "ingest", "document", str(doc_id),
            detail={
                "title": doc_structure.title,
                "format": doc_format,
                "chunks": len(small_chunks),
                "big_chunks": len(big_chunks),
                "object_name": object_name,
            },
        )
        meta_store.log(source, "success",
                       f"摄取完成: {len(small_chunks)} 子块 + {len(big_chunks)} 父块",
                       doc_id=doc_id)
    except Exception as e:
        console.print(f"  [yellow]⚠ 审计日志记录失败: {e}[/yellow]")

    console.print(f"  [green]✓ 完成:[/green] {doc_structure.title} "
                  f"(doc_id={doc_id}, {len(small_chunks)} 子块 + {len(big_chunks)} 父块)")

    return {
        "doc_id": doc_id,
        "version_id": version_id,
        "title": doc_structure.title,
        "format": doc_format,
        "chunks": len(small_chunks) + len(big_chunks),
        "small_chunks": len(small_chunks),
        "big_chunks": len(big_chunks),
        "chars": doc_structure.char_count,
    }

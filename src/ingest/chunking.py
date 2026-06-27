"""智能分块策略 — Small-to-Big 分层架构

新方案核心: 采用 small-to-big 分层策略，在索引效率和上下文保留之间取得平衡。

层次结构:
  1. 子块 (small chunk): 以元素或自然段落为粒度
     - 一个标题、一个段落、一个表格、一个幻灯片元素
     - 大小: ~512 tokens
     - 用于: 精确语义检索

  2. 父块 (big chunk): 聚合同一章节/幻灯片或相邻若干子块
     - 大小: ~2048 tokens
     - 用于: 检索命中后扩展上下文

文本表示（Enriched Text）:
  为每个子块生成富含元数据的文本，格式:
    [文档类型: Word] [节: 财务分析] [页眉: 内部资料] [标题2] 营收增长情况
    正文内容：本季度营收同比增长 15%...

向量化 payload 元数据:
  - chunk_id, doc_id, version_id
  - page_number / slide_number
  - element_type (标题/正文/表格/图片描述)
  - permission_ids
  - is_active
  - parent_chunk_id (关联父块)
  - 纯文本内容
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════

@dataclass
class SmallChunk:
    """子块 — 最小检索单元。"""
    chunk_id: str
    text: str                       # 富含元数据的文本表示
    plain_text: str                 # 纯文本
    # 元数据
    doc_id: str = ""
    version_id: int = 0
    page_number: int = 0
    slide_number: int = 0
    element_type: str = "Paragraph"  # Heading, Paragraph, Table, Picture, TextBox, etc.
    style: str = ""                  # 样式名
    level: int = 0                   # 标题层级
    position: str = ""               # PPT位置
    permission_ids: list[int] = field(default_factory=list)
    is_active: bool = True
    parent_chunk_id: str = ""        # 关联父块
    # 扩展元数据
    header: str = ""
    footer: str = ""
    layout: str = ""                 # PPT 布局名
    notes: str = ""                  # PPT 备注
    extra_meta: dict = field(default_factory=dict)
    # 排序
    order: int = 0                   # 原始顺序


@dataclass
class BigChunk:
    """父块 — 聚合多个子块，提供丰富上下文。"""
    chunk_id: str
    text: str                       # 纯文本拼接
    child_ids: list[str] = field(default_factory=list)
    page_range: tuple[int, int] = (0, 0)  # (start_page, end_page)
    section_title: str = ""         # 所属章节标题


# ═══════════════════════════════════════════════════════════════
# 分块引擎
# ═══════════════════════════════════════════════════════════════

class SmallToBigChunker:
    """Small-to-Big 分块引擎。

    用法:
        chunker = SmallToBigChunker(settings)
        small_chunks, big_chunks = chunker.chunk(doc_structure, doc_id, version_id)
    """

    def __init__(self, settings):
        from ..config import Settings
        self.settings: Settings = settings
        self.small_size = settings.chunking.small_size
        self.small_overlap = settings.chunking.small_overlap
        self.big_size = settings.chunking.big_size
        self.big_overlap = settings.chunking.big_overlap
        self.min_size = settings.chunking.min_chunk_size

    def chunk(self, doc_structure, doc_id: str, version_id: int,
              permission_ids: list[int] = None) -> tuple[list[SmallChunk], list[BigChunk]]:
        """对 DocumentStructure 执行 small-to-big 分块。

        Args:
            doc_structure: 解析后的 DocumentStructure
            doc_id: 文档 ID
            version_id: 版本 ID
            permission_ids: 权限 ID 列表

        Returns:
            (small_chunks, big_chunks)
        """
        from .parsers import extract_text_segments

        permission_ids = permission_ids or []
        segments = extract_text_segments(doc_structure)

        if not segments:
            return [], []

        # ── 第一阶段：生成子块 ──
        small_chunks = self._build_small_chunks(
            segments, doc_id, version_id,
            doc_structure.format, permission_ids,
        )

        # ── 第二阶段：聚合为父块 ──
        big_chunks = self._build_big_chunks(small_chunks)

        # ── 关联父子关系 ──
        self._link_parents(small_chunks, big_chunks)

        return small_chunks, big_chunks

    def _build_small_chunks(
        self, segments: list[dict], doc_id: str,
        version_id: int, doc_format: str, permission_ids: list[int],
    ) -> list[SmallChunk]:
        """从文本段构建子块。"""
        chunks = []
        order = 0

        for seg in segments:
            text = seg.get("text", "").strip()
            if not text:
                continue

            # 如果文本过长，先按句子切分
            sub_texts = self._split_long_text(text, self.small_size)

            for sub_idx, sub_text in enumerate(sub_texts):
                if len(sub_text) < self.min_size:
                    continue

                chunk_id = _make_chunk_id(doc_id, f"{order:05d}")

                # 生成富含元数据的文本表示
                enriched = _build_enriched_text(
                    text=sub_text,
                    doc_format=doc_format,
                    page_number=seg.get("page_number", 0),
                    slide_number=seg.get("slide_number", 0),
                    element_type=seg.get("element_type", "Paragraph"),
                    style=seg.get("style", ""),
                    level=seg.get("level", 0),
                    header=seg.get("header", ""),
                    footer=seg.get("footer", ""),
                    layout=seg.get("layout", ""),
                    notes=seg.get("notes", ""),
                )

                chunks.append(SmallChunk(
                    chunk_id=chunk_id,
                    text=enriched,
                    plain_text=sub_text,
                    doc_id=doc_id,
                    version_id=version_id,
                    page_number=seg.get("page_number", 0),
                    slide_number=seg.get("slide_number", 0),
                    element_type=seg.get("element_type", "Paragraph"),
                    style=seg.get("style", ""),
                    level=seg.get("level", 0),
                    position=seg.get("position", ""),
                    permission_ids=permission_ids,
                    is_active=True,
                    header=seg.get("header", ""),
                    footer=seg.get("footer", ""),
                    layout=seg.get("layout", ""),
                    notes=seg.get("notes", ""),
                    extra_meta=seg.get("metadata", {}),
                    order=order,
                ))
                order += 1

        return chunks

    def _split_long_text(self, text: str, max_size: int) -> list[str]:
        """将长文本按句子切分为适合子块的片段。"""
        if len(text) <= max_size:
            return [text]

        # 中英文句子分隔
        sentences = re.split(r'(?<=[。！？.!?\n])\s*', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current = ""
        for sent in sentences:
            candidate = current + (" " if current and not current.endswith('\n') else "") + sent
            if len(candidate) <= max_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                # 超长句子硬切
                if len(sent) > max_size:
                    for i in range(0, len(sent), max_size - self.small_overlap):
                        sub = sent[i:i + max_size].strip()
                        if sub:
                            chunks.append(sub)
                    current = ""
                else:
                    current = sent
        if current.strip():
            chunks.append(current.strip())

        return chunks

    def _build_big_chunks(self, small_chunks: list[SmallChunk]) -> list[BigChunk]:
        """将子块聚合为父块。

        聚合规则:
          - Word/PDF: 同一页或相邻多页的子块合并
          - PPT: 同一张幻灯片的子块合并
          - 控制父块总长度不超过 big_size
        """
        if not small_chunks:
            return []

        big_chunks = []
        current_kids = []
        current_text = ""
        current_pages = (small_chunks[0].page_number, small_chunks[0].page_number)
        section_title = ""
        big_idx = 0

        for sc in small_chunks:
            # 检测章节标题更新
            if sc.element_type.startswith("Heading") and sc.level <= 2:
                section_title = sc.plain_text

            candidate_text = current_text + ("\n" if current_text else "") + sc.plain_text

            # 决定是否开始新的父块
            new_parent = False
            if len(candidate_text) > self.big_size and current_kids:
                new_parent = True
            elif sc.slide_number and sc.slide_number != current_pages[0] and current_kids:
                # PPT 每张幻灯片一个父块
                new_parent = True

            if new_parent:
                big_id = _make_chunk_id(f"{sc.doc_id}_big", f"{big_idx:04d}")
                big_chunks.append(BigChunk(
                    chunk_id=big_id,
                    text=current_text,
                    child_ids=[k.chunk_id for k in current_kids],
                    page_range=current_pages,
                    section_title=section_title,
                ))
                big_idx += 1
                current_kids = []
                current_text = ""
                current_pages = (sc.page_number, sc.page_number)
                section_title = ""

            current_kids.append(sc)
            current_text = current_text + ("\n" if current_text else "") + sc.plain_text
            if sc.page_number:
                current_pages = (min(current_pages[0], sc.page_number),
                                 max(current_pages[1], sc.page_number))

        # 最后一个父块
        if current_kids:
            big_id = _make_chunk_id(f"{small_chunks[0].doc_id}_big", f"{big_idx:04d}")
            big_chunks.append(BigChunk(
                chunk_id=big_id,
                text=current_text,
                child_ids=[k.chunk_id for k in current_kids],
                page_range=current_pages,
                section_title=section_title,
            ))

        return big_chunks

    def _link_parents(self, small_chunks: list[SmallChunk], big_chunks: list[BigChunk]):
        """将子块的 parent_chunk_id 关联到父块。"""
        # 构建 child_id → big_id 的映射
        child_map = {}
        for bc in big_chunks:
            for cid in bc.child_ids:
                child_map[cid] = bc.chunk_id

        for sc in small_chunks:
            sc.parent_chunk_id = child_map.get(sc.chunk_id, "")


# ═══════════════════════════════════════════════════════════════
# 扁平分块（兼容旧策略: recursive/sentence/paragraph）
# ═══════════════════════════════════════════════════════════════

def split_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
    strategy: str = "sentence",
) -> list[str]:
    """扁平分块 — 兼容旧接口。

    策略:
      - recursive: 递归字符切分
      - sentence: 句子级切分
      - paragraph: 段落级切分
    """
    if not text.strip():
        return []

    if strategy == "recursive":
        return _recursive_split(text, chunk_size, overlap)
    elif strategy == "sentence":
        return _sentence_split(text, chunk_size, overlap)
    elif strategy == "paragraph":
        return _paragraph_split(text, chunk_size, overlap)
    elif strategy == "small_to_big":
        # 回退到 sentence 分块
        return _sentence_split(text, chunk_size, overlap)
    else:
        raise ValueError(f"未知的分块策略: {strategy}")


def _recursive_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """递归字符分块。"""
    separators = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", "；", ";", " "]
    return _do_recursive_split(text, separators, chunk_size, overlap)


def _do_recursive_split(text: str, separators: list[str], chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    sep = None
    for s in separators:
        if s in text:
            sep = s
            break

    if sep is None:
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
        return chunks

    parts = text.split(sep)
    chunks = []
    current = ""

    for part in parts:
        candidate = current + sep + part if current else part
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current.strip():
                chunks.append(current.strip())
            if len(part) > chunk_size:
                sub_chunks = _do_recursive_split(part, separators[1:], chunk_size, overlap)
                chunks.extend(sub_chunks)
                current = ""
            else:
                current = part

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _sentence_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """句子级分块。"""
    sentences = re.split(r"(?<=[。！？.!?])\s*", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    current = ""
    for sent in sentences:
        candidate = current + " " + sent if current else sent
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            if len(sent) > chunk_size:
                for i in range(0, len(sent), chunk_size - overlap):
                    sub = sent[i:i + chunk_size].strip()
                    if sub:
                        chunks.append(sub)
                current = ""
            else:
                current = sent

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _paragraph_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """段落级分块。"""
    paragraphs = text.split("\n\n")
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current = ""
    for para in paragraphs:
        candidate = current + "\n\n" + para if current else para
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            if len(para) > chunk_size:
                sub_chunks = _sentence_split(para, chunk_size, overlap)
                chunks.extend(sub_chunks)
                current = ""
            else:
                current = para

    if current.strip():
        chunks.append(current.strip())

    return chunks


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

def _make_chunk_id(prefix: str, suffix: str) -> str:
    """生成确定性块 ID。"""
    h = hashlib.md5(f"{prefix}_{suffix}".encode()).hexdigest()[:12]
    return f"{h}_{suffix}"


def _build_enriched_text(
    text: str,
    doc_format: str = "",
    page_number: int = 0,
    slide_number: int = 0,
    element_type: str = "Paragraph",
    style: str = "",
    level: int = 0,
    header: str = "",
    footer: str = "",
    layout: str = "",
    notes: str = "",
) -> str:
    """生成富含元数据的文本表示。

    格式:
      [文档类型: Word] [第5页] [页眉: 内部资料] [标题2] 营收增长情况
      [正文] 本季度营收同比增长 15%...
    """
    tags = []

    if doc_format:
        fmt_name = {"docx": "Word", "pptx": "PPT", "xlsx": "Excel",
                     "pdf": "PDF", "image": "图片", "md": "Markdown",
                     "code": "代码", "txt": "文本"}.get(doc_format, doc_format)
        tags.append(f"[文档类型: {fmt_name}]")

    if page_number:
        tags.append(f"[第{page_number}页]")
    elif slide_number:
        tags.append(f"[幻灯片{slide_number}]")

    if header:
        tags.append(f"[页眉: {header}]")
    if footer:
        tags.append(f"[页脚: {footer}]")
    if layout:
        tags.append(f"[布局: {layout}]")
    if notes:
        tags.append(f"[备注: {notes}]")

    if element_type.startswith("Heading") and level:
        tags.append(f"[标题{level}]")
    elif element_type == "Table":
        tags.append("[表格]")
    elif element_type == "Picture":
        tags.append("[图片]")
    elif element_type == "Code":
        tags.append("[代码]")
    elif element_type == "Title":
        tags.append("[幻灯片标题]")
    elif element_type == "ListItem":
        tags.append("[列表]")

    meta_prefix = " ".join(tags)
    return f"{meta_prefix}\n{text}" if meta_prefix else text

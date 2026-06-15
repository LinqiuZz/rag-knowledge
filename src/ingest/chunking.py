"""文本分块策略"""

from __future__ import annotations

import re


def split_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """
    智能文本分块。

    分块策略优先级：
    1. 按标题/章节切分（Markdown标题、数字编号）
    2. 按段落切分（双换行）
    3. 按句子切分（中文句号、问号、感叹号）
    4. 按换行切分
    5. 按空格切分
    6. 硬切（最后手段）

    保证每块不超过 chunk_size，块间有 overlap 字符重叠。
    最小块大小为 chunk_size 的 20%，避免碎片化。
    """
    if not text.strip():
        return []

    min_chunk_size = max(chunk_size // 5, 50)  # 最小块大小

    # 预处理：规范化换行符
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 第一步：按标题切分（Markdown # 或数字编号 1. 2. 等）
    sections = _split_by_headers(text)
    if len(sections) > 1:
        chunks = []
        for section in sections:
            if len(section) <= chunk_size:
                if section.strip():
                    chunks.append(section.strip())
            else:
                chunks.extend(_recursive_split(
                    section,
                    ["\n\n", "\n", "。", "！", "？", ".", "!", "?", "；", ";", " "],
                    chunk_size, overlap, min_chunk_size
                ))
        return _apply_overlap(chunks, overlap, min_chunk_size)

    # 第二步：递归分块
    separators = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", "；", ";", " "]
    chunks = _recursive_split(text, separators, chunk_size, overlap, min_chunk_size)
    return _apply_overlap(chunks, overlap, min_chunk_size)


def _split_by_headers(text: str) -> list[str]:
    """按标题切分文档（Markdown # 或数字编号）。"""
    # Markdown 标题：# ## ### 等
    # 数字编号：1. 2. 3. 或 一、二、三、
    header_pattern = r'(?=^#{1,4}\s|^\d+\.\s|^[一二三四五六七八九十]+[、.])'
    parts = re.split(header_pattern, text, flags=re.MULTILINE)
    return [p for p in parts if p.strip()]


def _recursive_split(
    text: str, separators: list[str], chunk_size: int, overlap: int, min_chunk_size: int
) -> list[str]:
    """递归分块，按分隔符优先级逐级切分。"""
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    # 找到第一个能用的分隔符
    sep = None
    for s in separators:
        if s in text:
            sep = s
            break

    if sep is None:
        # 没有分隔符，硬切
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i : i + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
        return chunks

    # 用分隔符切分
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
            # 如果单个 part 也超长，递归切分
            if len(part) > chunk_size:
                sub_chunks = _recursive_split(
                    part, separators[1:], chunk_size, overlap, min_chunk_size
                )
                chunks.extend(sub_chunks)
                current = ""
            else:
                current = part

    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if c]


def _apply_overlap(chunks: list[str], overlap: int, min_chunk_size: int) -> list[str]:
    """应用重叠并合并过小的块。"""
    if not chunks:
        return []

    if overlap <= 0 or len(chunks) <= 1:
        return _merge_small_chunks(chunks, min_chunk_size)

    # 应用重叠
    overlapped = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_tail = chunks[i - 1][-overlap:]
        overlapped.append(prev_tail + chunks[i])

    return _merge_small_chunks(overlapped, min_chunk_size)


def _merge_small_chunks(chunks: list[str], min_size: int) -> list[str]:
    """合并过小的块到相邻块。"""
    if not chunks or min_size <= 0:
        return chunks

    merged = []
    buffer = ""

    for chunk in chunks:
        if buffer and len(buffer) + len(chunk) + 1 <= min_size * 3:
            buffer += "\n" + chunk
        elif len(chunk) < min_size:
            buffer = chunk
        else:
            if buffer:
                merged.append(buffer)
                buffer = ""
            merged.append(chunk)

    if buffer:
        if merged and len(buffer) < min_size:
            merged[-1] += "\n" + buffer
        else:
            merged.append(buffer)

    return merged

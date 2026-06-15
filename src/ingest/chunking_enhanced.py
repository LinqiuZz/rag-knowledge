"""增强的文本分块策略"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ChunkMetadata:
    """分块元数据"""
    chunk_id: str
    source: str
    title: str
    doc_type: str
    chunk_idx: int
    start_char: int
    end_char: int
    char_count: int


def split_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
    strategy: str = "recursive",
) -> list[str]:
    """
    文本分块（支持多种策略）

    Args:
        text: 原始文本
        chunk_size: 每块目标字符数
        overlap: 块间重叠字符数
        strategy: 分块策略
            - "recursive": 递归字符切分（默认）
            - "sentence": 句子级切分
            - "paragraph": 段落级切分

    Returns:
        分块后的文本列表
    """
    if not text.strip():
        return []

    if strategy == "recursive":
        return _recursive_split(text, chunk_size, overlap)
    elif strategy == "sentence":
        return _sentence_split(text, chunk_size, overlap)
    elif strategy == "paragraph":
        return _paragraph_split(text, chunk_size, overlap)
    else:
        raise ValueError(f"未知的分块策略: {strategy}")


def _recursive_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """递归字符文本分块（原实现）"""
    separators = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", "；", ";", " "]
    return _do_recursive_split(text, separators, chunk_size, overlap)


def _do_recursive_split(
    text: str, separators: list[str], chunk_size: int, overlap: int
) -> list[str]:
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
            chunk = text[i : i + chunk_size].strip()
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
                sub_chunks = _do_recursive_split(
                    part, separators[1:], chunk_size, overlap
                )
                chunks.extend(sub_chunks)
            else:
                current = part
                continue
            current = ""

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _sentence_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """句子级分块（保持句子完整性）"""
    import re

    # 中英文句子分隔符
    sentences = re.split(r"(?<=[。！？.!?])\s*", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    current = ""

    for sentence in sentences:
        candidate = current + " " + sentence if current else sentence
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            if len(sentence) > chunk_size:
                # 超长句子回退到递归切分
                sub_chunks = _recursive_split(sentence, chunk_size, overlap)
                chunks.extend(sub_chunks)
            else:
                current = sentence
                continue
            current = ""

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _paragraph_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """段落级分块（保持段落完整性）"""
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
                # 超长段落回退到句子切分
                sub_chunks = _sentence_split(para, chunk_size, overlap)
                chunks.extend(sub_chunks)
            else:
                current = para
                continue
            current = ""

    if current.strip():
        chunks.append(current.strip())

    return chunks


def get_chunk_metadata(
    chunks: list[str],
    source: str,
    title: str,
    doc_type: str,
) -> list[ChunkMetadata]:
    """为分块生成元数据"""
    import hashlib

    metadata = []
    for i, chunk in enumerate(chunks):
        chunk_id = hashlib.md5(f"{source}_{i}".encode()).hexdigest()[:12]
        metadata.append(ChunkMetadata(
            chunk_id=chunk_id,
            source=source,
            title=title,
            doc_type=doc_type,
            chunk_idx=i,
            start_char=0,  # 简化版本，实际需要计算
            end_char=len(chunk),
            char_count=len(chunk),
        ))

    return metadata

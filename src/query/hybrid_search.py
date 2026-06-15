"""混合检索模块"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class HybridSearchResult:
    """混合检索结果"""
    text: str
    source: str
    title: str
    doc_type: str
    semantic_score: float
    keyword_score: float
    combined_score: float
    chunk_idx: int


def hybrid_search(
    query: str,
    vector_store,
    embedder,
    top_k: int = 5,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> list[HybridSearchResult]:
    """
    混合检索：语义检索 + 关键词检索

    Args:
        query: 查询
        vector_store: 向量存储
        embedder: 嵌入管理器
        top_k: 返回结果数
        semantic_weight: 语义检索权重
        keyword_weight: 关键词检索权重

    Returns:
        混合检索结果
    """
    from .search import semantic_search

    # 1. 语义检索
    semantic_results = semantic_search(query, vector_store, embedder, top_k=top_k * 2)

    # 2. 关键词检索（BM25 风格）
    keyword_results = _keyword_search(query, vector_store, top_k=top_k * 2)

    # 3. 合并结果
    combined = _merge_results(
        semantic_results,
        keyword_results,
        semantic_weight,
        keyword_weight,
    )

    # 4. 排序并返回 top_k
    combined.sort(key=lambda x: x.combined_score, reverse=True)
    return combined[:top_k]


def _keyword_search(
    query: str,
    vector_store,
    top_k: int = 10,
) -> list[dict]:
    """
    关键词检索（基于倒排索引）

    Args:
        query: 查询
        vector_store: 向量存储
        top_k: 返回结果数

    Returns:
        关键词检索结果
    """
    # 从向量库获取所有文档
    all_docs = vector_store.collection.get(
        include=["documents", "metadatas"],
    )

    if not all_docs["ids"]:
        return []

    # 计算关键词匹配分数
    query_keywords = set(query.lower().split())
    results = []

    for i, (doc_id, text, meta) in enumerate(zip(
        all_docs["ids"],
        all_docs["documents"],
        all_docs["metadatas"],
    )):
        text_lower = text.lower()
        # 计算关键词匹配比例
        match_count = sum(1 for kw in query_keywords if kw in text_lower)
        keyword_score = match_count / len(query_keywords) if query_keywords else 0

        if keyword_score > 0:
            results.append({
                "text": text,
                "source": meta.get("source", ""),
                "title": meta.get("title", ""),
                "doc_type": meta.get("doc_type", ""),
                "keyword_score": keyword_score,
                "chunk_idx": meta.get("chunk_idx", 0),
            })

    # 按分数排序
    results.sort(key=lambda x: x["keyword_score"], reverse=True)
    return results[:top_k]


def _merge_results(
    semantic_results: list,
    keyword_results: list,
    semantic_weight: float,
    keyword_weight: float,
) -> list[HybridSearchResult]:
    """
    合并语义和关键词检索结果

    Args:
        semantic_results: 语义检索结果
        keyword_results: 关键词检索结果
        semantic_weight: 语义权重
        keyword_weight: 关键词权重

    Returns:
        合并后的结果
    """
    # 按 source + chunk_idx 去重
    seen = {}
    combined = []

    # 处理语义检索结果
    for r in semantic_results:
        key = f"{r.source}_{r.chunk_idx}"
        semantic_score = 1 - r.score  # 转换为相似度

        if key not in seen:
            seen[key] = {
                "text": r.text,
                "source": r.source,
                "title": r.title,
                "doc_type": r.doc_type,
                "semantic_score": semantic_score,
                "keyword_score": 0.0,
                "chunk_idx": r.chunk_idx,
            }
        else:
            seen[key]["semantic_score"] = max(seen[key]["semantic_score"], semantic_score)

    # 处理关键词检索结果
    for r in keyword_results:
        key = f"{r['source']}_{r['chunk_idx']}"

        if key not in seen:
            seen[key] = {
                "text": r["text"],
                "source": r["source"],
                "title": r["title"],
                "doc_type": r["doc_type"],
                "semantic_score": 0.0,
                "keyword_score": r["keyword_score"],
                "chunk_idx": r["chunk_idx"],
            }
        else:
            seen[key]["keyword_score"] = max(seen[key]["keyword_score"], r["keyword_score"])

    # 计算综合分数
    for key, data in seen.items():
        combined_score = (
            data["semantic_score"] * semantic_weight +
            data["keyword_score"] * keyword_weight
        )
        combined.append(HybridSearchResult(
            text=data["text"],
            source=data["source"],
            title=data["title"],
            doc_type=data["doc_type"],
            semantic_score=data["semantic_score"],
            keyword_score=data["keyword_score"],
            combined_score=combined_score,
            chunk_idx=data["chunk_idx"],
        ))

    return combined

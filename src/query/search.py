"""语义搜索 — 优化版（带缓存）"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..utils.cache import TTLCache

if TYPE_CHECKING:
    from ..store.vector import VectorStore
    from ..store.embedding import EmbeddingManager


@dataclass
class SearchResult:
    text: str
    source: str
    title: str
    doc_type: str
    score: float       # 越小越相似 (cosine distance)
    chunk_idx: int


# 搜索结果缓存（5 分钟 TTL，最多 256 条）
_search_cache = TTLCache(maxsize=256, ttl=300)


def semantic_search(
    query: str,
    vector_store: VectorStore,
    embedder: EmbeddingManager,
    top_k: int = 5,
    use_cache: bool = True,
) -> list[SearchResult]:
    """执行语义搜索，返回最相关的文档块。

    优化点：
    1. 查询结果缓存（TTL=5分钟）
    2. 嵌入向量缓存（在 EmbeddingManager 中）
    """
    # 检查缓存
    if use_cache:
        cache_key = TTLCache.make_key(query, top_k)
        cached = _search_cache.get(cache_key)
        if cached is not None:
            return cached

    # 生成查询向量（EmbeddingManager 内部有缓存）
    query_vec = embedder.embed_query(query)

    # 向量检索
    results = vector_store.search(query_vec, top_k=top_k)

    items = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    for text, meta, dist in zip(docs, metas, dists):
        items.append(SearchResult(
            text=text,
            source=meta.get("source", ""),
            title=meta.get("title", ""),
            doc_type=meta.get("doc_type", ""),
            score=dist,
            chunk_idx=meta.get("chunk_idx", 0),
        ))

    # 写入缓存
    if use_cache:
        _search_cache.set(cache_key, items)

    return items


def clear_search_cache():
    """清空搜索缓存（文档更新后调用）"""
    _search_cache.clear()

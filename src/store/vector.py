"""ChromaDB 向量存储"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import chromadb

if TYPE_CHECKING:
    from ..config import Settings

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB 封装，管理文档块的向量索引。"""

    COLLECTION_NAME = "knowledge_base"

    def __init__(self, settings: Settings):
        self.db_path = str(settings.chroma_dir)
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
    ) -> None:
        """添加文档块到向量库。"""
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        # 清除搜索缓存
        self._invalidate_cache()

    def search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> dict:
        """语义搜索，返回 top_k 最相似的块。"""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        return results

    def count(self) -> int:
        return self.collection.count()

    def delete_by_source(self, source: str) -> int:
        """删除指定来源的所有块，返回删除数量。"""
        results = self.collection.get(where={"source": source})
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            self._invalidate_cache()
            return len(results["ids"])
        return 0

    def _invalidate_cache(self):
        """清除相关缓存"""
        try:
            from ..query.search import clear_search_cache
            clear_search_cache()
        except ImportError:
            pass

    def list_sources(self) -> list[str]:
        """列出所有不重复的来源。"""
        all_meta = self.collection.get(include=["metadatas"])
        sources = set()
        for m in all_meta["metadatas"]:
            if m and "source" in m:
                sources.add(m["source"])
        return sorted(sources)

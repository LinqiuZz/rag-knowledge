"""向量数据库抽象层 — 支持 Milvus / Qdrant / Chroma

提供统一的向量存储接口，支持标量过滤（is_active、permission_ids）。

每种后端负责提供:
  - add(ids, documents, embeddings, metadatas) → 插入/更新向量
  - search(query_embedding, top_k, filter_expr) → ANN 搜索
  - delete_by_filter(filter_expr) → 条件删除
  - count() → 向量数量
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class BaseVectorStore(ABC):
    """向量存储抽象基类。"""

    @abstractmethod
    def add(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
    ) -> None:
        """添加/更新向量。"""

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 50,
        filter_expr: dict | str | None = None,
    ) -> dict:
        """语义搜索。
        返回格式: {"ids": [...], "documents": [...], "metadatas": [...], "distances": [...]}
        """

    @abstractmethod
    def delete_by_filter(self, filter_expr: dict | str) -> int:
        """按条件删除，返回删除数量。"""

    @abstractmethod
    def count(self) -> int:
        """向量总数。"""

    def delete_by_source(self, source: str) -> int:
        """按 source 字段删除（兼容旧接口）。"""
        return self.delete_by_filter({"source": source})


# ═══════════════════════════════════════════════════════════════
# Chroma 实现（向后兼容）
# ═══════════════════════════════════════════════════════════════

class ChromaVectorStore(BaseVectorStore):
    """ChromaDB 后端 — 轻量级，适合本地开发。"""

    COLLECTION_NAME = "knowledge_base"

    def __init__(self, settings):
        import chromadb
        self.db_path = str(settings.chroma_dir)
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": settings.vector_db.distance_metric},
        )

    def add(self, ids, documents, embeddings, metadatas=None):
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        self._invalidate_cache()

    def search(self, query_embedding, top_k=50, filter_expr=None):
        where_filter = None
        # Chroma 支持简单的 where 过滤
        if isinstance(filter_expr, dict):
            where_filter = filter_expr

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
        return results

    def delete_by_filter(self, filter_expr):
        if isinstance(filter_expr, dict) and "source" in filter_expr:
            results = self.collection.get(where={"source": filter_expr["source"]})
            if results["ids"]:
                self.collection.delete(ids=results["ids"])
                self._invalidate_cache()
                return len(results["ids"])
        return 0

    def count(self) -> int:
        return self.collection.count()

    def _invalidate_cache(self):
        try:
            from ..query.search import clear_search_cache
            clear_search_cache()
        except ImportError:
            pass


# ═══════════════════════════════════════════════════════════════
# Qdrant 实现
# ═══════════════════════════════════════════════════════════════

class QdrantVectorStore(BaseVectorStore):
    """Qdrant 后端 — 性能好，过滤友好，推荐生产使用。"""

    def __init__(self, settings):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        self.settings = settings
        self.collection_name = settings.vector_db.collection_name

        self.client = QdrantClient(
            url=settings.vector_db.qdrant_url,
            api_key=settings.vector_db.qdrant_api_key or None,
        )

        # 确保 collection 存在
        distance = Distance.COSINE if settings.vector_db.distance_metric == "cosine" else Distance.EUCLID
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=settings.embedding.dimension,
                    distance=distance,
                ),
            )
            logger.info("创建 Qdrant collection: %s", self.collection_name)

    @staticmethod
    def _build_filter(filter_expr: dict | None):
        """从 dict 构建 Qdrant Filter 对象。"""
        if not filter_expr:
            return None
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        conditions = [
            FieldCondition(key=k, match=MatchValue(value=v))
            for k, v in filter_expr.items()
        ]
        return Filter(must=conditions) if conditions else None

    def add(self, ids, documents, embeddings, metadatas=None):
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(
                id=pid, vector=emb,
                payload={"document": doc, **((metadatas[i] or {}) if metadatas and i < len(metadatas) else {})}
            )
            for i, (pid, doc, emb) in enumerate(zip(ids, documents, embeddings))
        ]

        # 分批上传
        batch_size = 100
        for start in range(0, len(points), batch_size):
            self.client.upsert(
                collection_name=self.collection_name,
                points=points[start:start + batch_size],
            )

        self._invalidate_cache()

    def search(self, query_embedding, top_k=50, filter_expr=None):
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=self._build_filter(filter_expr),
            with_payload=True,
        )

        return {
            "ids": [[str(r.id) for r in results]],
            "documents": [[r.payload.get("document", "") for r in results]],
            "metadatas": [[{k: v for k, v in r.payload.items() if k != "document"} for r in results]],
            "distances": [[r.score for r in results]],
        }

    def delete_by_filter(self, filter_expr):
        query_filter = self._build_filter(filter_expr) if isinstance(filter_expr, dict) else None

        if query_filter:
            result = self.client.delete(
                collection_name=self.collection_name,
                points_selector=query_filter,
            )
            self._invalidate_cache()
            return result.status == "completed" and 1 or 0
        return 0

    def count(self) -> int:
        info = self.client.get_collection(self.collection_name)
        return info.points_count

    def _invalidate_cache(self):
        try:
            from ..query.search import clear_search_cache
            clear_search_cache()
        except ImportError:
            pass


# ═══════════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════════

def create_vector_store(settings) -> BaseVectorStore:
    """根据配置创建向量存储实例。"""
    provider = settings.vector_db.provider

    if provider == "qdrant":
        try:
            return QdrantVectorStore(settings)
        except ImportError:
            logger.warning("qdrant-client 未安装，回退到 Chroma")
            return ChromaVectorStore(settings)
        except Exception as e:
            logger.warning("Qdrant 连接失败 (%s)，回退到 Chroma", e)
            return ChromaVectorStore(settings)

    elif provider == "milvus":
        try:
            from .vector_milvus import MilvusVectorStore
            return MilvusVectorStore(settings)
        except ImportError:
            logger.warning("pymilvus 未安装，回退到 Chroma")
            return ChromaVectorStore(settings)
        except Exception as e:
            logger.warning("Milvus 连接失败 (%s)，回退到 Chroma", e)
            return ChromaVectorStore(settings)

    else:
        return ChromaVectorStore(settings)

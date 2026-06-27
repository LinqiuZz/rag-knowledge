"""存储层 — 向量数据库 + 元数据库 + 对象存储

导出:
  - create_vector_store: 向量数据库工厂（Qdrant/Milvus/Chroma）
  - MetadataStore: PostgreSQL 元数据存储
  - EmbeddingManager: 嵌入模型管理器
  - MinIOStorage: 对象存储服务
"""

from .vector import create_vector_store, BaseVectorStore, ChromaVectorStore, QdrantVectorStore
from .metadata import MetadataStore
from .embedding import EmbeddingManager
from .storage import MinIOStorage

__all__ = [
    "create_vector_store",
    "BaseVectorStore",
    "ChromaVectorStore",
    "QdrantVectorStore",
    "MetadataStore",
    "EmbeddingManager",
    "MinIOStorage",
]

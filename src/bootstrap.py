"""组件引导 — 统一初始化入口

CLI 和 API 共享的组件工厂，避免重复初始化逻辑。

用法:
    from src.bootstrap import bootstrap
    ctx = bootstrap()
    # ctx.settings, ctx.embedder, ctx.vector_store, ctx.meta_store, ctx.storage, ctx.llm
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from .config import Settings, load_settings
from .store.vector import create_vector_store, BaseVectorStore
from .store.embedding import EmbeddingManager
from .store.storage import MinIOStorage
from .llm.base import BaseLLM, get_llm

if TYPE_CHECKING:
    from .store.metadata import MetadataStore

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """应用上下文 — 持有所有服务组件的引用。"""
    settings: Settings
    embedder: EmbeddingManager
    vector_store: BaseVectorStore
    meta_store: Optional[MetadataStore]
    storage: MinIOStorage
    llm: BaseLLM
    _pipeline: object = None  # Cached RetrievalPipeline

    @property
    def pipeline(self):
        if self._pipeline is None:
            from .query.retrieval import RetrievalPipeline
            self._pipeline = RetrievalPipeline(self.settings, llm=self.llm)
        return self._pipeline

    def close(self):
        """关闭所有连接。"""
        if self.meta_store:
            try:
                self.meta_store.close()
            except Exception:
                pass


def bootstrap(
    config_path: str | None = None,
    llm_backend: str | None = None,
) -> AppContext:
    """初始化所有组件。企业服务（PostgreSQL/MinIO）不可用时自动降级。"""
    settings = load_settings(config_path)

    if llm_backend:
        settings.llm.default = llm_backend

    embedder = EmbeddingManager(settings, preload=False)
    vector_store = create_vector_store(settings)

    # 元数据存储：PostgreSQL → SQLite 自动降级
    meta_store = None
    try:
        from .store.metadata import MetadataStore as PgMetadataStore
        pg = PgMetadataStore(settings)
        # 测试连接是否可用
        pg._ensure_connected()
        meta_store = pg
        logger.info("元数据存储: PostgreSQL")
    except Exception as e:
        logger.info("PostgreSQL 不可用 (%s)，使用 SQLite", e)
        try:
            from .store.metadata_sqlite import MetadataStore as SqliteMetadataStore
            meta_store = SqliteMetadataStore(settings)
            logger.info("元数据存储: SQLite")
        except Exception as e2:
            logger.error("SQLite 也失败: %s", e2)

    # MinIO — 连接失败自动回退到本地文件
    storage = MinIOStorage(settings)

    llm = get_llm(settings.llm.default, settings)

    return AppContext(
        settings=settings,
        embedder=embedder,
        vector_store=vector_store,
        meta_store=meta_store,
        storage=storage,
        llm=llm,
    )

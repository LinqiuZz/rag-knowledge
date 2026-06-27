"""检索服务 — 语义搜索、混合检索、重排序、权限过滤"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RetrievalService:
    """检索服务。

    职责:
      - 语义搜索（ANN）
      - 混合检索（语义 + 关键词）
      - Cross-Encoder 重排序
      - 权限过滤（向量数据库标量过滤）
      - Small-to-Big 上下文扩展
      - 加权综合评分
    """

    def __init__(self, settings, embedder, vector_store, meta_store=None):
        self.settings = settings
        self.embedder = embedder
        self.vector_store = vector_store
        self.meta_store = meta_store

    def search(
        self, query: str, top_k: int = 5,
        user_id: int = None, use_hybrid: bool = False,
        use_rerank: bool = True,
    ) -> dict:
        """执行检索并返回结果。

        Returns:
            {
                "hits": list[RetrievalHit],
                "context": str,       # 构建好的 LLM 上下文
                "sources": list[dict], # 来源引用
                "stats": dict,        # 检索统计
            }
        """
        from ..query.retrieval import RetrievalPipeline, build_rag_context

        pipeline = RetrievalPipeline(self.settings)
        result = pipeline.retrieve(
            query=query,
            embedder=self.embedder,
            vector_store=self.vector_store,
            meta_store=self.meta_store,
            user_id=user_id,
            use_hybrid=use_hybrid,
            use_rerank=use_rerank,
            expand_context=True,
        )

        hits = result.hits[:top_k]
        context, sources = build_rag_context(hits)

        return {
            "hits": hits,
            "context": context,
            "sources": sources,
            "stats": {
                "total_candidates": result.total_candidates,
                "filtered_count": result.filtered_count,
                "reranked_count": result.reranked_count,
                "final_count": result.final_count,
            },
        }

    def get_accessible_doc_ids(self, user_id: int) -> list[int]:
        """获取用户可访问的文档 ID 列表。"""
        if self.meta_store:
            try:
                return self.meta_store.get_accessible_doc_ids(user_id)
            except Exception:
                pass
        return []

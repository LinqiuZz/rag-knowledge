"""本地嵌入模型管理器 — 优化版"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..utils.cache import TTLCache

if TYPE_CHECKING:
    from ..config import Settings

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """使用 sentence-transformers 加载本地嵌入模型。

    优化点：
    1. 嵌入结果缓存（TTL=10分钟）
    2. 模型预热（启动时加载）
    3. 批量编码优化
    """

    def __init__(self, settings: Settings, preload: bool = True):
        self.model_name = settings.embedding.model_name
        self.device = settings.embedding.device
        self._model = None
        self._cache = TTLCache(maxsize=512, ttl=600)  # 嵌入缓存 10 分钟

        if preload:
            self._ensure_model()

    def _ensure_model(self):
        """确保模型已加载"""
        if self._model is None:
            logger.info(f"加载嵌入模型: {self.model_name} (device={self.device})")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                self.model_name, device=self.device
            )
            logger.info("嵌入模型加载完成")

    @property
    def model(self):
        self._ensure_model()
        return self._model

    def embed(self, texts: list[str], use_cache: bool = True) -> list[list[float]]:
        """批量生成嵌入向量（带缓存）。"""
        if not texts:
            return []

        # 检查缓存
        if use_cache:
            cached_results = []
            uncached_indices = []
            uncached_texts = []

            for i, text in enumerate(texts):
                key = TTLCache.make_key(text)
                val = self._cache.get(key)
                if val is not None:
                    cached_results.append((i, val))
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(text)

            # 全部命中缓存
            if not uncached_texts:
                return [r[1] for r in sorted(cached_results, key=lambda x: x[0])]

            # 编码未缓存的文本
            new_embeddings = self.model.encode(
                uncached_texts, normalize_embeddings=True, show_progress_bar=False
            ).tolist()

            # 写入缓存
            for text, emb in zip(uncached_texts, new_embeddings):
                self._cache.set(TTLCache.make_key(text), emb)

            # 合并结果
            result = [None] * len(texts)
            for i, emb in cached_results:
                result[i] = emb
            for i, emb in zip(uncached_indices, new_embeddings):
                result[i] = emb
            return result
        else:
            embeddings = self.model.encode(
                texts, normalize_embeddings=True, show_progress_bar=False
            )
            return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """为查询生成嵌入向量（带缓存）。"""
        return self.embed([query], use_cache=True)[0]

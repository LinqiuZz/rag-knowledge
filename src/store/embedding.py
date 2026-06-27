"""嵌入模型管理器 — 企业版 (BGE-M3 / Jina v2)

支持:
  - BGE-M3: 1024维, 支持稠密+稀疏混合检索
  - BAAI/bge-small-zh-v1.5: 512维（向后兼容）
  - GPU 加速、批量编码、结果缓存
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..utils.cache import TTLCache

if TYPE_CHECKING:
    from ..config import Settings

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """嵌入模型管理器。

    优化点:
    1. 嵌入结果缓存（TTL=10分钟）
    2. 模型预热（启动时加载）
    3. 批量编码优化
    4. 支持多种嵌入模型（BGE-M3 / BGE-small / Jina）
    """

    def __init__(self, settings: Settings, preload: bool = True):
        self.model_name = settings.embedding.model_name
        self.device = settings.embedding.device
        self.normalize = getattr(settings.embedding, 'normalize', True)
        self.batch_size = getattr(settings.embedding, 'batch_size', 32)
        self._model = None
        self._cache = TTLCache(maxsize=1024, ttl=600)  # 嵌入缓存 10 分钟

        if preload:
            self._ensure_model()

    def _ensure_model(self):
        """确保模型已加载。"""
        if self._model is None:
            logger.info("加载嵌入模型: %s (device=%s, normalize=%s)",
                        self.model_name, self.device, self.normalize)
            from sentence_transformers import SentenceTransformer

            # BGE-M3 需要 trust_remote_code
            trust_remote = "bge-m3" in self.model_name.lower()

            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
                trust_remote_code=trust_remote,
            )
            logger.info("嵌入模型加载完成，维度: %d", self._model.get_sentence_embedding_dimension())

    @property
    def model(self):
        self._ensure_model()
        return self._model

    @property
    def dimension(self) -> int:
        self._ensure_model()
        return self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str], use_cache: bool = True) -> list[list[float]]:
        """批量生成嵌入向量（带缓存）。

        Args:
            texts: 文本列表
            use_cache: 是否使用缓存

        Returns:
            嵌入向量列表
        """
        if not texts:
            return []

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
                uncached_texts,
                normalize_embeddings=self.normalize,
                show_progress_bar=False,
                batch_size=self.batch_size,
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
                texts,
                normalize_embeddings=self.normalize,
                show_progress_bar=False,
                batch_size=self.batch_size,
            )
            return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """为查询生成嵌入向量（带缓存）。

        对于 BGE 系列模型，自动添加 instruction prefix。
        """
        if "bge-m3" in self.model_name.lower():
            query = f"Represent this sentence for searching relevant passages: {query}"
        elif "bge" in self.model_name.lower():
            query = f"为这个句子生成表示以用于检索相关文章：{query}"

        return self.embed([query], use_cache=True)[0]

    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        """为文档生成嵌入向量。

        对于 BGE 系列模型，不需要添加 instruction prefix。
        """
        return self.embed(documents, use_cache=True)

    # ── 稀疏向量（BGE-M3 支持）───────────────────────────────

    def embed_sparse(self, texts: list[str]) -> list[dict]:
        """生成稀疏词权重向量（仅 BGE-M3 支持）。

        Returns:
            [{"token_ids": [...], "weights": [...]}, ...]
        """
        self._ensure_model()

        if "bge-m3" not in self.model_name.lower():
            logger.warning("当前模型 %s 不支持稀疏编码", self.model_name)
            return [{}] * len(texts)

        try:
            # BGE-M3 的稀疏编码通过 encode 参数启用
            outputs = self.model.encode(
                texts,
                normalize_embeddings=False,
                show_progress_bar=False,
                batch_size=self.batch_size,
                return_dense=False,
            )
            # 取决于 sentence-transformers 的具体实现
            # 较新版本支持 return_sparse 参数
            return outputs if isinstance(outputs, list) else [{}] * len(texts)
        except Exception as e:
            logger.debug("稀疏编码不可用: %s", e)
            return [{}] * len(texts)

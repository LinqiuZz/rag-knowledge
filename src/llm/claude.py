"""Claude API 后端 — 优化版"""

from __future__ import annotations

import logging
from .base import BaseLLM
from ..utils.cache import TTLCache

logger = logging.getLogger(__name__)


class ClaudeLLM(BaseLLM):

    def __init__(self, settings):
        self.model = settings.llm.claude_model
        self.base_url = settings.llm.claude_base_url
        self.api_key = settings.llm.claude_api_key
        self._client = None
        self._cache = TTLCache(maxsize=128, ttl=600)  # 响应缓存 10 分钟

    @property
    def client(self):
        """懒加载并缓存客户端实例（连接池复用）"""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
                max_retries=2,           # 自动重试
                timeout=60.0,            # 超时设置
            )
            logger.info(f"Claude 客户端初始化完成: {self.base_url}")
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key)

    def chat(self, system: str, user: str, max_tokens: int = 2048) -> str:
        # 检查缓存（仅缓存短问题的回答）
        cache_key = TTLCache.make_key(system, user, max_tokens)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("命中 LLM 缓存")
            return cached

        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        answer = resp.content[0].text

        # 缓存结果
        self._cache.set(cache_key, answer)
        return answer

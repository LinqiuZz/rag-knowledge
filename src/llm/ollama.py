"""Ollama 本地后端"""

from __future__ import annotations

import time
from .base import BaseLLM


class OllamaLLM(BaseLLM):

    def __init__(self, settings):
        self.model = settings.llm.ollama_model
        self.url = settings.llm.ollama_url
        self._client = None
        self._available: bool | None = None
        self._available_checked_at: float = 0

    @property
    def client(self):
        """懒加载并缓存客户端实例"""
        if self._client is None:
            import ollama
            self._client = ollama.Client(host=self.url)
        return self._client

    def is_available(self) -> bool:
        now = time.monotonic()
        if self._available is not None and now - self._available_checked_at < 30:
            return self._available
        try:
            self.client.list()
            self._available = True
        except Exception:
            self._available = False
        self._available_checked_at = now
        return self._available

    def chat(self, system: str, user: str, max_tokens: int = 2048) -> str:
        resp = self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            options={"num_predict": max_tokens},
        )
        return resp["message"]["content"]

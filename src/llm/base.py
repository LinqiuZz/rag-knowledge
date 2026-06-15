"""LLM 抽象接口"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """所有 LLM 后端的基类。"""

    @abstractmethod
    def chat(self, system: str, user: str, max_tokens: int = 2048) -> str:
        """发送一条消息，返回文本回复。"""

    @abstractmethod
    def is_available(self) -> bool:
        """检测后端是否可用。"""


def get_llm(backend: str, settings) -> BaseLLM:
    """根据名称返回对应的 LLM 实例。"""
    if backend == "claude":
        from .claude import ClaudeLLM
        return ClaudeLLM(settings)
    elif backend == "ollama":
        from .ollama import OllamaLLM
        return OllamaLLM(settings)
    else:
        raise ValueError(f"未知的 LLM 后端: {backend}，可选: claude, ollama")

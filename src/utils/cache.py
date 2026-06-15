"""缓存工具 — LRU 缓存 + TTL 过期"""

from __future__ import annotations

import time
import hashlib
from functools import lru_cache
from collections import OrderedDict
from threading import Lock
from typing import Any, Callable, Optional


class TTLCache:
    """带过期时间的 LRU 缓存（线程安全）"""

    def __init__(self, maxsize: int = 256, ttl: int = 300):
        """
        Args:
            maxsize: 最大缓存条目数
            ttl: 缓存过期时间（秒），默认 5 分钟
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值，过期返回 None"""
        with self._lock:
            if key not in self._cache:
                return None
            ts, val = self._cache[key]
            if time.time() - ts > self.ttl:
                del self._cache[key]
                return None
            # 移到末尾（LRU）
            self._cache.move_to_end(key)
            return val

    def set(self, key: str, value: Any) -> None:
        """设置缓存值"""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (time.time(), value)
            # 淘汰最旧条目
            while len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()

    @staticmethod
    def make_key(*args, **kwargs) -> str:
        """生成缓存键"""
        raw = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(raw.encode()).hexdigest()


def cached_search(ttl: int = 300, maxsize: int = 256):
    """装饰器：缓存搜索结果"""
    cache = TTLCache(maxsize=maxsize, ttl=ttl)

    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            key = TTLCache.make_key(*args, **kwargs)
            result = cache.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        wrapper.cache_clear = cache.clear
        return wrapper
    return decorator

"""缓存抽象：Redis 后端 + 进程内内存后端，惰性选后端、优雅降级。

- 配置了 `REDIS_URL` 且启动时可 ping 通 → Redis 后端；否则内存字典兜底；
- Redis 运行期异常（如宕机）时，Redis 后端自动回退到内存，不抛给调用方。
"""
import json
import threading
import time

from app.core.config import settings


class MemoryCache:
    """进程内缓存（含 TTL）。"""

    def __init__(self) -> None:
        self._data: dict[str, tuple[float | None, str]] = {}  # key -> (expires_at, raw)
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires_at, raw = item
            if expires_at is not None and time.time() > expires_at:
                self._data.pop(key, None)
                return None
            return json.loads(raw)

    def set(self, key: str, value, ttl: int | None = None) -> None:
        raw = json.dumps(value, ensure_ascii=False, default=str)
        expires_at = (time.time() + ttl) if ttl else None
        with self._lock:
            self._data[key] = (expires_at, raw)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


class RedisCache:
    """Redis 后端；运行期异常回退内存，保证可用性。"""

    def __init__(self, client) -> None:
        self._client = client
        self._fallback = MemoryCache()

    def get(self, key: str):
        try:
            raw = self._client.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return self._fallback.get(key)

    def set(self, key: str, value, ttl: int | None = None) -> None:
        try:
            self._client.set(key, json.dumps(value, ensure_ascii=False, default=str), ex=ttl)
        except Exception:
            self._fallback.set(key, value, ttl)

    def delete(self, key: str) -> None:
        try:
            self._client.delete(key)
        except Exception:
            self._fallback.delete(key)


def _build_backend():
    if settings.REDIS_URL:
        try:
            import redis

            client = redis.from_url(
                settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2
            )
            client.ping()
            return RedisCache(client)
        except Exception:
            pass  # 未安装 redis / 未配置 / 不可达 → 内存兜底
    return MemoryCache()


cache = _build_backend()

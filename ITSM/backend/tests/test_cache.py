"""缓存抽象单测：内存后端（Redis 未配置时的降级路径）。"""
from app.core.cache import cache


def test_cache_roundtrip():
    cache.set("t1", {"a": 1})
    assert cache.get("t1") == {"a": 1}


def test_cache_delete():
    cache.set("t2", "v")
    cache.delete("t2")
    assert cache.get("t2") is None


def test_cache_missing_returns_none():
    assert cache.get("no_such_key_xyz") is None


def test_cache_ttl_expiry():
    cache.set("t3", "v", ttl=-1)  # 立即过期
    assert cache.get("t3") is None

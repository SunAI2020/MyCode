# -*- coding: utf-8 -*-
"""CCMS Redis 客户端 — 异步 Redis 连接管理"""

import redis.asyncio as aioredis
from redis.asyncio import Redis

from ..config import settings

# 全局 Redis 实例（延迟初始化）
_redis: Redis | None = None


async def get_redis() -> Redis:
    """获取或创建 Redis 连接"""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _redis


async def close_redis() -> None:
    """关闭 Redis 连接"""
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


async def publish(channel: str, message: str) -> int:
    """向 Redis 频道发布消息"""
    r = await get_redis()
    return await r.publish(channel, message)


async def subscribe(channel: str):
    """订阅 Redis 频道，返回异步迭代器"""
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    return pubsub


async def cache_get(key: str) -> str | None:
    """从缓存读取"""
    r = await get_redis()
    return await r.get(key)


async def cache_set(key: str, value: str, expire: int = 300) -> None:
    """写入缓存，默认 5 分钟过期"""
    r = await get_redis()
    await r.set(key, value, ex=expire)


async def cache_delete(key: str) -> None:
    """删除缓存"""
    r = await get_redis()
    await r.delete(key)

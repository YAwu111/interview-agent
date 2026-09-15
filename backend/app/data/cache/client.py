import redis.asyncio as redis

from app.core.config import settings


def build_redis() -> redis.Redis:
    """只构造不连接（懒连接）；首个命令时才触达 Redis。"""
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )

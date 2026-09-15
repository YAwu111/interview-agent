"""一次性授权码存储：Redis GETDEL 保证单次使用。接口极小，测试可注入内存实现。"""

import secrets
from typing import Protocol

import redis.asyncio as redis
from fastapi import Request

from app.core.config import settings
from app.data.cache import keys


class CodeStore(Protocol):
    async def issue(self, user_id: str) -> str: ...
    async def consume(self, code: str) -> str | None: ...


class RedisCodeStore:
    def __init__(self, client: redis.Redis) -> None:
        self.client = client

    async def issue(self, user_id: str) -> str:
        code = secrets.token_urlsafe(32)
        await self.client.set(keys.OAUTH_CODE + code, user_id, ex=settings.code_ttl_seconds)
        return code

    async def consume(self, code: str) -> str | None:
        return await self.client.getdel(keys.OAUTH_CODE + code)


def get_code_store(request: Request) -> CodeStore:
    return RedisCodeStore(request.app.state.redis)

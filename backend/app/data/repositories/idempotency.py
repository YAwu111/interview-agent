"""幂等仓储：Redis 快速状态（in-flight/completed）+ PG 兜底持久化。"""

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.data.cache.keys import IDEMPOTENCY
from app.data.db.models.idempotency import IdempotencyRecord

INFLIGHT_TTL_SECONDS = 300
COMPLETED_TTL_SECONDS = 24 * 60 * 60


def _redis_key(key: str) -> str:
    return f"{IDEMPOTENCY}{key}"


class IdempotencyRepository:
    def __init__(self, redis: Any, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._redis = redis
        self._sessionmaker = sessionmaker

    async def find(self, key: str) -> dict | None:
        raw = await self._redis.get(_redis_key(key))
        if raw:
            return json.loads(raw)
        async with self._sessionmaker() as s:
            row = (
                await s.scalars(
                    select(IdempotencyRecord).where(IdempotencyRecord.key == key)
                )
            ).first()
        if row is None:
            return None
        return {
            "status": "completed",
            "payload_hash": row.payload_hash,
            "status_code": row.status_code,
            "content_type": row.content_type,
            "response_body": row.response_body,
        }

    async def try_inflight(self, key: str, payload_hash: str) -> bool:
        payload = json.dumps({"status": "inflight", "payload_hash": payload_hash})
        return bool(
            await self._redis.set(
                _redis_key(key), payload, nx=True, ex=INFLIGHT_TTL_SECONDS
            )
        )

    async def complete(
        self,
        *,
        key: str,
        method: str,
        path: str,
        payload_hash: str,
        status_code: int,
        content_type: str | None,
        response_body: Any,
    ) -> None:
        payload = json.dumps(
            {
                "status": "completed",
                "payload_hash": payload_hash,
                "status_code": status_code,
                "content_type": content_type,
                "response_body": response_body,
            },
            ensure_ascii=False,
        )
        await self._redis.set(_redis_key(key), payload, ex=COMPLETED_TTL_SECONDS)
        async with self._sessionmaker() as s:
            stmt = insert(IdempotencyRecord).values(
                key=key,
                method=method,
                path=path,
                payload_hash=payload_hash,
                status_code=status_code,
                content_type=content_type,
                response_body=response_body,
            )
            await s.execute(stmt.on_conflict_do_nothing(index_elements=["key"]))
            await s.commit()

    async def fail(self, key: str) -> None:
        await self._redis.delete(_redis_key(key))


async def prune_expired(session: AsyncSession, older_than) -> int:
    """清理超过保留期的幂等兜底行，避免 PG 表只进不出。"""
    result = await session.execute(
        delete(IdempotencyRecord).where(IdempotencyRecord.created_at < older_than)
    )
    return result.rowcount

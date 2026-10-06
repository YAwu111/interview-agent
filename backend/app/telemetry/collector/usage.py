"""Redis + PG 用量采集实现（UsageSink）。"""

from datetime import date
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.data.cache.keys import USAGE
from app.data.db.models.usage import UsageDaily

RETENTION_SECONDS = 32 * 24 * 60 * 60


def _key(user_id: str, model: str, day: date) -> str:
    return f"{USAGE}{user_id}:{model}:{day.isoformat()}"


class RedisUsageSink:
    def __init__(self, redis: Any, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._redis = redis
        self._sessionmaker = sessionmaker

    async def record(self, user_id: str, usage: dict) -> None:
        model = usage.get("model") or "unknown"
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        latency = int(usage.get("latency_ms") or 0)
        total = prompt + completion
        day = date.today()
        key = _key(user_id, model, day)

        pipe = self._redis.pipeline()
        pipe.hincrby(key, "prompt_tokens", prompt)
        pipe.hincrby(key, "completion_tokens", completion)
        pipe.hincrby(key, "total_tokens", total)
        pipe.hincrby(key, "calls", 1)
        pipe.hincrby(key, "latency_sum_ms", latency)
        pipe.expire(key, RETENTION_SECONDS)
        await pipe.execute()

        async with self._sessionmaker() as s:
            stmt = insert(UsageDaily).values(
                user_id=user_id,
                model=model,
                date=day,
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=total,
                calls=1,
                latency_sum_ms=latency,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id", "model", "date"],
                set_={
                    "prompt_tokens": UsageDaily.prompt_tokens + prompt,
                    "completion_tokens": UsageDaily.completion_tokens + completion,
                    "total_tokens": UsageDaily.total_tokens + total,
                    "calls": UsageDaily.calls + 1,
                    "latency_sum_ms": UsageDaily.latency_sum_ms + latency,
                },
            )
            await s.execute(stmt)
            await s.commit()

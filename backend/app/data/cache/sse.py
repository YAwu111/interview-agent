"""SSE 事件流暂存：后台生成写入 Redis，SSE 端点按游标续读。"""

import json
from typing import Any

from app.data.cache.keys import SSE, SSE_META

STREAM_TTL_SECONDS = 10 * 60
META_TTL_SECONDS = 15 * 60


def _stream_key(session_id: str, message_id: str) -> str:
    return f"{SSE}{session_id}:{message_id}"


def _meta_key(session_id: str, message_id: str) -> str:
    return f"{SSE_META}{session_id}:{message_id}"


async def append_event(
    redis: Any, session_id: str, message_id: str, seq: int, payload: dict
) -> None:
    value = json.dumps({"seq": seq, "payload": payload}, ensure_ascii=False)
    key = _stream_key(session_id, message_id)
    await redis.rpush(key, value)
    await redis.expire(key, STREAM_TTL_SECONDS)


async def set_meta(
    redis: Any,
    session_id: str,
    message_id: str,
    status: str,
    last_seq: int,
) -> None:
    value = json.dumps({"status": status, "last_seq": last_seq}, ensure_ascii=False)
    key = _meta_key(session_id, message_id)
    await redis.set(key, value, ex=META_TTL_SECONDS)


async def get_meta(redis: Any, session_id: str, message_id: str) -> dict | None:
    raw = await redis.get(_meta_key(session_id, message_id))
    return json.loads(raw) if raw else None


async def read_tail(
    redis: Any, session_id: str, message_id: str, after_seq: int
) -> list[dict]:
    """返回 seq > after_seq 的事件；文本流较短，直接 LRANGE 全量解析。"""
    rows = await redis.lrange(_stream_key(session_id, message_id), 0, -1)
    out: list[dict] = []
    for row in rows:
        item = json.loads(row)
        if item["seq"] > after_seq:
            out.append(item)
    return out


async def delete_stream(redis: Any, session_id: str, message_id: str) -> None:
    await redis.delete(_stream_key(session_id, message_id), _meta_key(session_id, message_id))

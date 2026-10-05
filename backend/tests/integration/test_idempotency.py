"""幂等中间件集成：同 key 同 payload 重放、同 key 不同 payload 409、in-flight 409。"""

import asyncio
import json

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.access.auth.service import create_access_token
from app.data.db.models.chat import Session
from main import app
from tests.conftest import TestSession, make_redis


def _headers(key: str) -> dict:
    return {
        "Authorization": f"Bearer {create_access_token('u-idem')}",
        "Idempotency-Key": key,
    }


def test_idempotency_replay_conflict_and_inflight(client: TestClient) -> None:
    app.state.redis = make_redis()
    app.state.sessionmaker = TestSession
    app.state.chat_service = None

    headers = _headers("key-same")
    first = client.post("/api/v1/chat/sessions", json={"mode": "chat"}, headers=headers)
    assert first.status_code == 200
    first_id = first.json()["id"]

    replay = client.post("/api/v1/chat/sessions", json={"mode": "chat"}, headers=headers)
    assert replay.status_code == 200
    assert replay.json()["id"] == first_id

    conflict = client.post(
        "/api/v1/chat/sessions", json={"mode": "interview"}, headers=headers
    )
    assert conflict.status_code == 409

    async def count_sessions() -> int:
        async with TestSession() as s:
            return (
                await s.scalars(select(func.count()).select_from(Session))
            ).one()

    assert asyncio.run(count_sessions()) == 1

    # 预置 in-flight 状态，验证不重复执行
    async def seed_inflight() -> None:
        r = make_redis()
        await r.set(
            "idem:key-inflight",
            json.dumps({"status": "inflight", "payload_hash": "whatever"}),
        )
        await r.aclose()

    asyncio.run(seed_inflight())

    busy = client.post(
        "/api/v1/chat/sessions", json={"mode": "chat"}, headers=_headers("key-inflight")
    )
    assert busy.status_code == 409

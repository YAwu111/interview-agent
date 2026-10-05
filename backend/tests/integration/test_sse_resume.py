"""SSE 续传端点：从 Last-Event-ID 之后补推 Redis 事件流。"""

import json

from fastapi.testclient import TestClient

from app.access.auth.service import create_access_token
from app.domains.chat.service import ChatService
from main import app
from tests.conftest import TestSession, make_redis


class _FakeRetriever:
    async def retrieve(self, query: str, top_k: int | None = None) -> list[dict]:
        return [
            {
                "id": "c1",
                "title": "面经",
                "text": "React 并发渲染区别于虚拟 DOM diff。",
                "snippet": "React 并发渲染",
                "base_name": "知识库",
                "score": 0.9,
            }
        ]


class _FakeLLM:
    async def stream(self, messages, model, **kwargs):
        for ch in ["你", "好", "，", "面", "试", "官"]:
            yield {"type": "delta", "content": ch}


def _headers(extra: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {create_access_token('u-sse')}"}
    if extra:
        h.update(extra)
    return h


def _events(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        if line.startswith("data: "):
            out.append(json.loads(line[6:]))
    return out


def test_sse_resume_replays_from_cursor(client: TestClient, monkeypatch) -> None:
    app.state.redis = make_redis()
    app.state.sessionmaker = TestSession
    app.state.chat_service = None

    async def fake_retriever(self):
        return _FakeRetriever()

    monkeypatch.setattr(ChatService, "_get_retriever", fake_retriever)
    monkeypatch.setattr(ChatService, "_client", lambda self: _FakeLLM())

    sid = client.post(
        "/api/v1/chat/sessions", json={"mode": "chat"}, headers=_headers()
    ).json()["id"]

    stream = client.post(
        f"/api/v1/chat/sessions/{sid}/stream", json={"text": "自我介绍"}, headers=_headers()
    )
    assert stream.status_code == 200
    events = _events(stream.text)
    message_id = next(e["messageId"] for e in events if e.get("type") == "meta")
    last_id = max(e["eventId"] for e in events if "eventId" in e)
    deltas = "".join(e.get("content", "") for e in events if e.get("type") == "delta")
    assert "你好" in deltas

    replay = client.get(
        f"/api/v1/chat/sessions/{sid}/messages/{message_id}/stream",
        headers=_headers({"Last-Event-ID": "0"}),
    )
    replay_events = _events(replay.text)
    replay_deltas = "".join(
        e.get("content", "") for e in replay_events if e.get("type") == "delta"
    )
    assert "你好" in replay_deltas
    assert any(e.get("type") == "done" for e in replay_events)

    tail = client.get(
        f"/api/v1/chat/sessions/{sid}/messages/{message_id}/stream",
        headers=_headers({"Last-Event-ID": str(last_id)}),
    )
    tail_events = _events(tail.text)
    assert not any(e.get("type") == "delta" for e in tail_events)
    assert any(e.get("type") == "done" for e in tail_events)

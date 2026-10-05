"""chat 域 API 集成：会话 CRUD + 流式 SSE（打桩 retriever/LLM，不调真实模型）。"""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.access.auth.service import create_access_token
from app.data.db.models.chat import Message
from app.data.db.models.report import InterviewReport
from app.domains.chat import repository
from app.domains.chat.service import ChatService
from tests.conftest import TestSession


class _FakeRetriever:
    async def retrieve(self, query: str, top_k: int | None = None) -> list[dict]:
        return [
            {
                "id": "c1",
                "title": "前端面经",
                "text": "React 并发渲染通过并发特性协调优先级，区别于虚拟 DOM 的 diff 机制。",
                "snippet": "React 并发渲染通过并发特性协调优先级",
                "base_name": "面试知识库",
                "score": 0.9,
            }
        ]


class _FakeLLM:
    async def stream(self, messages, model, **kwargs):
        for ch in ["你", "好", "，", "面", "试", "官"]:
            yield {"type": "delta", "content": ch}


def _headers() -> dict:
    return {"Authorization": f"Bearer {create_access_token('u-chat-test')}"}


def test_chat_stream_end_to_end(client: TestClient, monkeypatch) -> None:
    async def fake_retriever(self):
        return _FakeRetriever()

    monkeypatch.setattr(ChatService, "_get_retriever", fake_retriever)
    monkeypatch.setattr(ChatService, "_client", lambda self: _FakeLLM())

    headers = _headers()
    res = client.post("/api/v1/chat/sessions", json={"mode": "chat"}, headers=headers)
    assert res.status_code == 200
    sid = res.json()["id"]
    assert res.json()["title"] == "新会话"

    stream = client.post(
        f"/api/v1/chat/sessions/{sid}/stream", json={"text": "自我介绍"}, headers=headers
    )
    assert stream.status_code == 200
    assert '"status"' in stream.text and '"sources"' in stream.text and '"done"' in stream.text

    msgs = client.get(f"/api/v1/chat/sessions/{sid}/messages", headers=headers).json()
    assert any(m["role"] == "user" and m["content"] == "自我介绍" for m in msgs)
    assert any(m["role"] == "assistant" and m["content"] == "你好，面试官" for m in msgs)

    assert client.delete(f"/api/v1/chat/sessions/{sid}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/chat/sessions/{sid}/messages", headers=headers).status_code == 404


def test_foreign_session_404(client: TestClient) -> None:
    headers = _headers()
    assert (
        client.get("/api/v1/chat/sessions/not-exist/messages", headers=headers).status_code == 404
    )


def test_delete_session_with_report_no_500(client: TestClient) -> None:
    """回归：有报告的面试会话删除不应触发 FK 违规 500。"""
    import asyncio

    headers = _headers()
    sid = client.post("/api/v1/chat/sessions", json={"mode": "interview"}, headers=headers).json()[
        "id"
    ]

    async def seed() -> None:
        async with TestSession() as s:
            s.add(
                InterviewReport(
                    session_id=sid,
                    user_id="u-chat-test",
                    overall=4,
                    dimensions=[],
                    strengths=[],
                    weaknesses=[],
                    next_steps=[],
                    end_reason="user_end",
                    model_used="deepseek-chat",
                )
            )
            await s.commit()

    asyncio.run(seed())
    assert client.delete(f"/api/v1/chat/sessions/{sid}", headers=headers).status_code == 200

    async def assert_gone() -> None:
        async with TestSession() as s:
            left = (
                await s.scalars(select(InterviewReport).where(InterviewReport.session_id == sid))
            ).first()
            assert left is None

    asyncio.run(assert_gone())


def test_delete_session_other_user_data_preserved() -> None:
    """回归：user_id 过滤——A 不能借删除操作清掉 B 会话下的报告/消息（路由校验被绕过时的仓储层兜底）。"""
    import asyncio

    async def scenario() -> None:
        async with TestSession() as s:
            b_session = await repository.create_session(s, "user-b", "chat", "B 的会话")
            await repository.create_message(s, b_session.id, "user", "B 的提问")
            s.add(
                InterviewReport(
                    session_id=b_session.id,
                    user_id="user-b",
                    overall=4,
                    dimensions=[],
                    strengths=[],
                    weaknesses=[],
                    next_steps=[],
                    end_reason="user_end",
                    model_used="deepseek-chat",
                )
            )
            await s.flush()

            # A 传入 B 的 session_id + A 自己的 user_id 执行删除
            await repository.delete_session(s, b_session.id, "user-a")

            # B 的会话/消息/报告均须保留
            assert await repository.get_session(s, b_session.id, "user-b") is not None
            left_msg = (
                await s.scalars(select(Message).where(Message.session_id == b_session.id))
            ).first()
            assert left_msg is not None and left_msg.content == "B 的提问"
            left_report = (
                await s.scalars(
                    select(InterviewReport).where(InterviewReport.session_id == b_session.id)
                )
            ).first()
            assert left_report is not None

    asyncio.run(scenario())

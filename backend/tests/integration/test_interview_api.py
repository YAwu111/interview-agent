"""面试模式 HTTP/SSE 端到端：注入 fake runner，覆盖 /stream 开场→回答→/end→幂等。"""

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.access.auth.service import create_access_token
from app.data.db.models.report import InterviewReport
from app.orchestration.agents.interview.runner import InterviewRunner
from main import app
from tests.conftest import TestSession
from tests.interview_fakes import fake_deps


def _headers() -> dict:
    return {"Authorization": f"Bearer {create_access_token('u-interview-api')}"}


def test_interview_stream_and_end(client: TestClient) -> None:
    app.state.interview_runner = InterviewRunner(deps=fake_deps())
    app.state.chat_service = None

    headers = _headers()
    res = client.post("/api/v1/chat/sessions", json={"mode": "interview"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["title"] == "新的模拟面试"
    sid = res.json()["id"]

    opening = client.post(
        f"/api/v1/chat/sessions/{sid}/stream", json={"text": "开始面试"}, headers=headers
    )
    assert opening.status_code == 200
    assert '"answering"' in opening.text and "自我介绍" in opening.text
    assert '"done"' in opening.text

    answer = client.post(
        f"/api/v1/chat/sessions/{sid}/stream",
        json={"text": "我用 React 做了个项目"},
        headers=headers,
    )
    assert answer.status_code == 200
    assert '"retrieving"' in answer.text and '"sources"' in answer.text
    assert '"answering"' in answer.text and '"probing"' in answer.text
    assert '"done"' in answer.text

    msgs = client.get(f"/api/v1/chat/sessions/{sid}/messages", headers=headers).json()
    assert any(m["role"] == "user" and m["content"] == "我用 React 做了个项目" for m in msgs)
    assert any(m["role"] == "assistant" and "点评" in m["content"] for m in msgs)

    end = client.post(f"/api/v1/chat/sessions/{sid}/end", headers=headers)
    assert end.status_code == 200
    assert '"finalizing"' in end.text and '"done"' in end.text

    async def check_report() -> None:
        async with TestSession() as s:
            report = (
                await s.scalars(select(InterviewReport).where(InterviewReport.session_id == sid))
            ).first()
            assert report is not None and report.overall == 4

    asyncio.run(check_report())

    end_again = client.post(f"/api/v1/chat/sessions/{sid}/end", headers=headers)
    assert "报告已生成" in end_again.text and '"finalizing"' not in end_again.text

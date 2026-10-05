"""真机验证：AsyncPostgresSaver 跨 runner 实例恢复 abilities / round_index。"""

import asyncio
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from app.orchestration.agents.interview.runner import InterviewRunner
from tests.conftest import TEST_DATABASE_URL
from tests.interview_fakes import fake_deps


def _pg_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(("postgresql", parts.netloc, parts.path, parts.query, parts.fragment))


def test_pg_checkpoint_persists_abilities_across_runners() -> None:
    async def run() -> None:
        thread_id = f"cp-{uuid4().hex[:8]}"
        db_url = _pg_url(TEST_DATABASE_URL)

        runner1 = InterviewRunner(deps=fake_deps(), db_url=db_url)
        opening = [
            e
            async for e in runner1.stream(
                user_id="u", session_id=thread_id, text="开始面试", history=[], personal_context=""
            )
        ]
        assert opening[-1]["type"] == "done"
        answer = [
            e
            async for e in runner1.stream(
                user_id="u",
                session_id=thread_id,
                text="我用 React 做了项目",
                history=[{"role": "assistant", "content": "请先做 60 秒自我介绍。"}],
                personal_context="",
            )
        ]
        assert answer[-1]["type"] == "done"
        await runner1.aclose()

        runner2 = InterviewRunner(deps=fake_deps(), db_url=db_url)
        deps = await runner2._ensure_deps()
        graph = await runner2._get_graph(deps)
        state = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        values = state.values or {}
        assert "technical" in values.get("abilities", {})
        assert values.get("round_index", 0) >= 1
        await runner2.aclose()

    asyncio.run(run())

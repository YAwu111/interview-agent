"""面试编排调用协议：orchestration 实现、access 注入、domains 经 app.state 调用。"""

from collections.abc import AsyncIterator
from typing import Protocol


class InterviewRunner(Protocol):
    async def stream(
        self,
        *,
        user_id: str,
        session_id: str,
        text: str,
        history: list[dict],
        personal_context: str,
    ) -> AsyncIterator[dict]: ...

    async def finalize(
        self,
        *,
        user_id: str,
        session_id: str,
        history: list[dict],
        personal_context: str,
    ) -> AsyncIterator[dict]: ...

"""用量采集协议：编排层只依赖本 Protocol（满足 import-linter），实现由上层注入。"""

from typing import Protocol


class TokenUsage(Protocol):
    node: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


class UsageSink(Protocol):
    async def record(self, user_id: str, usage: TokenUsage) -> None: ...

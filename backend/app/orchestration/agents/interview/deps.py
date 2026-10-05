"""节点依赖注入：llm / retriever / 模型档位 / usage sink / 预算参数。"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


class LLM(Protocol):
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        *,
        tools: list[dict] | None = None,
        json_mode: bool = False,
        temperature: float = 0.0,
        max_tokens: int = 1000,
    ) -> dict[str, Any]: ...

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> AsyncIterator[dict[str, Any]]: ...


class Retriever(Protocol):
    async def retrieve(self, query: str, top_k: int | None = None) -> list[dict]: ...


@dataclass
class InterviewDeps:
    llm: Any
    retriever: Any
    fast_model: str
    strong_model: str
    usage_sink: Any = None
    round_limit: int = 10
    llm_call_budget: int = 60
    probe_max_per_weakness: int = 2
    critic_timeout: float = 20.0
    critic_concurrency: int = 3
    # 预填充，避免每次读 settings；由 factory 注入
    retrieve_top_k: int = 6
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "uncertainty": 0.30,
            "relevance": 0.25,
            "severity": 0.20,
            "importance": 0.15,
            "probeability": 0.10,
        }
    )

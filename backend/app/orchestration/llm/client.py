"""DeepSeek（OpenAI 兼容）客户端：chat / stream / tools / json_object。纯 httpx，无框架依赖。"""

import json
import time
from collections.abc import AsyncIterator, Iterable, Iterator
from typing import Any

import httpx


class LLMError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status


def parse_usage(raw: dict[str, Any] | None) -> dict[str, int]:
    """把 OpenAI 风格 usage 收敛成 {prompt_tokens, completion_tokens, total_tokens}。"""
    if not raw:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": int(raw.get("prompt_tokens") or 0),
        "completion_tokens": int(raw.get("completion_tokens") or 0),
        "total_tokens": int(raw.get("total_tokens") or 0),
    }


def sse_delta_and_usage(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """纯函数：解析 SSE 的 `data:` 行，产出 {'type':'delta'|'usage', ...}。供单测。"""
    for line in lines:
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        if chunk.get("usage"):
            yield {"type": "usage", "usage": parse_usage(chunk["usage"])}
        delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
        if delta.get("content"):
            yield {"type": "delta", "content": delta["content"]}


class DeepSeekClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        *,
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
        temperature: float = 0.0,
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        t0 = time.monotonic()
        res = await self._client.post("/chat/completions", json=payload)
        if res.status_code >= 400:
            raise LLMError(res.status_code, res.text[:500])
        data = res.json()
        msg = data["choices"][0]["message"]
        return {
            "content": msg.get("content"),
            "tool_calls": msg.get("tool_calls"),
            "usage": parse_usage(data.get("usage")),
            "latency_ms": int((time.monotonic() - t0) * 1000),
        }

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        async with self._client.stream("POST", "/chat/completions", json=payload) as res:
            if res.status_code >= 400:
                body = (await res.aread()).decode(errors="replace")[:500]
                raise LLMError(res.status_code, body)
            async for line in res.aiter_lines():
                for event in sse_delta_and_usage([line]):
                    yield event

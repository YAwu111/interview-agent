"""DeepSeek（OpenAI 兼容）客户端与模型档位。放 core：domains 与 orchestration 都能用。"""

import asyncio
import json
import random
import time
from collections.abc import AsyncIterator, Iterable, Iterator
from typing import Any

import httpx

from app.core.config import settings

_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3


def _retry_delay(attempt: int, retry_after_ms: int = 0) -> float:
    cap = min(8.0, 0.5 * (2**attempt))
    jitter = random.uniform(0, cap)
    return max(jitter, retry_after_ms / 1000)


def _retry_after_ms(headers: httpx.Headers) -> int:
    raw = headers.get("retry-after")
    if not raw:
        return 0
    seconds = float(raw) if raw.isdigit() else None
    if seconds is not None and seconds >= 0:
        return int(seconds * 1000)
    date = time.mktime(time.strptime(raw, "%a, %d %b %Y %H:%M:%S GMT"))
    return max(0, int((date - time.time()) * 1000))


class LLMError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status


def parse_usage(raw: dict[str, Any] | None) -> dict[str, int]:
    if not raw:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": int(raw.get("prompt_tokens") or 0),
        "completion_tokens": int(raw.get("completion_tokens") or 0),
        "total_tokens": int(raw.get("total_tokens") or 0),
    }


def sse_delta_and_usage(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
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
        last_error: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                t0 = time.monotonic()
                res = await self._client.post("/chat/completions", json=payload)
                if res.status_code >= 400:
                    if res.status_code in _RETRYABLE_STATUSES and attempt < _MAX_ATTEMPTS - 1:
                        await asyncio.sleep(_retry_delay(attempt, _retry_after_ms(res.headers)))
                        continue
                    raise LLMError(res.status_code, res.text[:500])
                data = res.json()
                msg = data["choices"][0]["message"]
                return {
                    "content": msg.get("content"),
                    "reasoning_content": msg.get("reasoning_content"),
                    "tool_calls": msg.get("tool_calls"),
                    "usage": parse_usage(data.get("usage")),
                    "latency_ms": int((time.monotonic() - t0) * 1000),
                }
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < _MAX_ATTEMPTS - 1:
                    await asyncio.sleep(_retry_delay(attempt))
                    continue
                raise
        raise LLMError(0, str(last_error) if last_error else "未知错误")

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
            "stream_options": {"include_usage": True},
        }
        yielded = False
        last_error: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                async with self._client.stream("POST", "/chat/completions", json=payload) as res:
                    if res.status_code >= 400:
                        body = (await res.aread()).decode(errors="replace")[:500]
                        if res.status_code in _RETRYABLE_STATUSES and attempt < _MAX_ATTEMPTS - 1:
                            await asyncio.sleep(_retry_delay(attempt, _retry_after_ms(res.headers)))
                            continue
                        raise LLMError(res.status_code, body)
                    async for line in res.aiter_lines():
                        for event in sse_delta_and_usage([line]):
                            yielded = True
                            yield event
                return
            except httpx.HTTPError as exc:
                last_error = exc
                if yielded or attempt >= _MAX_ATTEMPTS - 1:
                    raise
                await asyncio.sleep(_retry_delay(attempt))
        raise LLMError(0, str(last_error) if last_error else "未知错误")


def fast_model() -> str:
    return settings.llm_model_fast


def strong_model() -> str:
    return settings.llm_model_strong or settings.llm_model_fast

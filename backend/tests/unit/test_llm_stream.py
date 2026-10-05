"""LLM 客户端纯逻辑单测：usage 收敛、SSE 解析、非流式调用（httpx MockTransport）。"""

import asyncio
import json

import httpx

from app.core.llm import DeepSeekClient, parse_usage, sse_delta_and_usage


def test_parse_usage_defaults() -> None:
    assert parse_usage(None) == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


def test_sse_delta_and_usage_parses_chunks() -> None:
    lines = [
        'data: {"choices":[{"delta":{"content":"你"}}]}',
        'data: {"choices":[{"delta":{"content":"好"}}]}',
        'data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12}}',
        "data: [DONE]",
        "data: should_be_ignored_after_done",
    ]
    events = list(sse_delta_and_usage(lines))
    assert events == [
        {"type": "delta", "content": "你"},
        {"type": "delta", "content": "好"},
        {
            "type": "usage",
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        },
    ]


def test_chat_parses_content_and_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "deepseek-chat"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "你好"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
            },
        )

    client = DeepSeekClient(
        "https://api.deepseek.com/v1", "test-key", transport=httpx.MockTransport(handler)
    )
    result = asyncio.run(client.chat([{"role": "user", "content": "hi"}], "deepseek-chat"))
    assert result["content"] == "你好"
    assert result["usage"]["total_tokens"] == 6

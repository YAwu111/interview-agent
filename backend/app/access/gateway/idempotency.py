"""幂等中间件：读 Idempotency-Key，编排 IdempotencyRepository 完成判重/重放/落库。"""

import hashlib
import json
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import get_logger
from app.data.repositories.idempotency import IdempotencyRepository

logger = get_logger(__name__)

IDEMPOTENT_METHODS = {"POST", "PATCH", "DELETE"}
_SKIP_SUFFIXES = ("/stream", "/end", "/stop")


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode()
    return None


async def _read_body(receive: Receive) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _body_receive(body: bytes) -> Receive:
    sent = False

    async def receive() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    return receive


def _response_header(headers: list[tuple[bytes, bytes]], name: bytes) -> str | None:
    for key, value in headers:
        if key == name:
            return value.decode()
    return None


def _decode_body(body: bytes, content_type: str | None) -> Any:
    if not body:
        return None
    text = body.decode("utf-8", errors="replace")
    if content_type and "json" in content_type:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def _encode_body(body: Any, content_type: str | None) -> bytes:
    if body is None:
        return b""
    if content_type and "json" in content_type:
        return json.dumps(body, ensure_ascii=False).encode()
    return str(body).encode()


async def _send_json(send: Send, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


class IdempotencyMiddleware:
    def __init__(self, app: ASGIApp, *, state: Any) -> None:
        self.app = app
        self._state = state

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        key = _header(scope, b"idempotency-key")
        raw_path = scope.get("path", "")
        path = raw_path.decode() if isinstance(raw_path, bytes) else raw_path
        if (
            not key
            or method not in IDEMPOTENT_METHODS
            or path.endswith(_SKIP_SUFFIXES)
            or "/auth/" in path
        ):
            await self.app(scope, receive, send)
            return

        redis = getattr(self._state, "redis", None)
        sessionmaker = getattr(self._state, "sessionmaker", None)
        if redis is None or sessionmaker is None:
            await self.app(scope, receive, send)
            return

        body = await _read_body(receive)
        query = scope.get("query_string", b"").decode()
        full_path = path + (f"?{query}" if query else "")
        payload_hash = hashlib.sha256(f"{method} {full_path}\n".encode() + body).hexdigest()

        repo = IdempotencyRepository(redis, sessionmaker)
        existing = await repo.find(key)
        if existing is not None:
            if existing["status"] == "inflight":
                await _send_json(send, 409, {"detail": "请求进行中"})
                return
            if existing["payload_hash"] != payload_hash:
                await _send_json(send, 409, {"detail": "幂等键冲突"})
                return
            await _replay(send, existing)
            return

        if not await repo.try_inflight(key, payload_hash):
            await _send_json(send, 409, {"detail": "请求进行中"})
            return

        captured: dict[str, Any] = {"status": 200, "headers": [], "body": b""}

        async def send_capture(message: Message) -> None:
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]
                captured["headers"] = message.get("headers", [])
            elif message["type"] == "http.response.body":
                captured["body"] += message.get("body", b"")
            await send(message)

        try:
            await self.app(scope, _body_receive(body), send_capture)
        except Exception:
            logger.exception("idempotent_request_failed key=%s", key)
            await repo.fail(key)
            raise

        status = captured["status"]
        if status < 500:
            content_type = _response_header(captured["headers"], b"content-type")
            await repo.complete(
                key=key,
                method=method,
                path=full_path,
                payload_hash=payload_hash,
                status_code=status,
                content_type=content_type,
                response_body=_decode_body(captured["body"], content_type),
            )
        else:
            await repo.fail(key)


async def _replay(send: Send, existing: dict) -> None:
    content_type = existing.get("content_type") or "application/json"
    await send(
        {
            "type": "http.response.start",
            "status": existing.get("status_code", 200),
            "headers": [(b"content-type", content_type.encode())],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": _encode_body(existing.get("response_body"), content_type),
        }
    )

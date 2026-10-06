"""chat 域 service：会话/消息 CRUD + 流式问答（检索 → LLM 作答）。"""

import asyncio
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import select

from app.core.config import settings
from app.core.llm import DeepSeekClient, fast_model
from app.core.logging import get_logger
from app.data.cache import sse
from app.data.db.models.chat import Message, Session
from app.data.db.models.report import InterviewReport
from app.data.rag.embeddings import HFEmbedder
from app.data.rag.retriever import HybridRetriever
from app.data.rag.vector_store import PgVectorStore

from . import repository
from .schemas import MessageOut, SessionOut

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "你是求职面试助手。优先依据给定资料回答，并在引用处标注 [来源:标题]。"
    "资料不足时明确回答“不确定”并说明缺什么，不得编造。"
)


def _ms(dt) -> int:
    return int(dt.timestamp() * 1000)


def _to_session(s: Session) -> SessionOut:
    return SessionOut(
        id=s.id,
        title=s.title,
        mode=s.mode,
        createdAt=_ms(s.created_at),
        updatedAt=_ms(s.updated_at),
    )


def _to_message(m: Message) -> MessageOut:
    return MessageOut(
        id=m.id,
        sessionId=m.session_id,
        role=m.role,
        content=m.content,
        sources=m.sources,
        status=m.status,
        createdAt=_ms(m.created_at),
    )


class ChatService:
    def __init__(self, sessionmaker, runner=None, redis=None, usage_sink=None) -> None:
        self._sessionmaker = sessionmaker
        self._runner = runner
        self._redis = redis
        self._usage_sink = usage_sink
        self._retriever = None
        self._llm = None
        self._tasks: set[asyncio.Task] = set()
        self._stream_tasks: dict[str, tuple[str, asyncio.Task]] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}

    def _start_task(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def _start_stream_task(self, session_id: str, message_id: str, coro) -> asyncio.Task:
        task = self._start_task(coro)
        self._stream_tasks[message_id] = (session_id, task)
        task.add_done_callback(lambda _t: self._stream_tasks.pop(message_id, None))
        return task

    async def stop_stream(self, session_id: str) -> None:
        for message_id, (sid, task) in list(self._stream_tasks.items()):
            if sid == session_id:
                task.cancel()

    def _lock_for(self, session_id: str) -> asyncio.Lock:
        lock = self._session_locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self._session_locks[session_id] = lock
        return lock

    async def aclose(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._llm is not None:
            await self._llm.aclose()

    def _client(self) -> DeepSeekClient:
        if self._llm is None:
            self._llm = DeepSeekClient(settings.deepseek_base_url, settings.deepseek_api_key)
        return self._llm

    async def _get_retriever(self) -> HybridRetriever:
        if self._retriever is None:
            store = PgVectorStore(self._sessionmaker)
            embedder = HFEmbedder(settings.embedding_model)
            # ponytail: v1 暂不加载 reranker（省一次 1GB+ 下载）；接 GPU 后再启用
            self._retriever = HybridRetriever(
                embedder, store.search, store.search_sparse, None, settings.retrieve_top_k
            )
        return self._retriever

    def has_runner(self) -> bool:
        return self._runner is not None

    async def list_sessions(self, user_id: str) -> list[SessionOut]:
        async with self._sessionmaker() as s:
            rows = await repository.list_sessions(s, user_id)
            return [_to_session(r) for r in rows]

    async def get_session(self, user_id: str, session_id: str) -> Session | None:
        async with self._sessionmaker() as s:
            return await repository.get_session(s, session_id, user_id)

    async def create_session(self, user_id: str, mode: str) -> SessionOut:
        async with self._sessionmaker() as s:
            title = "新的模拟面试" if mode == "interview" else "新会话"
            row = await repository.create_session(s, user_id, mode, title)
            await s.commit()
            return _to_session(row)

    async def update_session(self, user_id: str, session_id: str, mode: str) -> None:
        async with self._sessionmaker() as s:
            await repository.update_session(s, session_id, user_id, mode)
            await s.commit()

    async def delete_session(self, user_id: str, session_id: str) -> None:
        async with self._sessionmaker() as s:
            await repository.delete_session(s, session_id, user_id)
            await s.commit()

    async def get_messages(self, user_id: str, session_id: str) -> list[MessageOut]:
        async with self._sessionmaker() as s:
            rows = await repository.list_messages(s, session_id)
            return [_to_message(r) for r in rows]

    async def stream(self, sess: Session, text: str) -> AsyncIterator[dict]:
        lock = self._lock_for(sess.id)
        if lock.locked():
            yield {"type": "error", "message": "已有进行中的回答"}
            return
        async with lock:
            async with self._sessionmaker() as s:
                prior = await repository.list_messages(s, sess.id)
                history = [{"role": m.role, "content": m.content} for m in prior]
                first = len(prior) == 0
                await repository.create_message(s, sess.id, "user", text)
                await repository.touch_session(
                    s, sess.id, sess.user_id, title=text[:20] if first else None
                )
                await s.commit()

            if sess.mode == "interview" and self._runner is None:
                yield {"type": "error", "message": "面试服务未就绪"}
                return

            async with self._sessionmaker() as s:
                assistant = await repository.create_message(
                    s, sess.id, "assistant", "", status="streaming"
                )
                await s.commit()
            message_id = assistant.id

            producer = self._produce(sess, text, history)
            consumer = self._consume_stream(sess, message_id, producer)
            task = self._start_stream_task(sess.id, message_id, consumer)
            yield {"type": "meta", "messageId": message_id}
            async for ev in self._tail(sess.id, message_id, task):
                yield ev

    async def resume(
        self, sess: Session, message_id: str, last_event_id: int
    ) -> AsyncIterator[dict]:
        meta = await sse.get_meta(self._redis, sess.id, message_id)
        if meta is None:
            yield {"type": "error", "message": "流已过期或不存在"}
            return
        yield {"type": "meta", "messageId": message_id}
        async for ev in self._tail(sess.id, message_id, None, start_seq=last_event_id):
            yield ev

    async def _produce(
        self, sess: Session, text: str, history: list[dict]
    ) -> AsyncIterator[dict]:
        if sess.mode == "interview":
            async for ev in self._runner.stream(
                user_id=sess.user_id,
                session_id=sess.id,
                text=text,
                history=history,
                personal_context="",
            ):
                yield ev
            return

        yield {"type": "status", "stage": "retrieving"}
        retriever = await self._get_retriever()
        hits = await retriever.retrieve(text)
        sources = [
            {
                "id": h["id"],
                "title": h["title"],
                "snippet": h["snippet"],
                "baseName": h.get("base_name"),
            }
            for h in hits
        ]
        if sources:
            yield {"type": "sources", "items": sources}

        yield {"type": "status", "stage": "answering"}
        context = "\n\n".join(f"[来源:{h['title']}]\n{h['text'][:600]}" for h in hits)
        question = f"参考资料：\n{context}\n\n问题：{text}" if context else text
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        usage: dict = {}
        async for ev in self._client().stream(messages, fast_model()):
            if ev["type"] == "delta":
                yield {"type": "delta", "content": ev["content"]}
            elif ev["type"] == "usage":
                usage = ev.get("usage", {})
        if self._usage_sink and usage:
            await self._usage_sink.record(
                sess.user_id,
                {
                    "node": "answer",
                    "model": fast_model(),
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "latency_ms": 0,
                },
            )

    async def _consume_stream(
        self, sess: Session, message_id: str, producer: AsyncIterator[dict]
    ) -> None:
        parts: list[str] = []
        sources: list[dict] | None = None
        report: dict | None = None
        seq = 0
        await sse.set_meta(self._redis, sess.id, message_id, "running", 0)
        try:
            async for ev in producer:
                if ev.get("type") == "done":
                    continue
                seq += 1
                await sse.append_event(self._redis, sess.id, message_id, seq, ev)
                if ev.get("type") == "report":
                    report = ev.get("report")
                elif ev.get("type") == "sources":
                    sources = ev.get("items")
                elif ev.get("type") == "delta":
                    parts.append(ev.get("content"))

            async with self._sessionmaker() as s:
                await repository.update_message(
                    s, message_id, content="".join(parts), sources=sources, status="done"
                )
                await s.commit()
            if report is not None:
                await self._save_report(sess, report)
            await sse.set_meta(self._redis, sess.id, message_id, "done", seq)
        except asyncio.CancelledError:
            logger.info("stream cancelled session=%s", sess.id)
            async with self._sessionmaker() as s:
                await repository.update_message(
                    s, message_id, content="".join(parts), sources=sources, status="error"
                )
                await s.commit()
            await sse.set_meta(self._redis, sess.id, message_id, "failed", seq)
            raise
        except Exception:
            logger.exception("stream failed session=%s", sess.id)
            seq += 1
            await sse.append_event(
                self._redis,
                sess.id,
                message_id,
                seq,
                {"type": "error", "message": "生成失败，请重试"},
            )
            async with self._sessionmaker() as s:
                await repository.update_message(
                    s, message_id, content="".join(parts), sources=sources, status="error"
                )
                await s.commit()
            await sse.set_meta(self._redis, sess.id, message_id, "failed", seq)

    async def _tail(
        self,
        session_id: str,
        message_id: str,
        task: asyncio.Task | None,
        *,
        start_seq: int = 0,
    ) -> AsyncIterator[dict]:
        cursor = start_seq
        while True:
            events = await sse.read_tail(self._redis, session_id, message_id, cursor)
            for ev in events:
                payload = dict(ev["payload"])
                payload["eventId"] = ev["seq"]
                yield payload
                cursor = ev["seq"]
            meta = await sse.get_meta(self._redis, session_id, message_id)
            if meta is not None and meta["status"] in ("done", "failed"):
                if meta["status"] == "done":
                    yield {"type": "done"}
                return
            if task is not None and task.done():
                yield {"type": "error", "message": "生成失败，请重试"}
                return
            await asyncio.sleep(0.3)

    async def end_interview(self, sess: Session) -> AsyncIterator[dict]:
        if self._runner is None:
            yield {"type": "error", "message": "面试服务未就绪"}
            return
        async with self._sessionmaker() as s:
            prior = await repository.list_messages(s, sess.id)
            history = [{"role": m.role, "content": m.content} for m in prior]
            has_report = (
                await s.scalars(
                    select(InterviewReport).where(InterviewReport.session_id == sess.id)
                )
            ).first() is not None
        if has_report:
            yield {"type": "delta", "content": "报告已生成。"}
            yield {"type": "done"}
            return

        async with self._sessionmaker() as s:
            assistant = await repository.create_message(
                s, sess.id, "assistant", "", status="streaming"
            )
            await s.commit()
        message_id = assistant.id

        async def producer() -> AsyncIterator[dict]:
            async for ev in self._runner.finalize(
                user_id=sess.user_id, session_id=sess.id, history=history, personal_context=""
            ):
                yield ev

        consumer = self._consume_stream(sess, message_id, producer())
        task = self._start_stream_task(sess.id, message_id, consumer)
        yield {"type": "meta", "messageId": message_id}
        async for ev in self._tail(sess.id, message_id, task):
            yield ev

    async def _save_report(self, sess: Session, report: dict) -> None:
        payload = dict(
            user_id=sess.user_id,
            overall=float(report.get("overall") or 0),
            dimensions=report.get("dimensions") or [],
            strengths=report.get("strengths") or [],
            weaknesses=report.get("weaknesses") or [],
            next_steps=report.get("next_steps") or [],
            end_reason=str(report.get("end_reason") or "user_end"),
            model_used=settings.llm_model_strong or settings.llm_model_fast,
        )
        async with self._sessionmaker() as s:
            existing = (
                await s.scalars(
                    select(InterviewReport).where(InterviewReport.session_id == sess.id)
                )
            ).first()
            if existing is None:
                s.add(InterviewReport(session_id=sess.id, **payload))
            else:
                for k, v in payload.items():
                    setattr(existing, k, v)
            await s.commit()


def get_chat_service(request: Request) -> ChatService:
    """懒构建单例，挂在 app.state；不 import access/orchestration。"""
    svc = getattr(request.app.state, "chat_service", None)
    if svc is None:
        svc = ChatService(
            request.app.state.sessionmaker,
            runner=getattr(request.app.state, "interview_runner", None),
            redis=request.app.state.redis,
            usage_sink=getattr(request.app.state, "usage_sink", None),
        )
        request.app.state.chat_service = svc
    return svc

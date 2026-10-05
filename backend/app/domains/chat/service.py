"""chat 域 service：会话/消息 CRUD + 流式问答（检索 → LLM 作答）。"""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import select

from app.core.config import settings
from app.core.llm import DeepSeekClient, fast_model
from app.core.logging import get_logger
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
    def __init__(self, sessionmaker, runner=None) -> None:
        self._sessionmaker = sessionmaker
        self._runner = runner
        self._retriever = None
        self._llm = None

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
        async with self._sessionmaker() as s:
            prior = await repository.list_messages(s, sess.id)
            history = [{"role": m.role, "content": m.content} for m in prior]
            first = len(prior) == 0
            await repository.create_message(s, sess.id, "user", text)
            await repository.touch_session(
                s, sess.id, sess.user_id, title=text[:20] if first else None
            )
            await s.commit()

        if sess.mode == "interview":
            if self._runner is None:
                yield {"type": "error", "message": "面试服务未就绪"}
                return
            async for ev in self._stream_interview(sess, text, history):
                yield ev
            return

        try:
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
            parts: list[str] = []
            async for ev in self._client().stream(messages, fast_model()):
                if ev["type"] == "delta":
                    parts.append(ev["content"])
                    yield {"type": "delta", "content": ev["content"]}

            async with self._sessionmaker() as s:
                await repository.create_message(
                    s, sess.id, "assistant", "".join(parts), sources=sources or None, status="done"
                )
                await s.commit()
            yield {"type": "done"}
        except Exception:
            logger.exception("chat stream failed session=%s", sess.id)
            yield {"type": "error", "message": "生成失败，请重试"}

    async def _stream_interview(
        self, sess: Session, text: str, history: list[dict]
    ) -> AsyncIterator[dict]:
        parts: list[str] = []
        sources: list[dict] | None = None
        report: dict | None = None
        try:
            async for ev in self._runner.stream(
                user_id=sess.user_id,
                session_id=sess.id,
                text=text,
                history=history,
                personal_context="",
            ):
                if ev.get("type") == "report":
                    report = ev.get("report")
                    continue  # 报告事件只在服务端消费，不下发前端
                if ev.get("type") == "sources":
                    sources = ev.get("items")
                elif ev.get("type") == "delta":
                    parts.append(ev.get("content"))
                if ev.get("type") == "done":
                    continue  # 等落库成功后再发 done
                yield ev
            async with self._sessionmaker() as s:
                await repository.create_message(
                    s, sess.id, "assistant", "".join(parts), sources=sources, status="done"
                )
                await s.commit()
            if report is not None:
                await self._save_report(sess, report)
            yield {"type": "done"}
        except Exception:
            logger.exception("interview stream failed session=%s", sess.id)
            yield {"type": "error", "message": "生成失败，请重试"}

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
        parts: list[str] = []
        report: dict | None = None
        try:
            async for ev in self._runner.finalize(
                user_id=sess.user_id, session_id=sess.id, history=history, personal_context=""
            ):
                if ev.get("type") == "report":
                    report = ev.get("report")
                    continue
                if ev.get("type") == "delta":
                    parts.append(ev.get("content"))
                if ev.get("type") == "done":
                    continue
                yield ev
            async with self._sessionmaker() as s:
                await repository.create_message(
                    s, sess.id, "assistant", "".join(parts), sources=None, status="done"
                )
                await s.commit()
            if report is not None:
                await self._save_report(sess, report)
            yield {"type": "done"}
        except Exception:
            logger.exception("end interview failed session=%s", sess.id)
            yield {"type": "error", "message": "生成失败，请重试"}

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
        )
        request.app.state.chat_service = svc
    return svc

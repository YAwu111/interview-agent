"""chat 数据访问：会话与消息，全部按 user_id 归属过滤。"""

from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.db.models.chat import Message, Session
from app.data.db.models.report import InterviewReport


async def list_sessions(session: AsyncSession, user_id: str) -> list[Session]:
    rows = await session.scalars(
        select(Session).where(Session.user_id == user_id).order_by(Session.updated_at.desc())
    )
    return list(rows)


async def get_session(session: AsyncSession, session_id: str, user_id: str) -> Session | None:
    return (
        await session.scalars(
            select(Session).where(Session.id == session_id, Session.user_id == user_id)
        )
    ).first()


async def create_session(
    session: AsyncSession, user_id: str, mode: str, title: str = "新会话"
) -> Session:
    row = Session(user_id=user_id, title=title, mode=mode)
    session.add(row)
    await session.flush()
    return row


async def update_session(session: AsyncSession, session_id: str, user_id: str, mode: str) -> None:
    await session.execute(
        update(Session)
        .where(Session.id == session_id, Session.user_id == user_id)
        .values(mode=mode, updated_at=datetime.now(UTC))
    )


async def delete_session(session: AsyncSession, session_id: str, user_id: str) -> None:
    # 无 FK 级联：先清报告/消息，再删会话（同事务）
    # 按 user_id 过滤，防止越权删除他人数据（防御纵深：路由层 _owned_session 已校验）
    await session.execute(
        delete(InterviewReport).where(
            InterviewReport.session_id == session_id,
            InterviewReport.user_id == user_id,
        )
    )
    # Message 无 user_id 列，通过 sessions.user_id 子查询做归属校验
    await session.execute(
        delete(Message).where(
            Message.session_id == session_id,
            Message.session_id.in_(select(Session.id).where(Session.user_id == user_id)),
        )
    )
    await session.execute(
        delete(Session).where(Session.id == session_id, Session.user_id == user_id)
    )


async def list_messages(session: AsyncSession, session_id: str) -> list[Message]:
    rows = await session.scalars(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at.asc())
    )
    return list(rows)


async def count_messages(session: AsyncSession, session_id: str) -> int:
    return (
        await session.scalars(
            select(func.count()).select_from(Message).where(Message.session_id == session_id)
        )
    ).one()


async def create_message(
    session: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    sources: list[dict] | None = None,
    status: str = "done",
) -> Message:
    row = Message(session_id=session_id, role=role, content=content, sources=sources, status=status)
    session.add(row)
    await session.flush()
    return row


async def touch_session(
    session: AsyncSession, session_id: str, user_id: str, title: str | None = None
) -> None:
    values: dict = {"updated_at": datetime.now(UTC)}
    if title is not None:
        values["title"] = title
    await session.execute(
        update(Session).where(Session.id == session_id, Session.user_id == user_id).values(**values)
    )

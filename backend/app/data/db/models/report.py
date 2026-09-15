"""面试报告：finalize 节点落库，前端 v1 暂以 markdown 消息呈现。"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class InterviewReport(Base):
    __tablename__ = "interview_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id"), unique=True, index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    overall: Mapped[float] = mapped_column(Float)
    dimensions: Mapped[list] = mapped_column(JSONB)
    strengths: Mapped[list] = mapped_column(JSONB)
    weaknesses: Mapped[list] = mapped_column(JSONB)
    next_steps: Mapped[list] = mapped_column(JSONB)
    end_reason: Mapped[str] = mapped_column(String(32))
    model_used: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

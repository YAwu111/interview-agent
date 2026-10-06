"""ORM 模型注册处：domain 的 models 在此汇总导入，供 Alembic autogenerate 发现。"""

from .auth import OAuthAccount, RefreshToken, User
from .base import Base
from .chat import Message, Session
from .idempotency import IdempotencyRecord
from .knowledge import Chunk, Document, KnowledgeBase
from .report import InterviewReport
from .resources import Resource
from .usage import UsageDaily

__all__ = [
    "Base",
    "OAuthAccount",
    "RefreshToken",
    "User",
    "Message",
    "Session",
    "IdempotencyRecord",
    "Chunk",
    "Document",
    "KnowledgeBase",
    "InterviewReport",
    "Resource",
    "UsageDaily",
]

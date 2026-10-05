"""chat 域请求/响应模型。时间戳用 epoch 毫秒，与前端 ChatSession/ChatMessage 对齐。"""

from typing import Literal

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    mode: Literal["chat", "interview"] = "chat"


class SessionUpdate(BaseModel):
    mode: Literal["chat", "interview"] | None = None


class SessionOut(BaseModel):
    id: str
    title: str
    mode: str
    createdAt: int
    updatedAt: int


class MessageOut(BaseModel):
    id: str
    sessionId: str
    role: str
    content: str
    sources: list[dict] | None = None
    status: str
    createdAt: int


class StreamRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)

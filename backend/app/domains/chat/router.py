"""对话 领域路由（骨架占位）。鉴权由 gateway 聚合时统一注入，本层不感知。"""

from fastapi import APIRouter

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions")
async def list_placeholder() -> list[dict]:
    return []

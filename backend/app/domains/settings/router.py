"""设置 领域路由（骨架占位）。鉴权由 gateway 聚合时统一注入，本层不感知。"""

from fastapi import APIRouter

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/profile", status_code=501)
async def list_placeholder() -> dict[str, str]:
    return {"detail": "设置接口待实现"}

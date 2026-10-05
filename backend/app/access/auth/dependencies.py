import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AppError

from . import service

bearer = HTTPBearer(auto_error=False)

UNAUTHORIZED = AppError("未登录或登录已过期", status_code=401)


async def get_token_payload(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    """解析 Bearer JWT → claims；缺失/无效一律 401，语义对齐前端 authBridge。"""
    if creds is None:
        raise UNAUTHORIZED
    try:
        return service.decode_token(creds.credentials, "access")
    except jwt.PyJWTError:
        raise UNAUTHORIZED from None


async def get_current_user(request: Request, payload: dict = Depends(get_token_payload)) -> str:
    """当前用户 id（不查库；需要用户实体的端点自行按 id 加载）。"""
    user_id = payload["sub"]
    request.state.user_id = user_id  # 供 domains 经 request.state 读取，避免反向 import
    return user_id


def require_scope(scope: str):
    """scope 校验：已认证但 scope 不足 → 403。v1 仅 'api'。"""

    async def checker(payload: dict = Depends(get_token_payload)) -> dict:
        if scope not in str(payload.get("scope", "")).split():
            raise AppError("没有访问权限", status_code=403)
        return payload

    return checker

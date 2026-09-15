from fastapi import APIRouter, Depends, Form
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.data.db.models.auth import User
from app.data.db.session import get_session

from . import repository, service
from .code_store import CodeStore, get_code_store
from .dependencies import get_current_user
from .schemas import AuthResponse, LoginRequest, LogoutRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

BAD_CREDENTIALS = AppError("邮箱或密码错误", status_code=401)
EMAIL_TAKEN = AppError("邮箱已注册", status_code=409)


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, name=user.name, email=user.email, avatar=user.avatar)


async def _auth_response(session: AsyncSession, user: User) -> AuthResponse:
    refresh, _ = await service.issue_refresh(session, user.id)
    await session.commit()
    return AuthResponse(
        access_token=service.create_access_token(user.id),
        refresh_token=refresh,
        expires_in=service.access_expires_in(),
        user=_user_out(user),
    )


@router.post("/register")
async def register(
    body: RegisterRequest, session: AsyncSession = Depends(get_session)
) -> AuthResponse:
    if await repository.get_user_by_email(session, body.email):
        raise EMAIL_TAKEN
    try:
        user = await repository.create_user(
            session,
            email=body.email,
            name=body.name,
            password_hash=service.hash_password(body.password),
        )
    except IntegrityError:
        # 并发注册同一邮箱：预检查后仍撞上唯一约束 → 409 而非 500
        await session.rollback()
        raise EMAIL_TAKEN from None
    return await _auth_response(session, user)


@router.post("/login")
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> AuthResponse:
    user = await repository.get_user_by_email(session, body.email)
    # 统一 401，不区分账号不存在/密码错误（防枚举）
    password_hash = user.password_hash if user is not None else None
    if password_hash is None:
        # 计时均摊：也跑一次 Argon2，避免“用户不存在”返回明显更快
        service.verify_password(body.password, service.DUMMY_PASSWORD_HASH)
        raise BAD_CREDENTIALS
    if not service.verify_password(body.password, password_hash):
        raise BAD_CREDENTIALS
    return await _auth_response(session, user)


@router.post("/token")
async def token(
    grant_type: str = Form(...),
    code: str | None = Form(None),
    refresh_token: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    code_store: CodeStore = Depends(get_code_store),
) -> AuthResponse:
    """OAuth2 token 端点：authorization_code（回调换发）与 refresh_token（轮换）。"""
    if grant_type == "authorization_code":
        if not code:
            raise AppError("缺少 code", status_code=400)
        user_id = await code_store.consume(code)
        if user_id is None:
            raise service.INVALID_GRANT
        user = await repository.get_user_by_id(session, user_id)
        if user is None:
            raise service.INVALID_GRANT
        return await _auth_response(session, user)
    if grant_type == "refresh_token":
        if not refresh_token:
            raise AppError("缺少 refresh_token", status_code=400)
        user, new_refresh = await service.rotate_refresh(session, refresh_token)
        return AuthResponse(
            access_token=service.create_access_token(user.id),
            refresh_token=new_refresh,
            expires_in=service.access_expires_in(),
            user=_user_out(user),
        )
    raise AppError("不支持的 grant_type", status_code=400)


@router.post("/logout")
async def logout(
    body: LogoutRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    await service.revoke_refresh(session, body.refresh_token)
    return {"detail": "已退出"}


@router.get("/me")
async def me(
    user_id: str = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> UserOut:
    user = await repository.get_user_by_id(session, user_id)
    if user is None:
        raise service.UNAUTHORIZED
    return _user_out(user)

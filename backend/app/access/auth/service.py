"""鉴权业务：密码哈希、JWT（access）、opaque refresh（轮换/重用检测/撤销）。"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.data.db.models.auth import RefreshToken, User

from . import repository

_password_hash = PasswordHash.recommended()

UNAUTHORIZED = AppError("未登录或登录已过期", status_code=401)
INVALID_GRANT = AppError("授权已失效，请重新登录", status_code=401)


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def _encode(subject: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "scope": "api",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str) -> str:
    return _encode(user_id, "access", timedelta(minutes=settings.jwt_expire_access_minutes))


def decode_token(token: str, expected_type: str = "access") -> dict:
    """返回 claims；无效/过期/类型不符抛 jwt.PyJWTError 系异常。"""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise jwt.InvalidTokenError("invalid token")
    return payload


def access_expires_in() -> int:
    return settings.jwt_expire_access_minutes * 60


def _hash_refresh(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def issue_refresh(
    session: AsyncSession, user_id: str, family_id: str | None = None
) -> tuple[str, RefreshToken]:
    """签发 opaque refresh token，落库 sha256 哈希；返回明文（仅此一次可见）与行对象。"""
    raw = secrets.token_urlsafe(48)
    row = RefreshToken(
        user_id=user_id,
        family_id=family_id or uuid.uuid4().hex,
        token_hash=_hash_refresh(raw),
        expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_expire_refresh_days),
    )
    await repository.save_refresh_token(session, row)
    return raw, row


async def rotate_refresh(session: AsyncSession, raw: str) -> tuple[User, str]:
    """轮换：原子抢占旧值（并发下唯一成功）；旧值重用（已撤销仍使用）→ 撤销整个 family。"""
    row = await repository.get_refresh_by_hash(session, _hash_refresh(raw))
    if row is None:
        raise INVALID_GRANT
    if row.revoked_at is not None:
        # 重用检测：已被轮换/撤销的 token 再次被用 → 整族作废
        await repository.revoke_family(session, row.family_id)
        await session.commit()
        raise INVALID_GRANT
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        raise INVALID_GRANT
    user = await repository.get_user_by_id(session, row.user_id)
    if user is None:
        raise INVALID_GRANT
    if not await repository.claim_token(session, row.id):
        # 并发下旧值刚被另一请求轮换/撤销 → 视同重用，整族作废
        await repository.revoke_family(session, row.family_id)
        await session.commit()
        raise INVALID_GRANT
    new_raw, new_row = await issue_refresh(session, row.user_id, family_id=row.family_id)
    row.replaced_by_id = new_row.id
    await session.commit()
    return user, new_raw


async def revoke_refresh(session: AsyncSession, raw: str) -> None:
    """登出撤销：幂等，不存在/已撤销都视为成功。"""
    row = await repository.get_refresh_by_hash(session, _hash_refresh(raw))
    if row is not None and row.revoked_at is None:
        await repository.revoke_token(session, row)
        await session.commit()

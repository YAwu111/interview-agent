"""鉴权数据访问：users / oauth_accounts / refresh_tokens。函数接收 session，由 router 注入。"""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.db.models.auth import OAuthAccount, RefreshToken, User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return (await session.scalars(select(User).where(User.email == email.strip().lower()))).first()


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    return await session.get(User, user_id)


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    name: str,
    password_hash: str | None,
    avatar: str | None = None,
) -> User:
    user = User(email=email.strip().lower(), name=name, password_hash=password_hash, avatar=avatar)
    session.add(user)
    await session.flush()
    return user


async def get_oauth_account(
    session: AsyncSession, provider: str, provider_user_id: str
) -> OAuthAccount | None:
    return (
        await session.scalars(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )
    ).first()


async def link_oauth_account(
    session: AsyncSession, *, user_id: str, provider: str, provider_user_id: str
) -> OAuthAccount:
    account = OAuthAccount(user_id=user_id, provider=provider, provider_user_id=provider_user_id)
    session.add(account)
    await session.flush()
    return account


async def save_refresh_token(session: AsyncSession, token: RefreshToken) -> None:
    session.add(token)
    await session.flush()


async def get_refresh_by_hash(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    return (
        await session.scalars(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).first()


async def claim_token(session: AsyncSession, token_id: str) -> bool:
    """原子抢占：仅当 revoked_at 仍为 NULL 时置撤销；并发轮换下只有一个调用返回 True。"""
    res = await session.execute(
        update(RefreshToken)
        .where(RefreshToken.id == token_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    return res.rowcount == 1


async def revoke_token(
    session: AsyncSession, token: RefreshToken, replaced_by_id: str | None = None
) -> None:
    token.revoked_at = datetime.now(UTC)
    if replaced_by_id is not None:
        token.replaced_by_id = replaced_by_id
    await session.flush()


async def revoke_family(session: AsyncSession, family_id: str) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )

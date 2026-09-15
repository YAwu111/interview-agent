"""service 层单测：密码哈希、JWT scope、refresh 轮换/重用检测。"""

import asyncio

import jwt as pyjwt
import pytest

from app.access.auth import repository, service
from app.core.config import settings
from app.core.exceptions import AppError
from tests.conftest import TestSession


def test_password_hash_roundtrip() -> None:
    hashed = service.hash_password("secret-123")
    assert service.verify_password("secret-123", hashed)
    assert not service.verify_password("wrong", hashed)


def test_access_token_scope_and_type() -> None:
    token = service.create_access_token("u1")
    payload = service.decode_token(token, "access")
    assert payload["sub"] == "u1"
    assert payload["type"] == "access"
    assert payload["scope"] == "api"
    with pytest.raises(pyjwt.PyJWTError):
        service.decode_token(token, "refresh")
    with pytest.raises(pyjwt.PyJWTError):
        service.decode_token(token + "x", "access")


def test_require_scope() -> None:
    from app.access.auth.dependencies import require_scope

    checker = require_scope("api")
    assert asyncio.run(checker({"scope": "api"})) == {"scope": "api"}
    with pytest.raises(AppError) as exc:
        asyncio.run(checker({"scope": ""}))
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_refresh_rotation_and_reuse_detection() -> None:
    async with TestSession() as s:
        user = await repository.create_user(
            s, email="rot@example.com", name="rot", password_hash=None
        )
        raw1, _ = await service.issue_refresh(s, user.id)
        await s.commit()

        # 正常轮换：旧值作废，新值可用
        user2, raw2 = await service.rotate_refresh(s, raw1)
        assert user2.id == user.id
        assert raw2 != raw1

        # 旧值重用 → 401 且整族撤销
        with pytest.raises(AppError) as exc:
            await service.rotate_refresh(s, raw1)
        assert exc.value.status_code == 401
        with pytest.raises(AppError):
            await service.rotate_refresh(s, raw2)


@pytest.mark.anyio
async def test_concurrent_rotation_only_one_wins() -> None:
    """P1：两个并发请求携带同一 refresh token，原子抢占保证只有一个成功，败者视同重用 401。"""
    async with TestSession() as s:
        user = await repository.create_user(
            s, email="race@example.com", name="race", password_hash=None
        )
        raw, _ = await service.issue_refresh(s, user.id)
        await s.commit()

    async def attempt() -> str:
        async with TestSession() as s:
            _, new_raw = await service.rotate_refresh(s, raw)
            return new_raw

    results = await asyncio.gather(attempt(), attempt(), return_exceptions=True)
    wins = [r for r in results if isinstance(r, str)]
    losses = [r for r in results if isinstance(r, AppError)]
    assert len(wins) == 1
    assert len(losses) == 1 and losses[0].status_code == 401


@pytest.mark.anyio
async def test_expired_refresh_is_401(monkeypatch: pytest.MonkeyPatch) -> None:
    async with TestSession() as s:
        user = await repository.create_user(
            s, email="exp@example.com", name="exp", password_hash=None
        )
        monkeypatch.setattr(settings, "jwt_expire_refresh_days", -1)
        raw, _ = await service.issue_refresh(s, user.id)
        await s.commit()
        with pytest.raises(AppError) as exc:
            await service.rotate_refresh(s, raw)
        assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_revoke_is_idempotent() -> None:
    async with TestSession() as s:
        user = await repository.create_user(
            s, email="rev@example.com", name="rev", password_hash=None
        )
        raw, _ = await service.issue_refresh(s, user.id)
        await s.commit()
        await service.revoke_refresh(s, raw)
        await service.revoke_refresh(s, raw)  # 第二次不报错
        await service.revoke_refresh(s, "never-issued")  # 不存在的也不报错

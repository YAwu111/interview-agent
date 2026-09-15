"""第三方 OAuth：标准 Authorization Code + PKCE，state 走短期签名 cookie（itsdangerous）。"""

import base64
import hashlib
import secrets
from dataclasses import dataclass

from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.data.db.session import get_session

from . import repository
from .code_store import CodeStore, get_code_store

router = APIRouter(prefix="/auth/oauth", tags=["auth"])

STATE_COOKIE = "oauth_state"
STATE_MAX_AGE = 600

_serializer = URLSafeTimedSerializer(settings.jwt_secret, salt="oauth-state")


@dataclass(frozen=True)
class ProviderConfig:
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    scope: str


@dataclass(frozen=True)
class ProviderUser:
    provider_user_id: str
    email: str
    name: str
    avatar: str | None


def _providers() -> dict[str, ProviderConfig]:
    return {
        "github": ProviderConfig(
            client_id=settings.oauth_github_client_id,
            client_secret=settings.oauth_github_client_secret,
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            scope="read:user user:email",
        ),
        "google": ProviderConfig(
            client_id=settings.oauth_google_client_id,
            client_secret=settings.oauth_google_client_secret,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scope="openid email profile",
        ),
    }


def _redirect_uri(provider: str) -> str:
    return f"{settings.backend_base_url}/api/v1/auth/oauth/{provider}/callback"


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


async def exchange_provider_user(
    provider: str, code: str, code_verifier: str, redirect_uri: str
) -> ProviderUser:
    """用授权码换 provider token 并取用户信息。测试经 monkeypatch 替换本函数。"""
    cfg = _providers()[provider]
    client = AsyncOAuth2Client(
        cfg.client_id,
        cfg.client_secret,
        code_verifier=code_verifier,
        headers={"Accept": "application/json"},
    )
    token = await client.fetch_token(
        cfg.token_url, grant_type="authorization_code", code=code, redirect_uri=redirect_uri
    )
    client.token = token
    if provider == "github":
        data = (await client.get("https://api.github.com/user")).json()
        email = data.get("email")
        if not email:
            emails = (await client.get("https://api.github.com/user/emails")).json()
            primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
            email = primary["email"] if primary else None
        if not email:
            raise AppError("GitHub 账号无可用邮箱", status_code=400)
        name = data.get("name") or data["login"]
        return ProviderUser(str(data["id"]), email, name, data.get("avatar_url"))
    data = (await client.get("https://openidconnect.googleapis.com/v1/userinfo")).json()
    return ProviderUser(str(data["sub"]), data["email"], data.get("name", ""), data.get("picture"))


@router.get("/{provider}")
async def authorize(provider: str) -> RedirectResponse:
    cfg = _providers().get(provider)
    if cfg is None:
        raise AppError("不支持的登录方式", status_code=404)
    if not cfg.client_id:
        raise AppError(f"{provider} OAuth 未配置", status_code=501)

    state = secrets.token_urlsafe(16)
    verifier = secrets.token_urlsafe(64)
    params = (
        f"response_type=code&client_id={cfg.client_id}"
        f"&redirect_uri={_redirect_uri(provider)}&scope={cfg.scope.replace(' ', '%20')}"
        f"&state={state}&code_challenge={_pkce_challenge(verifier)}"
        f"&code_challenge_method=S256"
    )
    res = RedirectResponse(f"{cfg.authorize_url}?{params}", status_code=302)
    res.set_cookie(
        STATE_COOKIE,
        _serializer.dumps({"state": state, "verifier": verifier, "provider": provider}),
        max_age=STATE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return res


def _frontend_error() -> RedirectResponse:
    """OAuth 失败统一回前端错误页，并清掉 state cookie。"""
    res = RedirectResponse(f"{settings.frontend_url}/oauth/callback?error=1", status_code=302)
    res.delete_cookie(STATE_COOKIE)
    return res


@router.get("/{provider}/callback")
async def callback(
    request: Request,
    provider: str,
    code: str,
    state: str,
    session: AsyncSession = Depends(get_session),
    code_store: CodeStore = Depends(get_code_store),
) -> RedirectResponse:
    cfg = _providers().get(provider)
    if cfg is None or not cfg.client_id:
        return _frontend_error()

    signed = request.cookies.get(STATE_COOKIE, "")
    try:
        payload = _serializer.loads(signed, max_age=STATE_MAX_AGE)
    except BadSignature:
        return _frontend_error()
    if payload.get("state") != state or payload.get("provider") != provider:
        return _frontend_error()

    try:
        puser = await exchange_provider_user(
            provider, code, payload["verifier"], _redirect_uri(provider)
        )
    except Exception:
        # provider 网络/协议异常与业务错误统一走前端错误页，不外泄细节
        return _frontend_error()

    account = await repository.get_oauth_account(session, provider, puser.provider_user_id)
    if account is not None:
        user = await repository.get_user_by_id(session, account.user_id)
        if user is None:
            return _frontend_error()
    else:
        user = await repository.get_user_by_email(session, puser.email)
        if user is None:
            user = await repository.create_user(
                session, email=puser.email, name=puser.name or puser.email.split("@")[0],
                password_hash=None, avatar=puser.avatar,
            )
        await repository.link_oauth_account(
            session, user_id=user.id, provider=provider, provider_user_id=puser.provider_user_id
        )
        await session.commit()

    code_one_time = await code_store.issue(user.id)
    res = RedirectResponse(
        f"{settings.frontend_url}/oauth/callback?code={code_one_time}", status_code=302
    )
    res.delete_cookie(STATE_COOKIE)
    return res

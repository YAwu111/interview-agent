"""OAuth 流程：state 签名 cookie + PKCE，provider 交换经 monkeypatch 模拟。"""

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.access.auth import oauth
from app.access.auth.oauth import ProviderUser
from app.core.config import settings
from app.core.exceptions import AppError

FAKE_USER = ProviderUser(
    provider_user_id="gh-42", email="octo@example.com", name="Octo", avatar=None
)


def test_oauth_unconfigured_501(client: TestClient) -> None:
    res = client.get("/api/v1/auth/oauth/github", follow_redirects=False)
    assert res.status_code == 501


def test_oauth_unknown_provider_404(client: TestClient) -> None:
    res = client.get("/api/v1/auth/oauth/wechat", follow_redirects=False)
    assert res.status_code == 404


@pytest.fixture
def github_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oauth_github_client_id", "gid")
    monkeypatch.setattr(settings, "oauth_github_client_secret", "gsecret")

    async def fake_exchange(
        provider: str, code: str, verifier: str, redirect_uri: str
    ) -> ProviderUser:
        assert provider == "github" and code == "fake-code" and verifier
        return FAKE_USER

    monkeypatch.setattr(oauth, "exchange_provider_user", fake_exchange)


def test_github_flow_end_to_end(client: TestClient, github_configured: None) -> None:
    start = client.get("/api/v1/auth/oauth/github", follow_redirects=False)
    assert start.status_code == 302
    location = start.headers["location"]
    assert location.startswith("https://github.com/login/oauth/authorize")
    state = parse_qs(urlparse(location).query)["state"][0]
    assert "code_challenge=" in location

    cb = client.get(
        f"/api/v1/auth/oauth/github/callback?code=fake-code&state={state}",
        follow_redirects=False,
    )
    assert cb.status_code == 302
    front = urlparse(cb.headers["location"])
    assert front.path == "/oauth/callback"
    one_time_code = parse_qs(front.query)["code"][0]

    res = client.post(
        "/api/v1/auth/token", data={"grant_type": "authorization_code", "code": one_time_code}
    )
    assert res.status_code == 200
    assert res.json()["user"]["email"] == FAKE_USER.email

    # 第二次登录同一 provider 账号 → 关联到同一用户
    cb2 = client.get("/api/v1/auth/oauth/github", follow_redirects=False)
    state2 = parse_qs(urlparse(cb2.headers["location"]).query)["state"][0]
    cb2res = client.get(
        f"/api/v1/auth/oauth/github/callback?code=fake-code&state={state2}",
        follow_redirects=False,
    )
    code2 = parse_qs(urlparse(cb2res.headers["location"]).query)["code"][0]
    res2 = client.post(
        "/api/v1/auth/token", data={"grant_type": "authorization_code", "code": code2}
    )
    assert res2.json()["user"]["id"] == res.json()["user"]["id"]


def test_callback_bad_state_redirects_error(client: TestClient, github_configured: None) -> None:
    client.get("/api/v1/auth/oauth/github", follow_redirects=False)
    cb = client.get(
        "/api/v1/auth/oauth/github/callback?code=fake-code&state=tampered",
        follow_redirects=False,
    )
    assert cb.status_code == 302
    assert "error=1" in cb.headers["location"]


def test_callback_provider_exception_redirects_error(
    client: TestClient, github_configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P3：provider 交换抛异常（网络/无邮箱）统一 302 前端错误页，且清 state cookie。"""

    async def boom(provider: str, code: str, verifier: str, redirect_uri: str) -> ProviderUser:
        raise AppError("GitHub 账号无可用邮箱", status_code=400)

    monkeypatch.setattr(oauth, "exchange_provider_user", boom)
    start = client.get("/api/v1/auth/oauth/github", follow_redirects=False)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    cb = client.get(
        f"/api/v1/auth/oauth/github/callback?code=fake-code&state={state}",
        follow_redirects=False,
    )
    assert cb.status_code == 302
    assert "error=1" in cb.headers["location"]
    assert "oauth_state" in cb.headers.get("set-cookie", "")

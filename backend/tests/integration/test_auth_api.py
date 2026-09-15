"""鉴权 API 集成测试：注册/登录/刷新/登出/me/code 单次使用。"""

import pytest
from fastapi.testclient import TestClient

from app.access.auth.code_store import RedisCodeStore
from tests.conftest import make_redis

REGISTER = {"name": "小明", "email": "ming@example.com", "password": "secret-123"}


def _register(client: TestClient) -> dict:
    res = client.post("/api/v1/auth/register", json=REGISTER)
    assert res.status_code == 200
    return res.json()


def test_register_login_me(client: TestClient) -> None:
    body = _register(client)
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["user"]["email"] == REGISTER["email"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["name"] == "小明"

    login = client.post(
        "/api/v1/auth/login", json={"email": REGISTER["email"], "password": REGISTER["password"]}
    )
    assert login.status_code == 200


def test_register_duplicate_409(client: TestClient) -> None:
    _register(client)
    res = client.post("/api/v1/auth/register", json=REGISTER)
    assert res.status_code == 409
    assert res.json()["detail"] == "邮箱已注册"


def test_register_race_integrity_error_is_409(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P2：绕过预检查（模拟并发竞态），唯一约束冲突须映射 409 而非 500。"""
    from app.access.auth import repository

    async def no_precheck(session, email):  # noqa: ANN001, ANN202
        return None

    monkeypatch.setattr(repository, "get_user_by_email", no_precheck)
    # router 持有的是模块引用，补丁生效于调用点
    assert client.post("/api/v1/auth/register", json=REGISTER).status_code == 200
    res = client.post("/api/v1/auth/register", json=REGISTER)
    assert res.status_code == 409


def test_email_case_insensitive(client: TestClient) -> None:
    res = client.post(
        "/api/v1/auth/register",
        json={"name": "大写", "email": "Mixed@Example.com", "password": "secret-123"},
    )
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "mixed@example.com"
    login = client.post(
        "/api/v1/auth/login", json={"email": "MIXED@example.com", "password": "secret-123"}
    )
    assert login.status_code == 200
    dup = client.post(
        "/api/v1/auth/register",
        json={"name": "x", "email": "mixed@example.com", "password": "secret-123"},
    )
    assert dup.status_code == 409


def test_login_uniform_401(client: TestClient) -> None:
    _register(client)
    wrong_pwd = client.post(
        "/api/v1/auth/login", json={"email": REGISTER["email"], "password": "wrong"}
    )
    no_user = client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "x"}
    )
    assert wrong_pwd.status_code == no_user.status_code == 401
    assert wrong_pwd.json() == no_user.json()


def test_refresh_rotation_and_reuse(client: TestClient) -> None:
    body = _register(client)
    res = client.post(
        "/api/v1/auth/token",
        data={"grant_type": "refresh_token", "refresh_token": body["refresh_token"]},
    )
    assert res.status_code == 200
    rotated = res.json()
    assert rotated["refresh_token"] != body["refresh_token"]

    # 旧 refresh 重用 → 401，且整族撤销（新 refresh 也失效）
    reuse = client.post(
        "/api/v1/auth/token",
        data={"grant_type": "refresh_token", "refresh_token": body["refresh_token"]},
    )
    assert reuse.status_code == 401
    after_reuse = client.post(
        "/api/v1/auth/token",
        data={"grant_type": "refresh_token", "refresh_token": rotated["refresh_token"]},
    )
    assert after_reuse.status_code == 401


def test_logout_idempotent(client: TestClient) -> None:
    body = _register(client)
    out = client.post("/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]})
    assert out.status_code == 200
    again = client.post("/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]})
    assert again.status_code == 200
    use_after = client.post(
        "/api/v1/auth/token",
        data={"grant_type": "refresh_token", "refresh_token": body["refresh_token"]},
    )
    assert use_after.status_code == 401


async def _issue_code(user_id: str) -> str:
    r = make_redis()
    code = await RedisCodeStore(r).issue(user_id)
    await r.aclose()
    return code


def test_authorization_code_single_use(client: TestClient) -> None:
    import asyncio

    body = _register(client)
    code = asyncio.run(_issue_code(body["user"]["id"]))
    ok = client.post("/api/v1/auth/token", data={"grant_type": "authorization_code", "code": code})
    assert ok.status_code == 200
    replay = client.post(
        "/api/v1/auth/token", data={"grant_type": "authorization_code", "code": code}
    )
    assert replay.status_code == 401


def test_token_bad_grant_400(client: TestClient) -> None:
    res = client.post("/api/v1/auth/token", data={"grant_type": "password"})
    assert res.status_code == 400

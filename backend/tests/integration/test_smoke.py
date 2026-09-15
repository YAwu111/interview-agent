"""冒烟：应用可启动、health 200、受保护路由 401/200、错误体 {detail}。"""

from fastapi.testclient import TestClient

from app.access.auth.service import create_access_token


def test_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_protected_route_requires_token(client: TestClient) -> None:
    res = client.get("/api/v1/chat/sessions")
    assert res.status_code == 401
    assert "detail" in res.json()


def test_protected_route_with_token(client: TestClient) -> None:
    token = create_access_token("u-test")
    res = client.get("/api/v1/chat/sessions", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == []


def test_bad_token_is_401(client: TestClient) -> None:
    res = client.get("/api/v1/chat/sessions", headers={"Authorization": "Bearer bogus"})
    assert res.status_code == 401


def test_request_id_roundtrip(client: TestClient) -> None:
    res = client.get("/health", headers={"X-Request-ID": "rid-123"})
    assert res.headers["x-request-id"] == "rid-123"

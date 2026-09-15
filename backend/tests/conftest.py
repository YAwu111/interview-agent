import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import redis.asyncio as redis
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.access.auth.code_store import RedisCodeStore, get_code_store
from app.core.config import settings
from app.data.db.models.auth import OAuthAccount, RefreshToken, User
from app.data.db.session import get_session
from main import app

# 真实 PG（docker ia-postgres）+ Redis db1（测试隔离），每测清空
# NullPool / redis 工厂：pytest 内 asyncio.run 与 TestClient 各建事件循环，连接不跨循环复用
test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)

TEST_REDIS_URL = settings.redis_url.rsplit("/", 1)[0] + "/1"


def make_redis() -> redis.Redis:
    return redis.from_url(TEST_REDIS_URL, decode_responses=True)


async def _override_session() -> AsyncGenerator[AsyncSession]:
    async with TestSession() as s:
        yield s


app.dependency_overrides[get_session] = _override_session
app.dependency_overrides[get_code_store] = lambda: RedisCodeStore(make_redis())


async def _clean() -> None:
    async with TestSession() as s:
        for model in (RefreshToken, OAuthAccount, User):
            await s.execute(delete(model))
        await s.commit()
    r = make_redis()
    await r.flushdb()
    await r.aclose()


@pytest.fixture(scope="session", autouse=True)
def _require_infra() -> None:
    """无 docker PG/Redis 时整组跳过并给出提示，而非满屏连接错误。"""

    async def ping() -> None:
        async with test_engine.connect():
            pass
        r = make_redis()
        await r.ping()
        await r.aclose()

    try:
        asyncio.run(ping())
    except Exception as e:
        pytest.skip(f"测试需要本地 docker 容器 ia-postgres / ia-redis 在线：{e!r}")


@pytest.fixture(autouse=True)
def _clean_state() -> Generator[None]:
    asyncio.run(_clean())
    yield


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

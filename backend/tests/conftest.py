import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from urllib.parse import urlparse, urlunparse

os.environ.setdefault("LANGSMITH_TRACING", "false")  # 测试不联网追踪，避免 LangSmith 噪声

import pytest
import redis.asyncio as redis
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.access.auth.code_store import RedisCodeStore, get_code_store
from app.core.config import settings
from app.data.db.models import Base
from app.data.db.session import get_session
from app.telemetry.collector.usage import RedisUsageSink
from main import app


def _with_path(url: str, path: str) -> str:
    p = urlparse(url)
    return urlunparse(p._replace(path=path))


ADMIN_URL = _with_path(settings.database_url, "/postgres")
TEST_DB_NAME = urlparse(settings.database_url).path.lstrip("/") + "_test"
TEST_DATABASE_URL = _with_path(settings.database_url, f"/{TEST_DB_NAME}")

# NullPool + redis 工厂：pytest 内 asyncio.run 与 TestClient 各建事件循环，连接不跨循环复用
test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)

TEST_REDIS_URL = settings.redis_url.rsplit("/", 1)[0] + "/1"


def make_redis() -> redis.Redis:
    return redis.from_url(TEST_REDIS_URL, decode_responses=True)


async def _override_session() -> AsyncGenerator[AsyncSession]:
    async with TestSession() as s:
        yield s


app.dependency_overrides[get_session] = _override_session
app.dependency_overrides[get_code_store] = lambda: RedisCodeStore(make_redis())


async def _reset_test_db() -> None:
    """每次测试会话重建测试库 + 建表，保证 schema 与模型一致、不碰开发库。"""
    admin = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    async with admin.connect() as c:
        await c.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"'))
        await c.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    await admin.dispose()

    async with test_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(scope="session", autouse=True)
def _prepare_infra() -> Generator[None]:
    async def ping() -> None:
        admin = create_async_engine(ADMIN_URL, poolclass=NullPool)
        async with admin.connect():
            pass
        await admin.dispose()
        r = make_redis()
        await r.ping()
        await r.aclose()

    try:
        asyncio.run(ping())
        asyncio.run(_reset_test_db())
    except Exception as e:
        pytest.skip(f"测试需要本地 docker 容器 ia-postgres / ia-redis 在线：{e!r}")
    yield


async def _clean() -> None:
    async with TestSession() as s:
        tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        await s.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        await s.commit()
    r = make_redis()
    await r.flushdb()
    await r.aclose()


@pytest.fixture(autouse=True)
def _clean_state() -> Generator[None]:
    asyncio.run(_clean())
    yield


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        # 指向测试库；避免 ChatService 等经 app.state 误用开发库
        app.state.sessionmaker = TestSession
        app.state.redis = make_redis()
        app.state.usage_sink = RedisUsageSink(make_redis(), TestSession)
        app.state.chat_service = None
        yield c


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

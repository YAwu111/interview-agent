from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI

from app.access.gateway.idempotency import IdempotencyMiddleware
from app.access.gateway.middleware import (
    RequestIDMiddleware,
    add_exception_handlers,
    add_middleware,
)
from app.access.gateway.router import api_router
from app.core.logging import configure_logging, get_logger
from app.data.cache.client import build_redis
from app.data.db.engine import build_engine, build_sessionmaker
from app.domains.chat.repository import fail_stale_streaming
from app.orchestration.agents.interview.factory import build_interview_runner

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """懒连接：只构造 Engine/Session/Redis 对象，首次使用时才触达 PG/Redis。"""
    configure_logging()
    engine = build_engine()
    app.state.db_engine = engine
    app.state.sessionmaker = build_sessionmaker(engine)
    app.state.redis = build_redis()
    app.state.interview_runner = build_interview_runner(app.state.sessionmaker)
    try:
        async with app.state.sessionmaker() as s:
            older_than = datetime.now(UTC) - timedelta(minutes=10)
            await fail_stale_streaming(s, older_than)
            await s.commit()
    except Exception:
        logger.warning("startup_stale_streaming_sweep_failed", exc_info=True)
    yield
    svc = getattr(app.state, "chat_service", None)
    if svc is not None:
        await svc.aclose()
    await app.state.interview_runner.aclose()
    await app.state.redis.aclose()
    await engine.dispose()


app = FastAPI(title="interview-agent", lifespan=lifespan)

add_middleware(app)
add_exception_handlers(app)
app.add_middleware(IdempotencyMiddleware, state=app.state)
app.add_middleware(RequestIDMiddleware)
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    # Windows 下 uvicorn 默认 ProactorEventLoop，psycopg 异步不支持，改用 Selector
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        loop="app.core.loop:selector_loop_factory",
    )

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.access.gateway.middleware import (
    RequestIDMiddleware,
    add_exception_handlers,
    add_middleware,
)
from app.access.gateway.router import api_router
from app.core.logging import configure_logging
from app.data.cache.client import build_redis
from app.data.db.engine import build_engine, build_sessionmaker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """懒连接：只构造 Engine/Session/Redis 对象，首次使用时才触达 PG/Redis。"""
    configure_logging()
    engine = build_engine()
    app.state.db_engine = engine
    app.state.sessionmaker = build_sessionmaker(engine)
    app.state.redis = build_redis()
    yield
    await app.state.redis.aclose()
    await engine.dispose()


app = FastAPI(title="interview-agent", lifespan=lifespan)

add_middleware(app)
add_exception_handlers(app)
app.add_middleware(RequestIDMiddleware)
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

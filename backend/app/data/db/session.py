from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session(request: Request) -> AsyncGenerator[AsyncSession]:
    """Session 依赖：只供各 domain 的 repository 使用，router 禁止直连。"""
    factory = request.app.state.sessionmaker
    async with factory() as session:
        yield session

"""uvicorn 自定义 loop 工厂：Windows 下 psycopg 异步需要 SelectorEventLoop。"""

import asyncio


def selector_loop_factory() -> asyncio.SelectorEventLoop:
    return asyncio.SelectorEventLoop()

# psycopg async 不支持 Windows 默认的 ProactorEventLoop；
# 包导入即生效，覆盖 uvicorn 与 pytest 两种入口
import asyncio
import sys


def selector_loop_factory() -> asyncio.AbstractEventLoop:
    """uvicorn ≥0.36 直接构造 ProactorEventLoop，需 `--loop app:selector_loop_factory` 启动。"""
    return asyncio.SelectorEventLoop()


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

"""登录/注册的 Redis 固定窗口限流（按 IP）。"""

from fastapi import HTTPException, Request

from app.data.cache.keys import RATE_LIMIT


class RateLimiter:
    def __init__(self, limit: int = 20, window_seconds: int = 900) -> None:
        self.limit = limit
        self.window_seconds = window_seconds

    async def __call__(self, request: Request) -> None:
        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            return
        ip = request.client.host if request.client else "unknown"
        key = f"{RATE_LIMIT}auth:{ip}"
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, self.window_seconds)
        if current > self.limit:
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

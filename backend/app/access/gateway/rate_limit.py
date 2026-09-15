"""限流接入位置（暂未启用）。

实现时直接用 slowapi（Redis 存储，IP/User 维度），不自研；
Redis 键走 app.data.cache.keys.RATE_LIMIT 前缀。
"""

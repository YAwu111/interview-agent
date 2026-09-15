"""幂等性接入位置（接口位，暂不实现）。

契约：前端离线重放携带 `Idempotency-Key` 头。
流程：读 key → 算 payload hash → 查 key（同 key 同 payload 返回原结果；
同 key 不同 payload → 409；in-flight 重复策略实现时再定）。
Redis 快速状态 + PG 持久化，Middleware 只编排，经 Idempotency Service → Repository 落库。
"""

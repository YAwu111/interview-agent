# backend

FastAPI 模块化单体：四层横切骨架（`access` 接入 / `orchestration` 编排 / `data` 数据 / `telemetry` 检测）+ `domains` 业务领域。

## 运行

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -e ".[dev]"
uvicorn main:app --reload                                # /health；API 前缀 /api/v1
```

懒连接设计：本机无 PG/Redis 也能启动；`.env` 覆盖默认连接串。

## 门禁

```bash
python -m compileall main.py app
ruff check .
lint-imports        # 四层依赖方向契约（pyproject.toml）
pytest              # tests/，含 smoke（health 200 + 无 token 401）
alembic upgrade head  # 需 PG 在线
```

## 分层约束（import-linter 强制）

`access → domains/orchestration → data → core`；telemetry 只依赖 core/data，被 access/domains/orchestration 单向调用；domains 之间禁止互引；router 不直连 DB/Redis（经 service → repository）；鉴权在 gateway 聚合处统一注入。

## 待实现

- access/auth：login/register/refresh（依赖用户表）、OAuth（Authlib，路由位已留）
- gateway：slowapi 限流、Idempotency-Key 幂等（Redis 快速态 + PG 持久化）
- data：domain models 落 `data/db/models` 注册、Alembic 首迁移、rag 适配实现（pgvector）
- telemetry：TokenUsageEvent 采集与存储、`/monitoring/usage` 真实数据
- orchestration：LangGraph 接入后启用 OpenTelemetry

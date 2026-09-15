# Orchestration 编排层

> 具体设计（图形态、状态 schema、节点契约、检索与降级、实施顺序）见 **[DESIGN.md](DESIGN.md)**。

Agent 代码的家：`agents/`（agent 定义与图装配）、`tools/`（检索/资源等工具）、`memory/`（会话记忆与上下文）。内部结构自行设计，本文件只规定**与其他层对接的硬约束**。

## 1. 依赖方向（import-linter 强制，CI 门禁）

契约在 `backend/pyproject.toml`，`lint-imports` 必须过。对本层最关键的一条：

> **orchestration 只能 import `app.core` 和 `app.data`**（含自身）。禁止 import `app.access` / `app.domains` / `app.telemetry`。

由此产生三个对接推论：

- **用户身份**：不能解析 JWT 也不能 import auth。`user_id` 由调用方（domains.chat）作为参数传入。
- **领域能力**：不能 import domains.knowledge/resources。需要检索知识库 → 用 `app.data.rag`（retriever / vector_store / embeddings / chunking 已占位）；需要领域业务逻辑 → 要么下沉到 `app.data`（repository 模式），要么在 `app.access.gateway` 聚合处注入（鉴权就是这个模式）。
- **telemetry**：`telemetry/events/token_usage.py` 已定义 `TokenUsageEvent`，但契约禁止本层 import telemetry。用量事件两条路：调用方在编排外采集，或在 core 定义事件接口、由上层注入实现。设计时先定这条，别直接 import。

反向：`app.access.gateway.router` 负责把 domains/telemetry 路由聚合并统一注入鉴权；编排层的 HTTP 出口走 domains.chat（SSE 路由属于 chat），不直接挂路由。

## 2. data 层怎么用

- **DB**：`app.data.db.session.get_session` 是 FastAPI 依赖，注释明确"只供各 domain 的 repository 使用"。编排层在非请求上下文（后台任务/长会话）不要复用请求级 session，用 `app.state.sessionmaker` 自建。
- **Redis**：`app.data.cache.client.build_redis()` 只构造不连接（懒连接）。键前缀统一在 `app/data/cache/keys.py` 登记，现有：`rl:` `idem:` `usage:` `cache:` `code:`。agent 的会话状态/图 checkpoint 若存 Redis，先在 keys.py 加新前缀再用。
- **测试环境**：测试用 db1（`make_redis()` 工厂）+ engine `NullPool`，见 `tests/conftest.py`。跨事件循环复用连接会炸（`Task got Future attached to a different loop`），照抄 conftest 模式。

## 3. 前端契约（SSE）

出口格式必须与前端解析器对齐（`frontend/src/shared/services/types.ts`）：

```ts
SSEChunk = { type: 'delta'; content: string }   // 增量文本
         | { type: 'sources'; items: SourceItem[] }  // RAG 引用
         | { type: 'done' }
         | { type: 'error'; message: string }
```

入口 `streamChat(sessionId, text)`，另有 `stop(sessionId)` → 编排要支持中断（前端带 AbortSignal，401 会自动刷新重试一次）。事件类型若要扩展（如 agent 步骤可视化），前后端同步改，别单方面加。

## 4. 运行环境坑

- **Windows 事件循环**：psycopg async 不支持 ProactorEventLoop。启动必须 `uvicorn main:app --loop app:selector_loop_factory`（`start.sh` 已内置）。LangGraph/任何 async 库同样受此约束；Linux 容器内无此问题。
- **配置**：LLM API key 等加在 `app/core/config.py` 的 `Settings`，同步 `backend/.env`；密钥不进仓库。
- **新依赖**：进 `backend/pyproject.toml`，`pip install -e .[dev]`。

## 5. 门禁（改动后必过）

```bash
ruff check . && ruff format --check .   # 行宽 100，启用 ASYNC 规则
lint-imports                            # 6 条依赖契约
pytest                                  # 需 docker compose up -d（PG 5432 / Redis 6379）
```

## 待你设计

agents/ memory/ tools/ 的内部结构、图形态、模型选型、OpenTelemetry 接入时机——本文件不涉及。

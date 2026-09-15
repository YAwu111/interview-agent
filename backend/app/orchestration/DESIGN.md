# 面试 Agent 编排设计（单 Agent + 混合双路检索 + 自循环追问）

本文件是 `orchestration/` 层的实现契约：状态 schema、节点级 I/O、prompt 契约、SSE 时序、
持久化分工、模型档位、降级路径与实施顺序。与 `README.md` 的分层约束冲突时，以 README 为准。

## 0. 一句话架构

一张 LangGraph 图 + `mode` 分支：**横向多视角语义分析（广度）** 与 **纵向自适应追问（深度）**
通过**短期能力状态**连接；每轮用户消息 = 一次 `ainvoke`（图外循环，`thread_id = session_id`），
`interrupt()` 只用于真正需要人工确认的暂停点（v1 保留给报告确认，暂不启用）。

```text
用户消息 ──► prepare ──► (mode=chat) ──► retrieve ──► answer ──► persist ──► END
                   │
                   └──(mode=interview)
                          │
                          ├─► analyze:  decompose → critics(动态路由,并行) → judge
                          │                    ↑ 横向：广度
                          ├─► probe:    update_memory → select_weakness → generate_probe
                          │                    ↑ 纵向：深度（probe_level 1→2→3）
                          └─► answer(点评+追问, 流式) ──► persist ──► END
                                │
                                └─ 触发终止（轮次/预算/质量/用户结束）→ finalize → persist → END
```

## 1. 状态 schema（`orchestration/agents/interview/state.py`）

```python
class InterviewState(TypedDict):
    # 输入（调用方注入，编排层不解析 JWT）
    user_id: str
    session_id: str
    mode: Literal["chat", "interview"]
    user_input: str
    history: list[dict]  # [{role, content}]，最近 N 条，由 chat 域读取后传入
    personal_context: str  # 简历/JD/资源摘要（get_personal_context 产出）
    # 检索
    retrieved: list[dict]  # [{id, title, snippet, base_name, score}] → 前端 SourceItem
    # 横向分析（面试模式）
    claims: list[dict]  # decompose 产出：{id, type, text, has_evidence}
    critic_reports: list[dict]  # 本轮实际运行的 critic 输出
    abilities: dict[str, Ability]  # 短期能力状态（跨轮持久化）
    unverified: list[str]
    # 纵向追问
    probe_history: list[dict]  # [{weakness, level, asked_at_round}]
    selected_weakness: dict | None
    probe_level: int  # 当前弱点的追问层级，1..3
    round_index: int  # 已完成的问答轮次
    # 产出与预算
    answer: str
    sources: list[dict]
    end_reason: Literal["round_limit", "budget", "quality_met", "user_end"] | None
    llm_calls: int
    usage: list[dict]  # 每节点一条 {node, model, prompt_tokens, completion_tokens, latency_ms}


class Ability(TypedDict):
    dimension: str  # technical|logic|depth|evidence|consistency|completeness
    level: float  # 0..5
    confidence: float  # 0..1
    evidence_ids: list[str]
    updated_round: int
```

状态由 `langgraph-checkpoint-postgres` 持久化（`thread_id = session_id`）；业务可见数据
（消息、报告）另落业务表，见 §6。

## 2. 节点级 I/O 契约

| 节点 | 读取 | 输出 | 模型档位 |
|---|---|---|---|
| `prepare` | user_input, history, mode | personal_context | fast |
| `retrieve` | user_input, personal_context | retrieved（top-6） | 无（本地模型） |
| `decompose` | user_input, retrieved | claims[{id,type,text,has_evidence}] | fast |
| `critics` | claims, retrieved, user_input | critic_reports[]（动态路由 2~4 个） | fast |
| `judge` | critic_reports, abilities | abilities', unverified, needs_probe, selected_weakness | strong |
| `select_weakness` | abilities, probe_history, round_index | selected_weakness, probe_level | 规则（无 LLM） |
| `generate_probe` | selected_weakness, strengths, probe_level, history[-3:] | probe 文本 | strong |
| `answer` | retrieved, abilities, probe, mode | answer（流式） | fast |
| `finalize` | abilities, probe_history, end_reason | 报告 JSON + markdown | strong |

**critic 统一契约**（每个 critic 同一 schema，`response_format=json_object` + 字段校验）：

```json
{"dimension":"technical","verdict":"strong|partial|missing|unverifiable",
 "claims":["..."],"gaps":["..."],"confidence":0.0,"evidence_refs":["claim-id"]}
```

解析失败降级：`verdict=unverifiable, confidence=0.3`，记入 `critic_reports` 并在报告里标注
“本轮 N 个维度未完成评估”。**critics 共享本轮 `retrieved`**，不各自检索。

**judge 输出契约**：

```json
{"abilities":[{"dimension":"depth","level":3.5,"confidence":0.7,"evidence_refs":["c2"]}],
 "unverified":["未说明失败案例"],"needs_probe":true,
 "selected_weakness":{"dimension":"depth","reason":"..."}}
```

## 3. 动态 critic 路由（R4-Q2 = b）

`decompose` 产出 claim 类型后，按固定映射挑 2~4 个 critic（`CRITIC_MIN/MAX` 可配）：

| claim 类型 | 必跑 critic |
|---|---|
| `tech_claim`（技术断言） | technical, evidence, depth |
| `behavior_story`（行为叙述） | logic, consistency, completeness |
| `result_metric`（结果/数据） | evidence, completeness |
| `opinion`（观点/取舍） | logic, depth |

其余 critic 不跑；每轮实际运行的维度写入 `critic_reports` 与报告，供可信度说明。

## 4. `select_weakness` 标定（R4-Q4 = d）

- 因子离散 1–3 级（LLM/规则产出）：`severity, importance, uncertainty, relevance, probeability`。
- 打分：加权和 `0.30*uncertainty + 0.25*relevance + 0.20*severity + 0.15*importance + 0.10*probeability`。
- 硬约束：同一 weakness 已追问次数 `>= PROBE_MAX_PER_WEAKNESS`（默认 2）→ 权重乘 0.3；
  本轮已问过 → 直接排除。
- `probe_level` 递进语义：1 = 表层事实/流程；2 = 边界条件与权衡；3 = 反例/失败经验/极端场景。
- 全部弱点都被追问过或 `needs_probe=false` → 触发 `quality_met` 收尾。

## 5. 检索设计（混合双路 + 精排）

- Embedding：`BAAI/bge-m3`（1024 维，本地 GPU）；精排：`BAAI/bge-reranker-v2-m3`（cross-encoder，本地 GPU）。
  两者进程内加载（`sentence-transformers`），模型名走 `.env`；换 `bge-large-zh-v1.5` 只需改配置 + 迁移列宽。
- 稀疏路：`jieba` 分词后写入 `chunks.tsv (tsvector)`，PG 侧 `simple` 配置 + `ts_rank_cd` 排序（无 zhparser 依赖）。
- 融合：dense top-20 + sparse top-20 → RRF（k=60）→ top-10 → 精排 → **top-6** 进 prompt。
- 切分：按中文句读边界切，目标 480 字 / overlap 64 字（`CHUNK_SIZE/OVERLAP` 可配）。
- 向量索引：pgvector `hnsw (vector_cosine_ops)`；稀疏路 `GIN(tsv)`。
- `web_search` 结果**只进本轮上下文，绝不入库**；引用标记 `[来源:title]`。

## 6. 持久化分工

| 数据 | 位置 | 说明 |
|---|---|---|
| 图执行状态（abilities/probe_history/claims…） | LangGraph checkpoint（同一个 PG） | 可回放、可回归测试 |
| 会话/消息 | `sessions` / `messages`（chat 域） | 前端唯一事实源 |
| 知识库 | `knowledge_bases` / `documents` / `chunks(vector(1024), tsv)` | 入库与检索 |
| 资源 | `resources` | 简历/JD/资料文件元数据 |
| 面试报告 | `interview_reports(session_id, user_id, overall, dimensions jsonb, strengths jsonb, weaknesses jsonb, next_steps jsonb, end_reason, model_used, created_at)` | `finalize` 落库 |
| 用量 | telemetry（core `UsageSink` Protocol 注入） | 见 §8 |

## 7. SSE 时序与前端改动（R2-Q6 = b / R4-Q6 = b）

一次请求一条流，事件顺序：

```text
status{stage:"retrieving", round:n}
status{stage:"analyzing",  round:n}      # 面试模式才有
delta(点评/作答文本, 流式)
status{stage:"probing",    round:n}      # 面试模式且 needs_probe
delta(追问文本, 流式)
sources(items)                           # 有引用时
status{stage:"finalizing"} → delta(报告 markdown) → done
```

前端改动清单（需与后端同批改，禁止单方面扩展）：

1. `frontend/src/shared/services/types.ts`：`SSEChunk` 增加 `{type:'status'; stage:string; round?:number}`。
2. `frontend/src/features/chat/services/sseClient.ts` 与 `sseParser`：透传解析（解析器无需改，仅类型放宽）。
3. `chatStore`：新增 `status` 字段（当前阶段/轮次），`done` 时清空。
4. `ChatWorkspace`：输入区上方显示一行状态文本（如“正在检索知识库…”），弱网下有明确反馈。

中断语义：`stop` → 取消 SSE → 保留已产出文本 → 该轮 checkpoint 不写入结果（`llm_calls` 预算照记）。

## 8. 模型档位与配置（R3-Q3 = b）

`.env` / `Settings` 新增：

```text
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=...
LLM_MODEL_FAST=deepseek-chat          # 工具决策、作答、critics、decompose
LLM_MODEL_STRONG=deepseek-v4-pro   # judge、generate_probe、finalize、报告
LANGSMITH_TRACING / LANGSMITH_API_KEY / LANGSMITH_PROJECT=interview-agent
EMBEDDING_MODEL=BAAI/bge-m3
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
ROUND_LIMIT=10            # 总轮次上限（用户要求从 5 提到 10）
PROBE_MAX_PER_WEAKNESS=2
LLM_CALL_BUDGET=60        # 单会话 LLM 调用预算
CHUNK_SIZE=480  CHUNK_OVERLAP=64  RETRIEVE_TOP_K=6
```

用量采集：`app/core` 定义 `UsageSink` Protocol（`async record(event: TokenUsageEvent)`），
编排层只依赖 Protocol（满足 import-linter），由 `domains/chat` 注入实现（写 `usage:` Redis 计数 +
PG 日聚合）。每个节点调用后上报一次，字段含 `node/model/prompt_tokens/completion_tokens/latency_ms`。

## 9. 终止与降级

终止（任一命中 → `finalize`）：`round_index >= ROUND_LIMIT` → `end_reason=round_limit`；
`llm_calls >= LLM_CALL_BUDGET` → `budget`；全部弱点已追问或 `needs_probe=false` → `quality_met`；
用户点「结束面试」（chat 域下发指令）→ `user_end`。

降级链：embedding/精排失败 → 只走稀疏路（发 `status{stage:"degraded"}`）；
critics 部分失败 → 跳过该维度并降 confidence；judge 失败 → 不追问，直接作答；
LLM 超时（默认 60s/次，流式首字 15s）→ 重试 1 次，仍失败返回 `error` 事件 + 保留部分文本；
HF 模型不可用 → 启动即失败并给出明确错误（不做静默降级，避免检索静默失效）。

## 10. 目录落位

```text
backend/app/orchestration/
  agents/interview/{graph.py, state.py, nodes/{prepare,decompose,critics,judge,select_weakness,probe,answer,finalize}.py, prompts/}
  agents/chat/graph.py          # 轻量：retrieve → answer
  tools/{registry.py, knowledge.py, personal.py, websearch.py}
  memory/short_term.py          # abilities/probe_history 的读写与合并规则
  llm/{client.py, tiers.py}     # httpx 直连 DeepSeek（chat/stream/tools/json_object）+ 档位映射
backend/app/data/rag/
  embeddings.py  vector_store.py  retriever.py  rerank.py  chunking.py   # 实现既有 Protocol
backend/app/domains/chat/
  router.py（SSE 路由）/ service.py（编排调用 + UsageSink 注入）/ repository.py / models.py
backend/scripts/seed_knowledge.py     # 种子文档入库（txt/md/pdf）
```

## 11. 实施顺序与门禁

1. 基础设施：compose 换 `pgvector/pgvector:pg16`、迁移（`vector` 扩展 + 6 张表 + HNSW/GIN 索引）、config/`.env` 增项、依赖（langgraph、langgraph-checkpoint-postgres、jieba、sentence-transformers、torch、pypdf、langsmith）
2. 检索层：`embeddings/vector_store/retriever/rerank/chunking` 实现 + `seed_knowledge.py` + 单测（RRF 融合、切分、真实 PG 检索 smoke）
3. LLM 客户端与档位：`llm/client.py`（流式、tool calling、json_object）+ 单测（stub transport，不打真实 API）
4. 自由对话图：`retrieve → answer`，接 `domains/chat` SSE + `status` 事件 + 消息落库
5. 面试图：decompose → critics（动态路由并行）→ judge → select_weakness → probe → answer；状态 schema + checkpoint
6. `finalize` 报告 + `interview_reports` 落库；`UsageSink` 注入与用量记录
7. 评估：`backend/tests/eval/`（eval set + 关键词/来源/拒答/路径断言，跑 3 次报区间）+ LangSmith trace 人工抽查 2 条

门禁：`ruff check . && ruff format --check .`、`lint-imports`、`pytest`（需 compose 起 PG/Redis）、
`python -m compileall main.py app`、前端 `npm run build && npm run lint && npm test`（SSE 类型改动后）。

## 12. 待验证清单（实施第一天先做）

1. `langgraph-checkpoint-postgres` 安装 + `AsyncPostgresSaver.setup()` 与现有 PG 16 的兼容性。
2. DeepSeek 侧：tool calling 与 `json_object` 在 `LLM_MODEL_FAST` 上的真实可用性；`LLM_MODEL_STRONG` 的确切 model id。
3. 12GB 显存下 bge-m3 + bge-reranker-v2-m3 同载、并发 4 路时的峰值占用；不足则精排 batch=1 或换 `bge-small-zh`。
4. HF 模型下载与缓存路径（`HF_TOKEN` 是否需要、`HF_HOME` 落盘位置）。
5. Windows 事件循环：`--loop app:selector_loop_factory` 下 LangGraph async 与 psycopg 混用的稳定性。

## 13. 未决参数（有默认值，可随时改）

- `ROUND_LIMIT=10`：你要求从 5 上调，10 是默认值；想要 15/20 直接改 `.env`。
- `LLM_CALL_BUDGET=60`：按每轮 ~4–6 次调用（1 decompose + 2–4 critics + 1 judge + 1 probe + 1 answer）估。
- `RETRIEVE_TOP_K=6`、`CHUNK_SIZE=480`：按 480 字切片、6 条引用估 prompt 约 3–4k tokens，按实测再调。

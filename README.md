# 面试 Agent

面向个人求职者的集中式多 Agent 协作对话 Web 应用：核心业务是 Agent 聊天（自由对话 + 模拟面试），辅助业务是面试资源上传与 RAG 知识库管理。

## 技术栈

- **前端**：React 19 + Vite + TypeScript + Tailwind CSS v4 + shadcn/ui（Base UI），动效 motion（GSAP 备用），react-router-dom + Zustand
- **后端**：FastAPI（Python 3.13），缓存 Redis，数据库 PostgreSQL（psycopg 驱动，ORM 待架构设计）

## 目录结构

```
interview-agent/
├── frontend/   # 求职者端 Web 应用（详见 frontend/PRODUCT.md、frontend/DESIGN.md）
└── backend/    # FastAPI 服务骨架（main.py + /health）
```

## 快速开始

一键启动（基础设施 + 迁移 + 后端 + 前端，`Ctrl+C` 全部停止）：

```bash
bash start.sh   # Git Bash；后期加进程直接在脚本里补两行
```

cmd / PowerShell / 双击用 `start.bat`（包装同一脚本，逻辑只有一份）。

或分步手动启动——基础设施（PostgreSQL + Redis，Docker）：

```bash
docker compose up -d   # ia-postgres:5432 / ia-redis:6379，含健康检查与自动重启
```

前端（默认 mock 数据，无需后端即可体验完整流程）：

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

后端：

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash；PowerShell 用 .venv\Scripts\Activate.ps1
pip install -e .[dev]
alembic upgrade head            # 建表（需基础设施已启动）
uvicorn main:app --reload --loop app:selector_loop_factory   # http://localhost:8000
# --loop 仅 Windows 需要（psycopg async 不支持 ProactorEventLoop）；Linux/macOS 直接 uvicorn main:app --reload
```

前端接真实后端：在 `frontend/.env.local` 设 `VITE_API_MODE=live`，dev 服务器会把 `/api` 代理到 `http://localhost:8000`。

## 前端门禁

```bash
cd frontend
npm run build   # tsc + vite 构建
npm run lint    # oxlint
npm test        # SSE 解析器纯函数单测（Node 内置 runner）
```

## 状态

- 前端 v1：认证 / 聊天工作台（流式 + 模拟面试 + RAG 引用）/ 知识库 / 资源 / 设置 已完成，mock 先行
- 后端：仅骨架；业务接口、ORM、agent 编排架构待设计
- **待补齐（后端完善后）**：前端请求层（`frontend/src/shared/services/apiClient.ts`）的四个弱网策略模块——缓存、指数退避重试、并发限制、离线重放队列（依赖后端 `Idempotency-Key` 去重）。届时以 axios 拦截器形式挂入，核心请求语义不变

#!/usr/bin/env bash
# 一键启动：基础设施 + 迁移 + 后端(8000) + 前端(5173)；Ctrl+C 停止全部
# 后期加进程：照下面模式补两行即可（后台启动 + 记入 pids）
set -euo pipefail
cd "$(dirname "$0")"

PY="$PWD/backend/.venv/Scripts/python.exe"
[ -f "$PY" ] || PY="$PWD/backend/.venv/bin/python"   # Linux/macOS 兜底

pids=()
cleanup() {
  kill "${pids[@]}" 2>/dev/null || true
  # Windows 下 --reload/vite 子进程可能残留占端口，按端口兜底清理
  if command -v powershell >/dev/null; then
    powershell -NoProfile -Command 'Get-NetTCPConnection -LocalPort 8000,5173 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }' >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

echo "==> [1/4] 基础设施 postgres:5432 redis:6379"
docker compose up -d --wait

echo "==> [2/4] 数据库迁移"
(cd backend && "$PY" -m alembic upgrade head)

echo "==> [3/4] 后端 http://localhost:8000"
(cd backend && "$PY" -m uvicorn main:app --reload --port 8000 --loop app:selector_loop_factory) &
pids+=($!)

echo "==> [4/4] 前端 http://localhost:5173"
(cd frontend && npm run dev -- --clearScreen false) &
pids+=($!)

wait

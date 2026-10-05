"""面试 runner：跑分析图（LangGraph），自行流式产出点评/追问/报告（raw httpx 流式）。"""

import json
from collections.abc import AsyncIterator

from langgraph.checkpoint.memory import InMemorySaver

from . import prompts
from .deps import InterviewDeps
from .graph import build_graph
from .schemas import InterviewReport, parse_llm


class InterviewRunner:
    def __init__(
        self,
        deps: InterviewDeps | None = None,
        *,
        sessionmaker=None,
        usage_sink=None,
        db_url: str | None = None,
    ) -> None:
        self._deps = deps
        self._sessionmaker = sessionmaker
        self._usage_sink = usage_sink
        self._db_url = db_url
        self._graph = None
        self._checkpointer = None
        self._saver_ctx = None

    async def _ensure_deps(self) -> InterviewDeps:
        if self._deps is None:
            from .factory import build_deps  # 延迟 import，避免测试注入 fake deps 时拉起模型

            self._deps = build_deps(self._sessionmaker, self._usage_sink)
        return self._deps

    async def _get_graph(self, deps: InterviewDeps):
        if self._graph is None:
            if self._db_url:
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

                ctx = AsyncPostgresSaver.from_conn_string(self._db_url)
                saver = await ctx.__aenter__()
                await saver.setup()
                self._saver_ctx = ctx
            else:
                saver = InMemorySaver()
            self._checkpointer = saver
            self._graph = build_graph(deps, saver)
        return self._graph

    def _config(self, session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}}

    async def aclose(self) -> None:
        """关闭 checkpointer 与 llm 底层连接；fake deps / InMemorySaver 无 close 时安全跳过。"""
        checkpointer = self._checkpointer
        if checkpointer is not None:
            close = getattr(checkpointer, "aclose", None)
            if close is not None:
                await close()
        ctx = self._saver_ctx
        if ctx is not None:
            await ctx.__aexit__(None, None, None)
        deps = self._deps
        if deps is not None and deps.llm is not None:
            llm_close = getattr(deps.llm, "aclose", None)
            if llm_close is not None:
                await llm_close()

    async def stream(
        self,
        *,
        user_id: str,
        session_id: str,
        text: str,
        history: list[dict],
        personal_context: str,
    ) -> AsyncIterator[dict]:
        deps = await self._ensure_deps()
        graph = await self._get_graph(deps)
        cfg = self._config(session_id)
        input_state = {
            "user_id": user_id,
            "session_id": session_id,
            "mode": "interview",
            "text": text,
            "history": history,
            "personal_context": personal_context,
        }
        yield {"type": "status", "stage": "retrieving"}
        final = await graph.ainvoke(input_state, cfg)

        if final.get("opening"):
            yield {"type": "status", "stage": "answering"}
            yield {"type": "delta", "content": final.get("opening_text", "")}
            yield {"type": "done"}
            return

        if final.get("sources"):
            yield {"type": "sources", "items": final["sources"]}

        if self._should_finalize(final):
            async for ev in self._emit_report(deps, user_id, final):
                yield ev
            return

        yield {"type": "status", "stage": "answering"}
        async for ev in self._stream_answer(deps, final):
            yield ev
        if final.get("needs_probe") and final.get("probe_text"):
            yield {"type": "status", "stage": "probing"}
            yield {"type": "delta", "content": final["probe_text"]}
        yield {"type": "done"}

    async def finalize(
        self,
        *,
        user_id: str,
        session_id: str,
        history: list[dict],
        personal_context: str,
    ) -> AsyncIterator[dict]:
        deps = await self._ensure_deps()
        graph = await self._get_graph(deps)
        state = await graph.aget_state(self._config(session_id))
        final: dict = (state.values or {}).copy()
        final.setdefault("history", history)
        final.setdefault("personal_context", personal_context)
        if not final.get("abilities") and final.get("round_index", 0) == 0:
            yield {"type": "delta", "content": "本次面试尚未开始，无法生成报告。"}
            yield {"type": "done"}
            return
        async for ev in self._emit_report(deps, user_id, final):
            yield ev

    def _should_finalize(self, state: dict) -> bool:
        if state.get("round_index", 0) >= self._deps.round_limit:
            return True
        if state.get("llm_calls", 0) >= self._deps.llm_call_budget:
            return True
        if not state.get("needs_probe") and state.get("round_index", 0) >= 2:
            return True
        return False

    async def _stream_answer(self, deps: InterviewDeps, state: dict) -> AsyncIterator[dict]:
        context = "\n\n".join(
            f"[来源:{h.get('title', '')}]\n{h.get('text', '')[:400]}"
            for h in state.get("retrieved", [])
        )
        messages = [
            {"role": "system", "content": prompts.ANSWER_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"候选回答：{state.get('text', '')}\n资料：{context}\n"
                    f"画像：{json.dumps(state.get('abilities', {}), ensure_ascii=False)}\n"
                    "请点评并引出追问。"
                ),
            },
        ]
        usage: dict = {}
        async for ev in deps.llm.stream(messages, deps.fast_model):
            if ev.get("type") == "delta":
                yield {"type": "delta", "content": ev["content"]}
            elif ev.get("type") == "usage":
                usage = ev.get("usage", {})
        if deps.usage_sink and usage:
            await deps.usage_sink.record(
                state.get("user_id", ""),
                {
                    "node": "answer",
                    "model": deps.fast_model,
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "latency_ms": 0,
                },
            )

    async def _emit_report(
        self, deps: InterviewDeps, user_id: str, state: dict
    ) -> AsyncIterator[dict]:
        yield {"type": "status", "stage": "finalizing"}
        messages = [
            {"role": "system", "content": prompts.REPORT_SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "abilities": state.get("abilities", {}),
                        "probe_history": state.get("probe_history", []),
                        "unverified": state.get("unverified", []),
                        "round_index": state.get("round_index", 0),
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        res = await deps.llm.chat(messages, deps.fast_model, json_mode=True, max_tokens=2000)
        out = parse_llm(res.get("content"), InterviewReport)
        report = out.model_dump() if out else {}
        if deps.usage_sink:
            usage = res.get("usage") or {}
            await deps.usage_sink.record(
                user_id,
                {
                    "node": "finalize",
                    "model": deps.fast_model,
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "latency_ms": res.get("latency_ms", 0),
                },
            )
        yield {"type": "report", "report": report}
        yield {"type": "delta", "content": _report_markdown(report)}
        yield {"type": "done"}


def _report_markdown(report: dict) -> str:
    overall = report.get("overall", 0)
    lines = [f"# 面试报告（综合评分 {overall}/5）", ""]
    lines.append("## 各维度")
    for d in report.get("dimensions") or []:
        lines.append(f"- {d.get('dimension', '')}：{d.get('level', 0)}/5 — {d.get('comment', '')}")
    lines.append("")
    lines.append("## 亮点")
    strengths = report.get("strengths") or []
    lines += [f"- {s}" for s in strengths] if strengths else ["- （无）"]
    lines.append("## 待改进")
    weaknesses = report.get("weaknesses") or []
    lines += [f"- {w}" for w in weaknesses] if weaknesses else ["- （无）"]
    lines.append("## 下一步")
    next_steps = report.get("next_steps") or []
    lines += [f"- {n}" for n in next_steps] if next_steps else ["- （无）"]
    return "\n".join(lines)

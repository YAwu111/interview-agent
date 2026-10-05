"""面试编排单测：合并/衰减/选弱点纯逻辑 + 打桩 LLM 跑整图与 checkpoint 持久化。"""

import asyncio

from app.orchestration.agents.interview import nodes
from app.orchestration.agents.interview.deps import InterviewDeps
from app.orchestration.agents.interview.runner import InterviewRunner
from app.orchestration.agents.interview.schemas import CriticReport, parse_llm
from app.orchestration.memory.short_term import decay_unseen, merge_ability


class _FakeLLM:
    async def chat(self, messages, model, **kw):
        sys = messages[0].get("content", "") if messages else ""
        if "第一个面试问题" in sys:
            return {
                "content": "请先做 60 秒自我介绍。",
                "usage": {"total_tokens": 15},
                "latency_ms": 10,
            }
        if "语义单元" in sys:
            return {
                "content": '{"claims":[{"id":"c1","type":"tech_claim",'
                '"text":"...","has_evidence":true}]}',
                "usage": {"total_tokens": 1},
                "latency_ms": 1,
            }
        if "技术正确性" in sys or "逻辑严密性" in sys:
            return {
                "content": '{"dimension":"technical","verdict":"strong",'
                '"confidence":0.8,"evidence_refs":["c1"]}',
                "usage": {"total_tokens": 1},
                "latency_ms": 1,
            }
        if "综合多位评审" in sys:
            return {
                "content": (
                    '{"abilities":[{"dimension":"technical","level":4,"confidence":0.8,'
                    '"evidence_refs":["c1"]}],"unverified":[],"needs_probe":true,'
                    '"candidates":[{"dimension":"depth","severity":2,"importance":2,'
                    '"uncertainty":3,"relevance":3,"probeability":2}]}'
                ),
                "usage": {"total_tokens": 1},
                "latency_ms": 1,
            }
        if "递进式追问" in sys:
            return {
                "content": "能展开说说你的具体分工吗？",
                "usage": {"total_tokens": 1},
                "latency_ms": 1,
            }
        if "结构化面试报告" in sys:
            return {
                "content": '{"overall":4,"dimensions":[],"strengths":[],"weaknesses":[],'
                '"next_steps":[],"end_reason":"user_end"}',
                "usage": {"total_tokens": 1},
                "latency_ms": 1,
            }
        return {"content": "", "usage": {}, "latency_ms": 0}

    async def stream(self, messages, model, **kw):
        for ch in "点评：回答得不错，但缺少具体例子。":
            yield {"type": "delta", "content": ch}


class _FakeRetriever:
    async def retrieve(self, query, top_k=None):
        return []


def _deps() -> InterviewDeps:
    return InterviewDeps(
        llm=_FakeLLM(), retriever=_FakeRetriever(), fast_model="fast", strong_model="strong"
    )


def test_merge_ability_cold_start_and_ema() -> None:
    cold = merge_ability(None, 4.0, 0.8, ["e1"], 1)
    assert cold["level"] == 4.0 and cold["confidence"] == 0.8
    merged = merge_ability(cold, 2.0, 0.4, ["e2"], 2)
    assert merged["level"] == 3.2  # 4*(1-0.4) + 2*0.4
    assert merged["evidence_ids"] == ["e1", "e2"]


def test_decay_unseen_dims() -> None:
    abilities = {
        "a": {"level": 3, "confidence": 0.5, "evidence_ids": [], "updated_round": 1},
        "b": {"level": 2, "confidence": 0.5, "evidence_ids": [], "updated_round": 1},
    }
    out = decay_unseen(abilities, {"a"})
    assert out["a"]["confidence"] == 0.5
    assert out["b"]["confidence"] == 0.45


def test_select_weakness_weighted() -> None:
    async def run() -> None:
        deps = InterviewDeps(llm=None, retriever=None, fast_model="f", strong_model="s")
        state = {
            "candidates": [
                {
                    "dimension": "depth",
                    "severity": 2,
                    "importance": 2,
                    "uncertainty": 3,
                    "relevance": 3,
                    "probeability": 2,
                },
                {
                    "dimension": "logic",
                    "severity": 3,
                    "importance": 3,
                    "uncertainty": 1,
                    "relevance": 1,
                    "probeability": 1,
                },
            ],
            "probe_history": [],
            "round_index": 0,
        }
        out = await nodes.select_weakness(state, deps)
        assert out["selected_weakness"]["dimension"] == "depth"
        assert out["probe_level"] == 1
        assert out["round_index"] == 1

    asyncio.run(run())


def test_parse_llm_valid_coerce_and_invalid() -> None:
    ok = parse_llm('{"verdict":"strong","confidence":0.8}', CriticReport)
    assert ok is not None and ok.verdict == "strong" and ok.confidence == 0.8

    fenced = parse_llm('```json\n{"verdict":"partial","confidence":"0.5"}\n```', CriticReport)
    assert fenced is not None and fenced.verdict == "partial" and fenced.confidence == 0.5

    assert parse_llm("不是 json", CriticReport) is None
    assert parse_llm(None, CriticReport) is None
    assert parse_llm('{"verdict":"strong","confidence":1.5}', CriticReport) is None


def test_runner_opening_then_answer_persists_abilities() -> None:
    async def run() -> None:
        runner = InterviewRunner(deps=_deps())
        opening = [
            e
            async for e in runner.stream(
                user_id="u", session_id="s", text="开始面试", history=[], personal_context=""
            )
        ]
        assert any(e["type"] == "delta" and "自我介绍" in e["content"] for e in opening)
        assert opening[-1]["type"] == "done"

        history = [{"role": "assistant", "content": "请先做 60 秒自我介绍。"}]
        answer = [
            e
            async for e in runner.stream(
                user_id="u",
                session_id="s",
                text="我用 React 做了个项目",
                history=history,
                personal_context="",
            )
        ]
        delta_text = "".join(e["content"] for e in answer if e["type"] == "delta")
        assert "点评" in delta_text
        assert answer[-1]["type"] == "done"

        deps = await runner._ensure_deps()
        graph = await runner._get_graph(deps)
        st = await graph.aget_state({"configurable": {"thread_id": "s"}})
        assert "technical" in (st.values or {}).get("abilities", {})
        assert (st.values or {}).get("round_index", 0) >= 1

    asyncio.run(run())

"""面试图节点：prepare/retrieve/decompose/critics/judge/select_weakness/generate_probe。"""

import asyncio
import json
from typing import Any

from app.orchestration.memory.short_term import decay_unseen, merge_ability

from . import prompts
from .deps import InterviewDeps
from .schemas import CriticReport, DecomposeOutput, JudgeOutput, parse_llm
from .state import InterviewState

CLAIM_TYPES = {"tech_claim", "behavior_story", "result_metric", "opinion"}
CRITIC_NAMES = ("technical", "logic", "depth", "evidence", "consistency", "completeness")
CRITIC_ROUTE: dict[str, list[str]] = {
    "tech_claim": ["technical", "evidence", "depth"],
    "behavior_story": ["logic", "consistency", "completeness"],
    "result_metric": ["evidence", "completeness"],
    "opinion": ["logic", "depth"],
}


async def _record(
    deps: InterviewDeps, state: InterviewState, node: str, model: str, res: dict
) -> None:
    if deps.usage_sink is None:
        return
    usage = res.get("usage") or {}
    await deps.usage_sink.record(
        state.get("user_id", ""),
        {
            "node": node,
            "model": model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "latency_ms": res.get("latency_ms", 0),
        },
    )


def _bump(state: InterviewState, n: int = 1) -> dict:
    return {"llm_calls": state.get("llm_calls", 0) + n}


async def prepare(state: InterviewState, deps: InterviewDeps) -> dict:
    opening = state.get("mode") == "interview" and not state.get("history")
    if not opening:
        return {"opening": False}

    messages = [
        {"role": "system", "content": prompts.OPENING_SYSTEM},
        {
            "role": "user",
            "content": f"候选人资料：{state.get('personal_context') or '（无）'}",
        },
    ]
    res = await deps.llm.chat(messages, deps.strong_model, max_tokens=500)
    await _record(deps, state, "prepare", deps.strong_model, res)
    return {
        "opening": True,
        "opening_text": (res.get("content") or "请先简单介绍一下自己。").strip(),
        **_bump(state),
    }


async def retrieve(state: InterviewState, deps: InterviewDeps) -> dict:
    hits = await deps.retriever.retrieve(state.get("text", ""), deps.retrieve_top_k)
    sources = [
        {
            "id": h["id"],
            "title": h["title"],
            "snippet": h["snippet"],
            "baseName": h.get("base_name"),
        }
        for h in hits
    ]
    return {"retrieved": hits, "sources": sources}


async def decompose(state: InterviewState, deps: InterviewDeps) -> dict:
    messages = [
        {"role": "system", "content": prompts.DECOMPOSE_SYSTEM},
        {"role": "user", "content": state.get("text", "")},
    ]
    res = await deps.llm.chat(messages, deps.fast_model, json_mode=True)
    await _record(deps, state, "decompose", deps.fast_model, res)
    out = parse_llm(res.get("content"), DecomposeOutput)
    claims = [c.model_dump() for c in (out.claims if out else [])]
    if not claims:
        claims = [
            {"id": "c1", "type": "opinion", "text": state.get("text", ""), "has_evidence": False}
        ]
    for i, c in enumerate(claims):
        c["id"] = c.get("id") or f"c{i + 1}"
        if c.get("type") not in CLAIM_TYPES:
            c["type"] = "opinion"
    return {"claims": claims, **_bump(state)}


async def _run_critic(deps: InterviewDeps, state: InterviewState, dimension: str) -> dict:
    retrieved_text = json.dumps(
        [h.get("text", "")[:300] for h in state.get("retrieved", [])], ensure_ascii=False
    )
    messages = [
        {
            "role": "system",
            "content": f"{prompts.CRITIC_SYSTEM[dimension]}\n{prompts.CRITIC_OUTPUT}",
        },
        {
            "role": "user",
            "content": (
                f"候选回答：{state.get('text', '')}\n"
                f"语义单元：{json.dumps(state.get('claims', []), ensure_ascii=False)}\n"
                f"参考资料：{retrieved_text}"
            ),
        },
    ]
    try:
        res = await asyncio.wait_for(
            deps.llm.chat(messages, deps.fast_model, json_mode=True), timeout=deps.critic_timeout
        )
    except Exception:
        return {"dimension": dimension, "verdict": "unverifiable", "confidence": 0.3}
    await _record(deps, state, "critics", deps.fast_model, res)
    out = parse_llm(res.get("content"), CriticReport)
    if out is None:
        return {"dimension": dimension, "verdict": "unverifiable", "confidence": 0.3}
    report = out.model_dump()
    report["dimension"] = dimension
    return report


async def critics(state: InterviewState, deps: InterviewDeps) -> dict:
    picked: list[str] = []
    for claim in state.get("claims", []):
        for name in CRITIC_ROUTE.get(claim.get("type", "opinion"), ["logic", "depth"]):
            if name not in picked:
                picked.append(name)
    sem = asyncio.Semaphore(deps.critic_concurrency)

    async def _gated(dimension: str) -> dict:
        async with sem:
            return await _run_critic(deps, state, dimension)

    reports = await asyncio.gather(*(_gated(n) for n in picked))
    return {"critic_reports": list(reports), **_bump(state, len(picked))}


async def judge(state: InterviewState, deps: InterviewDeps) -> dict:
    prior: dict = state.get("abilities", {})
    messages = [
        {"role": "system", "content": prompts.JUDGE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"评审结论：{json.dumps(state.get('critic_reports', []), ensure_ascii=False)}\n"
                f"现有画像：{json.dumps(prior, ensure_ascii=False)}"
            ),
        },
    ]
    res = await deps.llm.chat(messages, deps.fast_model, json_mode=True, max_tokens=2000)
    await _record(deps, state, "judge", deps.fast_model, res)
    out = parse_llm(res.get("content"), JudgeOutput)
    if out is None:
        return {"needs_probe": False, "candidates": [], "unverified": [], **_bump(state)}

    round_index = state.get("round_index", 0)
    seen: set[str] = set()
    abilities: dict[str, Any] = {}
    for item in out.abilities:
        dim = item.dimension
        if dim not in CRITIC_NAMES or item.level <= 0:
            continue
        seen.add(dim)
        abilities[dim] = merge_ability(
            prior.get(dim), item.level, item.confidence, item.evidence_refs, round_index + 1
        )
    abilities = decay_unseen(prior, seen) | abilities

    candidates = [c.model_dump() for c in out.candidates if c.dimension in CRITIC_NAMES]
    return {
        "abilities": abilities,
        "unverified": out.unverified,
        "needs_probe": out.needs_probe,
        "candidates": candidates,
        **_bump(state),
    }


async def select_weakness(state: InterviewState, deps: InterviewDeps) -> dict:
    candidates = state.get("candidates") or []
    history = state.get("probe_history") or []
    counts: dict[str, int] = {}
    for h in history:
        dim = h.get("dimension")
        if dim:
            counts[dim] = counts.get(dim, 0) + 1

    if not candidates:
        return {
            "selected_weakness": None,
            "probe_level": 1,
            "round_index": state.get("round_index", 0) + 1,
        }

    scored: list[tuple[float, str]] = []
    for c in candidates:
        dim = c.get("dimension", "")
        score = sum(deps.weights.get(k, 0.0) * int(c.get(k, 1) or 1) for k in deps.weights)
        if counts.get(dim, 0) >= deps.probe_max_per_weakness:
            score *= 0.3
        scored.append((score, dim))
    scored.sort(key=lambda x: -x[0])
    dim = scored[0][1]
    level = min(counts.get(dim, 0) + 1, 3)
    return {
        "selected_weakness": {"dimension": dim},
        "probe_level": level,
        "round_index": state.get("round_index", 0) + 1,
    }


async def generate_probe(state: InterviewState, deps: InterviewDeps) -> dict:
    if not (state.get("needs_probe") and state.get("selected_weakness")):
        return {}
    dim = state["selected_weakness"]["dimension"]
    level = state.get("probe_level", 1)
    messages = [
        {"role": "system", "content": prompts.PROBE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"薄弱点：{dim}；追问层级：{level}\n"
                f"能力画像：{json.dumps(state.get('abilities', {}), ensure_ascii=False)}\n"
                f"最近对话：{json.dumps(state.get('history', [])[-3:], ensure_ascii=False)}"
            ),
        },
    ]
    res = await deps.llm.chat(messages, deps.strong_model, max_tokens=500)
    await _record(deps, state, "generate_probe", deps.strong_model, res)
    entry = {"dimension": dim, "level": level, "asked_at_round": state.get("round_index", 0)}
    return {
        "probe_text": (res.get("content") or "").strip(),
        "probe_history": state.get("probe_history", []) + [entry],
        **_bump(state),
    }

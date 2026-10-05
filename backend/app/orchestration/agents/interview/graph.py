"""面试分析图装配：prepare → (opening? END : retrieve → decompose → critics → judge → probe)。"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from . import nodes
from .deps import InterviewDeps
from .state import InterviewState


def build_graph(deps: InterviewDeps, checkpointer: Any):
    g = StateGraph(InterviewState)

    async def prepare(s: InterviewState) -> dict:
        return await nodes.prepare(s, deps)

    async def retrieve(s: InterviewState) -> dict:
        return await nodes.retrieve(s, deps)

    async def decompose(s: InterviewState) -> dict:
        return await nodes.decompose(s, deps)

    async def critics(s: InterviewState) -> dict:
        return await nodes.critics(s, deps)

    async def judge(s: InterviewState) -> dict:
        return await nodes.judge(s, deps)

    async def select_weakness(s: InterviewState) -> dict:
        return await nodes.select_weakness(s, deps)

    async def generate_probe(s: InterviewState) -> dict:
        return await nodes.generate_probe(s, deps)

    g.add_node("prepare", prepare)
    g.add_node("retrieve", retrieve)
    g.add_node("decompose", decompose)
    g.add_node("critics", critics)
    g.add_node("judge", judge)
    g.add_node("select_weakness", select_weakness)
    g.add_node("generate_probe", generate_probe)

    g.add_edge(START, "prepare")

    def route(state: InterviewState) -> str:
        return "end" if state.get("opening") else "retrieve"

    g.add_conditional_edges("prepare", route, {"end": END, "retrieve": "retrieve"})
    g.add_edge("retrieve", "decompose")
    g.add_edge("decompose", "critics")
    g.add_edge("critics", "judge")
    g.add_edge("judge", "select_weakness")
    g.add_edge("select_weakness", "generate_probe")
    g.add_edge("generate_probe", END)

    return g.compile(checkpointer=checkpointer)

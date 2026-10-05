"""面试图状态：跨轮持久化到 LangGraph checkpoint（thread_id = session_id）。"""

from typing import TypedDict


class Ability(TypedDict):
    level: float
    confidence: float
    evidence_ids: list[str]
    updated_round: int


class InterviewState(TypedDict, total=False):
    user_id: str
    session_id: str
    mode: str
    text: str
    history: list[dict]
    personal_context: str
    opening: bool
    opening_text: str
    retrieved: list[dict]
    sources: list[dict]
    claims: list[dict]
    critic_reports: list[dict]
    abilities: dict[str, Ability]  # dimension -> Ability
    unverified: list[str]
    needs_probe: bool
    candidates: list[dict]
    selected_weakness: dict | None
    probe_level: int
    probe_text: str
    probe_history: list[dict]
    round_index: int
    llm_calls: int

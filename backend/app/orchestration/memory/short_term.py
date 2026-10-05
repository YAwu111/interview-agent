"""短期能力画像合并规则（纯函数，可单测）。"""

from app.orchestration.agents.interview.state import Ability


def merge_ability(
    prev: Ability | None,
    new_level: float,
    new_confidence: float,
    evidence_ids: list[str],
    round_index: int,
) -> Ability:
    """指数平滑合并；首轮（prev=None）直接建 baseline。"""
    if prev is None:
        return {
            "level": round(new_level, 2),
            "confidence": round(min(max(new_confidence, 0.0), 1.0), 3),
            "evidence_ids": list(dict.fromkeys(evidence_ids))[:5],
            "updated_round": round_index,
        }
    w = min(max(new_confidence, 0.2), 0.8)
    level = round(prev["level"] * (1 - w) + new_level * w, 2)
    confidence = round(min(max(0.5 * prev["confidence"] + 0.5 * new_confidence, 0.0), 1.0), 3)
    ids = list(dict.fromkeys(prev["evidence_ids"] + evidence_ids))[:5]
    return {
        "level": level,
        "confidence": confidence,
        "evidence_ids": ids,
        "updated_round": round_index,
    }


def decay_unseen(abilities: dict[str, Ability], seen: set[str]) -> dict[str, Ability]:
    """本轮未更新的维度置信度乘 0.9 时间衰减。"""
    out: dict[str, Ability] = {}
    for dim, a in abilities.items():
        if dim in seen:
            out[dim] = a
        else:
            out[dim] = {**a, "confidence": round(a["confidence"] * 0.9, 3)}
    return out

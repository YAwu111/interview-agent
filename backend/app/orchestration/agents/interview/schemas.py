"""LLM 结构化输出的 Pydantic 硬约束：字段白名单、类型校正、取值范围、非法值显式降级。"""

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _coerce_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def _coerce_int_1_5(v):
    try:
        return max(1, min(5, int(v)))
    except (TypeError, ValueError):
        return v


class Claim(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = ""
    type: str = "opinion"
    text: str = ""
    has_evidence: bool = False


class DecomposeOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    claims: list[Claim] = []


class CriticReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    dimension: str = ""
    verdict: Literal["strong", "partial", "missing", "unverifiable"] = "unverifiable"
    claims: list[str] = []
    gaps: list[str] = []
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_refs: list[str] = []

    _conf = field_validator("confidence", mode="before")(_coerce_float)


class JudgeAbility(BaseModel):
    model_config = ConfigDict(extra="ignore")
    dimension: str = ""
    level: float = Field(default=0.0, ge=0.0, le=5.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_refs: list[str] = []

    _level = field_validator("level", mode="before")(_coerce_float)
    _conf = field_validator("confidence", mode="before")(_coerce_float)


class Candidate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    dimension: str = ""
    severity: int = Field(default=1, ge=1, le=5)
    importance: int = Field(default=1, ge=1, le=5)
    uncertainty: int = Field(default=1, ge=1, le=5)
    relevance: int = Field(default=1, ge=1, le=5)
    probeability: int = Field(default=1, ge=1, le=5)

    _sev = field_validator(
        "severity",
        "importance",
        "uncertainty",
        "relevance",
        "probeability",
        mode="before",
    )(_coerce_int_1_5)


class JudgeOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    abilities: list[JudgeAbility] = []
    unverified: list[str] = []
    needs_probe: bool = False
    candidates: list[Candidate] = []


class ReportDimension(BaseModel):
    model_config = ConfigDict(extra="ignore")
    dimension: str = ""
    level: float = Field(default=0.0, ge=0.0, le=5.0)
    comment: str = ""

    _level = field_validator("level", mode="before")(_coerce_float)


class InterviewReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    overall: float = Field(default=0.0, ge=0.0, le=5.0)
    dimensions: list[ReportDimension] = []
    strengths: list[str] = []
    weaknesses: list[str] = []
    next_steps: list[str] = []
    end_reason: str = "user_end"

    _overall = field_validator("overall", mode="before")(_coerce_float)


def extract_json(content: str | None) -> dict | None:
    """从 LLM 文本里稳健提取 JSON：剥 code fence、取首尾大括号。"""
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def parse_llm(content: str | None, model_cls: type[BaseModel]):
    data = extract_json(content)
    if data is None:
        return None
    try:
        return model_cls.model_validate(data)
    except Exception:
        return None

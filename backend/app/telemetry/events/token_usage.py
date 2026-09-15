from datetime import datetime

from pydantic import BaseModel


class TokenUsageEvent(BaseModel):
    """单次 LLM 调用的 token 用量。llm/agent/tool 事件待 agent 层落地再加。"""

    user_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    timestamp: datetime

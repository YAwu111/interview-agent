"""模型档位映射：fast（决策/作答/critics）、strong（judge/probe/finalize）。均可被 .env 覆盖。"""

from app.core.config import settings


def fast_model() -> str:
    return settings.llm_model_fast


def strong_model() -> str:
    return settings.llm_model_strong or settings.llm_model_fast

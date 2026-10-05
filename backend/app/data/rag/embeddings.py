"""嵌入适配：进程内 sentence-transformers。模型首次在 asyncio.to_thread 里加载，多实例共享。"""

import asyncio
from typing import Any, Protocol

_MODELS: dict[str, Any] = {}


def _load_model(name: str):
    if name not in _MODELS:
        from sentence_transformers import SentenceTransformer  # 懒加载：torch 依赖重

        _MODELS[name] = SentenceTransformer(name)
    return _MODELS[name]


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class HFEmbedder:
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None

    async def _ensure_model(self):
        if self._model is None:
            self._model = await asyncio.to_thread(_load_model, self._model_name)
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = await self._ensure_model()
        vectors = await asyncio.to_thread(model.encode, texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

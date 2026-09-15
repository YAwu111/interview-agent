"""嵌入适配：进程内 sentence-transformers。重依赖懒加载，未安装时不影响模块编译。"""

import asyncio
from typing import Protocol


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class HFEmbedder:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # 懒加载：torch 依赖重

        self._model = SentenceTransformer(model_name)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = await asyncio.to_thread(self._model.encode, texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

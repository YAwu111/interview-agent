"""精排：进程内 cross-encoder（bge-reranker-v2-m3）。同步接口，调用方包 to_thread。"""

from typing import Protocol


class Reranker(Protocol):
    def rerank(self, query: str, texts: list[str]) -> list[tuple[int, float]]: ...


class HFReranker:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import CrossEncoder  # 懒加载

        self._model = CrossEncoder(model_name)

    def rerank(self, query: str, texts: list[str]) -> list[tuple[int, float]]:
        if not texts:
            return []
        scores = self._model.predict([(query, t) for t in texts])
        order = sorted(range(len(texts)), key=lambda i: scores[i], reverse=True)
        return [(i, float(scores[i])) for i in order]

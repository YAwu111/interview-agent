"""混合双路检索：dense + sparse → RRF → 精排 → top_k。融合为纯函数，可离线单测。"""

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from .embeddings import Embedder
from .rerank import Reranker


class Retriever(Protocol):
    async def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, str]]: ...


SparseSearch = Callable[[str, int], Awaitable[list[dict[str, Any]]]]
DenseSearch = Callable[[list[float], int], Awaitable[list[dict[str, Any]]]]


def rrf_rank(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    """Reciprocal Rank Fusion：score = Σ 1/(k + position)，position 从 1 起。"""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for pos, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + pos)
    return scores


class HybridRetriever:
    def __init__(
        self,
        embedder: Embedder,
        dense_search: DenseSearch,
        sparse_search: SparseSearch,
        reranker: Reranker | None = None,
        top_k: int = 6,
    ) -> None:
        self.embedder = embedder
        self.dense_search = dense_search
        self.sparse_search = sparse_search
        self.reranker = reranker
        self.top_k = top_k

    async def retrieve(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        limit = top_k or self.top_k
        vector = (await self.embedder.embed([query]))[0]
        dense, sparse = await self.dense_search(vector, 20), await self.sparse_search(query, 20)

        by_id: dict[str, dict[str, Any]] = {}
        for hit in [*dense, *sparse]:
            by_id.setdefault(hit["id"], hit)

        fused = rrf_rank([[h["id"] for h in dense], [h["id"] for h in sparse]])
        top10 = sorted(fused, key=fused.get, reverse=True)[:10]
        hits = [by_id[i] for i in top10]

        if self.reranker and len(hits) > 1:
            order = self.reranker.rerank(query, [h["text"] for h in hits])
            hits = [hits[i] for i, _ in order[:limit]]
        else:
            hits = hits[:limit]

        return [
            {
                "id": h["id"],
                "title": h.get("title", ""),
                "snippet": h["text"][:200],
                "base_name": h.get("base_name"),
                "score": h.get("score", 0.0),
            }
            for h in hits
        ]

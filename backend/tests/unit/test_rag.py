"""检索层纯逻辑单测：切分、RRF、混合检索编排（全部用假依赖，无模型/无库）。"""

import asyncio

from app.data.rag.chunking import SentenceChunker, split_sentences
from app.data.rag.retriever import HybridRetriever, rrf_rank


def test_split_sentences_keeps_delimiters() -> None:
    parts = split_sentences("第一句。第二句！第三句？")
    assert parts == ["第一句。", "第二句！", "第三句？"]


def test_chunker_respects_size_and_overlap() -> None:
    text = "。".join(f"句子{i}" for i in range(40)) + "。"
    chunks = SentenceChunker(chunk_size=80, overlap=16).chunk(text)
    assert len(chunks) > 1
    assert all(0 < len(c) <= 80 + 8 for c in chunks)  # 单句超长时允许略超


def test_rrf_ranks_overlap_higher() -> None:
    scores = rrf_rank([["a", "b"], ["a", "c"]], k=60)
    assert scores["a"] > scores["b"]
    assert scores["a"] > scores["c"]


class _FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]


class _FakeReranker:
    def rerank(self, query: str, texts: list[str]) -> list[tuple[int, float]]:
        assert len(texts) == 3
        # 把末尾的 s1 提到最前，验证精排确实改变了 RRF 顺序
        return [(1, 2.0), (0, 1.0), (2, 0.0)]


def test_hybrid_retriever_reranks_and_truncates() -> None:
    dense = [
        {"id": "d1", "text": "a" * 5, "title": "t1", "base_name": "b", "score": 0.9},
        {"id": "d2", "text": "b" * 5, "title": "t2", "base_name": "b", "score": 0.8},
    ]
    sparse = [{"id": "s1", "text": "c" * 5, "title": "t3", "base_name": "b", "score": 0.7}]

    async def dense_search(_v, _k):
        return dense

    async def sparse_search(_q, _k):
        return sparse

    retriever = HybridRetriever(
        _FakeEmbedder(), dense_search, sparse_search, _FakeReranker(), top_k=2
    )
    result = asyncio.run(retriever.retrieve("q"))

    assert len(result) == 2
    assert result[0]["id"] == "s1"  # 精排把 s1 放到最前
    assert all("title" in r and "snippet" in r for r in result)

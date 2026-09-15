"""检索 smoke：真 PG + jieba/tsvector + pgvector，嵌入用合成向量（不依赖模型下载）。"""

import asyncio
import random
import uuid

from sqlalchemy import delete, select

from app.data.db.models.knowledge import Chunk, Document, KnowledgeBase
from app.data.rag.retriever import HybridRetriever
from app.data.rag.vector_store import PgVectorStore
from tests.conftest import TestSession


def _vec(dim: int = 1024) -> list[float]:
    return [random.uniform(-1, 1) for _ in range(dim)]


class _FakeEmbedder:
    def __init__(self, vector: list[float]) -> None:
        self.vector = vector

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.vector for _ in texts]


def test_rag_roundtrip_smoke() -> None:
    async def run() -> None:
        async with TestSession() as s:
            doc_ids = select(Document.id).where(Document.name == "smoke.md")
            await s.execute(delete(Chunk).where(Chunk.document_id.in_(doc_ids)))
            await s.execute(delete(Document).where(Document.name == "smoke.md"))
            await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == "smoke"))
            await s.commit()

        async with TestSession() as s:
            base = KnowledgeBase(name="smoke")
            s.add(base)
            await s.flush()
            doc = Document(
                base_id=base.id,
                name="smoke.md",
                size=1,
                status="ready",
                content_hash=f"smoke-{uuid.uuid4().hex}",
            )
            s.add(doc)
            await s.flush()
            doc_id = doc.id
            await s.commit()

        chunks = [
            "前端面试中 React 的并发渲染和虚拟 DOM 有什么区别",
            "模拟面试应该准备自我介绍和行为面试题",
        ]
        vector = _vec()
        store = PgVectorStore(TestSession)
        await store.upsert(doc_id, chunks, [vector, _vec()])

        sparse = await store.search_sparse("React 并发渲染", top_k=2)
        dense = await store.search(vector, top_k=2)
        assert sparse and dense
        assert sparse[0]["title"] == "smoke.md"
        assert sparse[0]["base_name"] == "smoke"

        async def sparse_search(q: str, k: int):
            return await store.search_sparse(q, k)

        async def dense_search(v: list[float], k: int):
            return await store.search(v, k)

        hybrid = HybridRetriever(_FakeEmbedder(vector), dense_search, sparse_search, top_k=1)
        result = await hybrid.retrieve("React 并发渲染")
        assert len(result) == 1 and result[0]["title"] == "smoke.md"

        async with TestSession() as s:
            await s.execute(delete(Chunk))
            await s.execute(delete(Document))
            await s.execute(delete(KnowledgeBase))
            await s.commit()

    asyncio.run(run())

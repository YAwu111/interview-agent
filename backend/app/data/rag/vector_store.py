"""PG + pgvector 存取：稠密向量检索 + jieba/tsvector 稀疏检索。"""

from typing import Any, Protocol

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.data.db.models.knowledge import Chunk, Document, KnowledgeBase


class VectorStore(Protocol):
    async def upsert(self, doc_id: str, chunks: list[str], vectors: list[list[float]]) -> None: ...

    async def search(self, vector: list[float], top_k: int = 20) -> list[dict[str, Any]]: ...


class PgVectorStore:
    """document_id → chunks 增量 upsert；search/search_sparse 返回含 title/base_name 的命中。"""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def upsert(self, doc_id: str, chunks: list[str], vectors: list[list[float]]) -> None:
        import jieba  # 懒加载

        async with self._sessionmaker() as s:
            await s.execute(delete(Chunk).where(Chunk.document_id == doc_id))
            for seq, (text, vec) in enumerate(zip(chunks, vectors, strict=True)):
                tokens = " ".join(jieba.lcut(text))
                s.add(
                    Chunk(
                        document_id=doc_id,
                        seq=seq,
                        text=text,
                        embedding=vec,
                        tsv=func.to_tsvector("simple", tokens),
                    )
                )
            await s.commit()

    async def search(self, vector: list[float], top_k: int = 20) -> list[dict[str, Any]]:
        async with self._sessionmaker() as s:
            dist = Chunk.embedding.cosine_distance(vector)
            rows = (
                await s.execute(
                    select(Chunk.id, Chunk.text, Document.name, KnowledgeBase.name, dist)
                    .join(Document, Chunk.document_id == Document.id)
                    .join(KnowledgeBase, Document.base_id == KnowledgeBase.id)
                    .order_by(dist)
                    .limit(top_k)
                )
            ).all()
        return [
            {
                "id": r[0],
                "text": r[1],
                "title": r[2],
                "base_name": r[3],
                "score": round(1.0 - float(r[4]), 6),
            }
            for r in rows
        ]

    async def search_sparse(self, query: str, top_k: int = 20) -> list[dict[str, Any]]:
        import jieba  # 懒加载

        q = func.to_tsvector("simple", " ".join(jieba.lcut(query)))
        rank = func.ts_rank_cd(Chunk.tsv, q)
        async with self._sessionmaker() as s:
            rows = (
                await s.execute(
                    select(Chunk.id, Chunk.text, Document.name, KnowledgeBase.name, rank)
                    .join(Document, Chunk.document_id == Document.id)
                    .join(KnowledgeBase, Document.base_id == KnowledgeBase.id)
                    .where(Chunk.tsv.op("@@")(q))
                    .order_by(rank.desc())
                    .limit(top_k)
                )
            ).all()
        return [
            {
                "id": r[0],
                "text": r[1],
                "title": r[2],
                "base_name": r[3],
                "score": round(float(r[4]), 6),
            }
            for r in rows
        ]

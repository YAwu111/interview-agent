"""种子入库：txt/md → 切分 → 嵌入 → 写入 pgvector（一次性调试脚本）。"""

import asyncio
import hashlib
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.data.db.models.knowledge import Document, KnowledgeBase
from app.data.rag.chunking import SentenceChunker
from app.data.rag.embeddings import HFEmbedder
from app.data.rag.vector_store import PgVectorStore


async def main(text: str, path: str, base_name: str) -> None:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    async with sessionmaker() as s:
        existing = (
            await s.scalars(select(Document).where(Document.content_hash == content_hash))
        ).first()
        if existing is not None:
            await engine.dispose()
            print(f"已存在相同内容，跳过（{existing.name}）")
            return

        base = KnowledgeBase(name=base_name)
        s.add(base)
        await s.flush()
        doc = Document(
            base_id=base.id,
            name=path,
            size=len(text.encode("utf-8")),
            status="indexing",
            content_hash=content_hash,
        )
        s.add(doc)
        await s.flush()
        doc_id = doc.id
        await s.commit()

    try:
        chunks = SentenceChunker(settings.chunk_size, settings.chunk_overlap).chunk(text)
        vectors = await HFEmbedder(settings.embedding_model).embed(chunks)
        await PgVectorStore(sessionmaker).upsert(doc_id, chunks, vectors)
    except Exception:
        async with sessionmaker() as s:
            row = await s.get(Document, doc_id)
            if row is not None:
                row.status = "failed"
                await s.commit()
        await engine.dispose()
        raise

    async with sessionmaker() as s:
        row = await s.get(Document, doc_id)
        if row is not None:
            row.status = "ready"
            await s.commit()
    await engine.dispose()
    print(f"seeded {len(chunks)} chunks from {path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python scripts/seed_knowledge.py <file> [base_name]")
    text = open(sys.argv[1], encoding="utf-8").read()
    asyncio.run(main(text, sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "默认知识库"))

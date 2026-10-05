"""生产装配：懒构建 llm/retriever/deps 与 runner；测试可注入 fake deps。"""

from app.core.config import settings
from app.core.llm import DeepSeekClient, fast_model, strong_model
from app.data.rag.embeddings import HFEmbedder
from app.data.rag.retriever import HybridRetriever
from app.data.rag.vector_store import PgVectorStore

from .deps import InterviewDeps
from .runner import InterviewRunner


def _strip_driver(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


def build_deps(sessionmaker, usage_sink=None) -> InterviewDeps:
    store = PgVectorStore(sessionmaker)
    embedder = HFEmbedder(settings.embedding_model)
    retriever = HybridRetriever(
        embedder, store.search, store.search_sparse, None, settings.retrieve_top_k
    )
    llm = DeepSeekClient(settings.deepseek_base_url, settings.deepseek_api_key)
    return InterviewDeps(
        llm=llm,
        retriever=retriever,
        fast_model=fast_model(),
        strong_model=strong_model(),
        usage_sink=usage_sink,
        round_limit=settings.round_limit,
        llm_call_budget=settings.llm_call_budget,
        probe_max_per_weakness=settings.probe_max_per_weakness,
        retrieve_top_k=settings.retrieve_top_k,
    )


def build_interview_runner(sessionmaker, usage_sink=None, db_url: str | None = None):
    if db_url is None:
        db_url = _strip_driver(settings.database_url)
    return InterviewRunner(sessionmaker=sessionmaker, usage_sink=usage_sink, db_url=db_url)

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://interview:interview@localhost:5432/interview"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev-secret-change-me-please-32bytes"  # HS256 要求 ≥32 字节，生产必须覆盖
    jwt_algorithm: str = "HS256"
    jwt_expire_access_minutes: int = 30
    jwt_expire_refresh_days: int = 7

    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""

    frontend_url: str = "http://localhost:5173"
    backend_base_url: str = "http://localhost:8000"
    code_ttl_seconds: int = 600

    cors_origins: list[str] = ["http://localhost:5173"]

    # LLM / RAG / agent（编排层与检索层专用）
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_api_key: str = ""
    llm_model_fast: str = "deepseek-chat"
    llm_model_strong: str = ""  # V4 级 model id，实施时填入
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "interview-agent"
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    embedding_dim: int = 1024
    chunk_size: int = 480
    chunk_overlap: int = 64
    retrieve_top_k: int = 6
    round_limit: int = 10
    probe_max_per_weakness: int = 2
    llm_call_budget: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

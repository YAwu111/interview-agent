from functools import lru_cache

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()  # 把 .env 注入 os.environ，供 huggingface_hub / langsmith 等第三方库读取

_WEAK_JWT_SECRETS = {
    "dev-secret-change-me",
    "dev-secret-change-me-please-32bytes",
    "changeme",
    "secret",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://interview:interview@localhost:5432/interview"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str  # 必填：缺失即启动失败，杜绝硬编码默认值
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
    llm_model_strong: str = ""  # 为空时回退 llm_model_fast；deepseek-v4-pro 经 .env 覆盖
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

    @field_validator("jwt_secret")
    @classmethod
    def _check_jwt_secret(cls, value: str) -> str:
        if len(value) < 32 or value in _WEAK_JWT_SECRETS:
            raise ValueError("JWT_SECRET 必须 ≥32 字节，且不能使用公开的默认弱值")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

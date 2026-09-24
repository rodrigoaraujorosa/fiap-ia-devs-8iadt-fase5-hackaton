from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_name: str = "SDR Imobiliário API"
    environment: str = "local"

    database_url: str = "postgresql+psycopg://sdr:sdr@127.0.0.1:5432/sdr"

    # Embeddings (RAG) — modelo local multilíngue, 384 dimensões
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384
    embedding_cache_dir: str | None = None

    # LLMs (usados a partir do Dia 2)
    anthropic_api_key: str | None = None
    llm_main_model: str = "claude-sonnet-5"
    llm_fast_model: str = "claude-haiku-4-5-20251001"

    # Follow-up
    followup_minutes: int = 2
    followup_max_attempts: int = 3

    cors_origins: list[str] = ["http://localhost:3001", "http://127.0.0.1:3001"]


@lru_cache
def get_settings() -> Settings:
    return Settings()

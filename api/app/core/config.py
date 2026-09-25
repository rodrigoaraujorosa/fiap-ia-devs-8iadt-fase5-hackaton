from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
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
    llm_fast_model: str = "claude-haiku-4-5"
    llm_agent_effort: str = "low"  # conversa curta e rápida; suba para "medium" se a qualidade pedir
    llm_agent_max_tokens: int = 16000

    # Base simulada (JSON). Local: <repo>/data | Docker: /data (volume montado)
    data_dir: Path = Path(__file__).resolve().parents[3] / "data"

    # Follow-up automático: 1ª tentativa após N minutos sem resposta, depois 2N, 4N... (cadência crescente).
    # Valores padrão: a tela /configuration pode sobrescrevê-los em tempo real (tabela app_settings).
    followup_enabled: bool = True
    followup_minutes: int = 2
    followup_max_attempts: int = 3
    followup_check_seconds: int = 30

    # Agenda
    timezone: str = "America/Sao_Paulo"
    slot_days_ahead: int = 10

    # Observabilidade (Langfuse) — vazio = desabilitado
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str = Field(
        "https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_BASE_URL", "LANGFUSE_HOST"),  # LANGFUSE_HOST: nome antigo
    )

    cors_origins: list[str] = ["http://localhost:3001", "http://127.0.0.1:3001"]

    @property
    def checkpoint_db_url(self) -> str:
        """URL no formato psycopg puro, exigido pelo checkpointer do LangGraph."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://")


@lru_cache
def get_settings() -> Settings:
    return Settings()

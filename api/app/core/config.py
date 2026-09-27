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

    # E-mail aos corretores (resumo + convite de calendário). Padrão: Mailpit local (nada sai de verdade).
    # Produção: SMTP da Hostinger (smtp.hostinger.com, porta 465, SMTP_SSL=true, usuário/senha da caixa remetente).
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_ssl: bool = False  # TLS implícito (porta 465)
    smtp_starttls: bool = False  # STARTTLS (porta 587)
    email_from: str = "Laris · ImobiQ <laris@arrtsoftware.com.br>"
    # Valores iniciais: a tela /configuration altera em tempo real
    email_enabled: bool = True
    email_demo_mode: bool = True  # entrega tudo na caixa de demonstração
    email_demo_recipient: str = "corretor@arrtsoftware.com.br"
    public_app_url: str = "http://localhost:3001"  # links "Abrir no dashboard" nos e-mails

    # Telegram (bot criado no @BotFather). Sem token, a integração fica desligada.
    # polling: a API busca as mensagens no Telegram (local, sem URL pública); webhook: o Telegram chama
    # POST /webhooks/telegram (produção, exige TELEGRAM_WEBHOOK_URL pública com HTTPS).
    telegram_bot_token: str | None = None
    telegram_mode: str = "polling"  # polling | webhook
    telegram_webhook_url: str | None = None  # ex.: https://imobiq.arrtsoftware.com.br/api/webhooks/telegram
    telegram_webhook_secret: str | None = None  # conferido no cabeçalho X-Telegram-Bot-Api-Secret-Token
    telegram_brand: str = "Imobiliária Exemplo"  # em nome de quem a Laris atende no Telegram
    public_site_url: str = "http://localhost:5500"  # site da imobiliária: links "ver no site" dos imóveis

    # Senha da área de administração (configurações, reset da demo). Vazia = sem senha (uso local).
    admin_password: str | None = None

    # Limite de mensagens (valores iniciais: a tela /configuration altera em tempo real)
    rate_limit_enabled: bool = True
    rate_limit_conversation_hour: int = 40  # mensagens de uma conversa por hora
    rate_limit_ip_hour: int = 80  # mensagens de um mesmo IP por hora (várias conversas somadas)
    rate_limit_sessions_ip_hour: int = 10  # conversas novas por IP por hora
    rate_limit_daily_total: int = 1500  # teto de mensagens por dia no total (trava de custo)
    # Atrás de um proxy reverso (Caddy na AWS), o IP do visitante vem no X-Forwarded-For
    trust_proxy_headers: bool = False

    # Domínios que podem embutir o widget (valores iniciais: a tela /configuration altera em tempo real)
    widget_restrict_domains: bool = False
    widget_allowed_domains: list[str] = ["localhost:5500", "127.0.0.1:5500"]

    # Agenda
    timezone: str = "America/Sao_Paulo"
    slot_days_ahead: int = 10

    # Painel de observabilidade: o Langfuse registra custos em dólar; conversão aproximada para real
    usd_brl: float = 5.40

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

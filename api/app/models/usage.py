import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UsageEvent(Base):
    """Uso da IA registrado pelo próprio app: é a fonte do painel de observabilidade.

    kind: "llm" (uma chamada ao Claude), "tool" (ferramenta de um agente), "trace" (fluxo inteiro: turno,
    follow-up, resumo) ou "guardrail" (suspeita de prompt injection).
    """

    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(12))
    name: Mapped[str] = mapped_column(String(60))  # agente, ferramenta ou fluxo
    model: Mapped[str | None] = mapped_column(String(60))
    # sem chave estrangeira de propósito: o reset da demo (TRUNCATE leads ... CASCADE) apagaria o histórico de custo
    lead_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)  # entrada fora do cache
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EmailLog(Base):
    """Histórico de e-mails aos corretores (enviado, erro ou ignorado), exibido no detalhe do lead."""

    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    summary_id: Mapped[int | None] = mapped_column(ForeignKey("summaries.id", ondelete="SET NULL"))
    broker_id: Mapped[int | None] = mapped_column(ForeignKey("brokers.id"))
    trigger: Mapped[str] = mapped_column(String(20))  # agendamento | encaminhamento | manual
    recipient: Mapped[str | None] = mapped_column(String(160))  # para quem saiu de fato
    intended_recipient: Mapped[str | None] = mapped_column(String(160))  # e-mail do corretor
    demo_mode: Mapped[bool] = mapped_column(default=False)
    subject: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20))  # enviado | erro | ignorado
    detail: Mapped[str | None] = mapped_column(Text)  # motivo do erro/ignorado
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

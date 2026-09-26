import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import Channel, Intent, LeadStatus, MessageRole, Temperature


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(30), index=True)  # a mesma pessoa pode ter várias conversas
    email: Mapped[str | None] = mapped_column(String(160))
    channel: Mapped[str] = mapped_column(String(20), default=Channel.WEB)

    # Qualificação (preenchida pelo agente extrator)
    segment: Mapped[str] = mapped_column(String(20), default="indefinido")  # comercial | residencial
    company: Mapped[str | None] = mapped_column(String(160))  # B2B: empresa do lead
    job_title: Mapped[str | None] = mapped_column(String(80))  # cargo/papel (sócio, gerente de facilities...)
    decision_maker: Mapped[str | None] = mapped_column(String(20))  # sim | compartilhada | nao
    business_activity: Mapped[str | None] = mapped_column(String(120))  # clínica, escritório, restaurante...
    area_min: Mapped[int | None] = mapped_column(Integer)  # m²
    area_max: Mapped[int | None] = mapped_column(Integer)
    headcount: Mapped[int | None] = mapped_column(Integer)  # nº de pessoas/postos de trabalho
    requirements: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)  # vagas, docas, fachada...
    intent: Mapped[str] = mapped_column(String(20), default=Intent.INDEFINIDO, index=True)
    property_type: Mapped[str | None] = mapped_column(String(40))
    budget_min: Mapped[int | None] = mapped_column(Integer)
    budget_max: Mapped[int | None] = mapped_column(Integer)
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    regions: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    urgency: Mapped[str | None] = mapped_column(String(10))
    timeline: Mapped[str | None] = mapped_column(String(120))
    financing: Mapped[str | None] = mapped_column(String(60))
    investor_profile: Mapped[str | None] = mapped_column(String(120))
    ticket: Mapped[int | None] = mapped_column(Integer)
    expected_return: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Funil
    score: Mapped[int] = mapped_column(Integer, default=0)
    temperature: Mapped[str] = mapped_column(String(10), default=Temperature.FRIO, index=True)
    status: Mapped[str] = mapped_column(String(20), default=LeadStatus.NOVO, index=True)
    assigned_broker_id: Mapped[int | None] = mapped_column(ForeignKey("brokers.id"))

    # Follow-up
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_lead_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    followup_count: Mapped[int] = mapped_column(Integer, default=0)
    next_followup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="lead",
        order_by="Message.id",
        cascade="all, delete-orphan",  # id: imune a ajustes de relógio
    )
    assigned_broker: Mapped["Broker | None"] = relationship()  # noqa: F821


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default=MessageRole.USER)
    content: Mapped[str] = mapped_column(Text)
    agent: Mapped[str | None] = mapped_column(String(40))  # qual agente respondeu
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lead: Mapped[Lead] = relationship(back_populates="messages")


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    content: Mapped[dict] = mapped_column(JSONB)  # resumo estruturado
    text: Mapped[str] = mapped_column(Text)  # versão legível para o corretor
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import AppointmentKind, AppointmentStatus, BrokerRole


class Broker(Base):
    __tablename__ = "brokers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(30))
    role: Mapped[str] = mapped_column(String(40), default=BrokerRole.CORRETOR)
    zones: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    bio: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    slots: Mapped[list["Slot"]] = relationship(back_populates="broker", cascade="all, delete-orphan")


class Slot(Base):
    __tablename__ = "slots"
    __table_args__ = (UniqueConstraint("broker_id", "start_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broker_id: Mapped[int] = mapped_column(ForeignKey("brokers.id", ondelete="CASCADE"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_booked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    broker: Mapped[Broker] = relationship(back_populates="slots")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    broker_id: Mapped[int] = mapped_column(ForeignKey("brokers.id"), index=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"), unique=True)
    property_id: Mapped[str | None] = mapped_column(ForeignKey("properties.id"))
    kind: Mapped[str] = mapped_column(String(20), default=AppointmentKind.VISITA)
    status: Mapped[str] = mapped_column(String(20), default=AppointmentStatus.AGENDADO)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    broker: Mapped[Broker] = relationship()
    slot: Mapped[Slot] = relationship()

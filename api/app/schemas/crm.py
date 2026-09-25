import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.lead import LeadOut, MessageOut


class BrokerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: str
    role: str
    zones: list[str]
    bio: str | None


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID
    lead_name: str | None = None
    kind: str
    status: str
    property_id: str | None
    notes: str | None
    start_at: datetime
    broker: BrokerOut
    created_at: datetime


class SummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: dict
    text: str
    created_at: datetime


class LeadDetail(LeadOut):
    assigned_broker: BrokerOut | None = None
    summary: SummaryOut | None = None
    appointments: list[AppointmentOut] = []
    messages: list[MessageOut] = []

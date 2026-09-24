import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeadCreate(BaseModel):
    name: str | None = Field(None, max_length=120)
    phone: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=160)


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    phone: str | None
    email: str | None
    channel: str
    intent: str
    property_type: str | None
    budget_min: int | None
    budget_max: int | None
    bedrooms: int | None
    regions: list[str]
    urgency: str | None
    timeline: str | None
    financing: str | None
    investor_profile: str | None
    ticket: int | None
    expected_return: str | None
    extra: dict
    score: int
    temperature: str
    status: str
    followup_count: int
    last_message_at: datetime | None
    next_followup_at: datetime | None
    created_at: datetime


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    agent: str | None
    meta: dict
    created_at: datetime

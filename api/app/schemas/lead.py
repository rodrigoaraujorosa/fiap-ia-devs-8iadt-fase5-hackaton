import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

PROPERTY_CODE = r"^IMV-\d{3}$"


class LeadSource(BaseModel):
    """Origem do lead que chega pelo widget (site da imobiliária). Tudo opcional e com tamanho limitado."""

    brand: str | None = Field(None, max_length=80, description="Imobiliária dona do site onde o widget está")
    page_url: str | None = Field(None, max_length=500)
    page_title: str | None = Field(None, max_length=200)
    referrer: str | None = Field(None, max_length=500)
    utm_source: str | None = Field(None, max_length=80)
    utm_medium: str | None = Field(None, max_length=80)
    utm_campaign: str | None = Field(None, max_length=120)
    property_id: str | None = Field(None, pattern=PROPERTY_CODE, description="Imóvel da página de entrada")


class PageContext(BaseModel):
    """Onde o visitante está agora (enviado a cada mensagem pelo widget)."""

    page_url: str | None = Field(None, max_length=500)
    property_id: str | None = Field(None, pattern=PROPERTY_CODE)


class LeadCreate(BaseModel):
    name: str | None = Field(None, max_length=120)
    phone: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=160)
    source: LeadSource | None = None


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    phone: str | None
    email: str | None
    channel: str
    segment: str
    company: str | None
    job_title: str | None
    decision_maker: str | None
    business_activity: str | None
    area_min: int | None
    area_max: int | None
    headcount: int | None
    requirements: list[str]
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
    context: PageContext | None = None


class ContactIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=8, max_length=30)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    agent: str | None
    meta: dict
    created_at: datetime

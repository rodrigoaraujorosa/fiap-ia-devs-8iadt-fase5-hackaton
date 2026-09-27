"""Configurações editáveis em tempo real (tela /configuration).

O .env define os padrões; o que for salvo na tabela app_settings sobrescreve, sem reiniciar a API.
Os jobs leem a configuração a cada ciclo, então a mudança vale na próxima rodada (até 30s).
"""

import logging
import re
from datetime import datetime, time
from zoneinfo import ZoneInfo

from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AppSetting

log = logging.getLogger(__name__)

HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class FollowupConfig(BaseModel):
    enabled: bool = Field(description="Liga/desliga o envio automático de follow-ups")
    minutes: int = Field(ge=1, le=1440, description="Minutos sem resposta até a 1ª tentativa (depois 2x, 4x...)")
    max_attempts: int = Field(ge=1, le=5, description="Tentativas antes de marcar o lead como perdido")
    quiet_hours: bool = Field(False, description="Não enviar follow-ups no horário de silêncio")
    quiet_start: str = Field("21:00", pattern=HHMM)
    quiet_end: str = Field("08:00", pattern=HHMM)

    def in_quiet_hours(self, now: datetime | None = None) -> bool:
        if not self.quiet_hours:
            return False
        tz = ZoneInfo(get_settings().timezone)
        now_t = (now or datetime.now(tz)).astimezone(tz).time()
        start, end = time.fromisoformat(self.quiet_start), time.fromisoformat(self.quiet_end)
        if start <= end:
            return start <= now_t < end
        return now_t >= start or now_t < end  # janela que atravessa a meia-noite (ex.: 21:00 → 08:00)


class EmailConfig(BaseModel):
    enabled: bool = Field(description="Envia o resumo ao corretor ao agendar ou encaminhar um lead")
    demo_mode: bool = Field(description="Entrega todos os e-mails na caixa de demonstração")
    demo_recipient: EmailStr = Field(description="Caixa que recebe os e-mails no modo demonstração")


class AIConfig(BaseModel):
    enabled: bool = Field(description="Liga/desliga o uso das LLMs (conversa, follow-up e resumos)")


class RateLimitConfig(BaseModel):
    enabled: bool = Field(description="Liga/desliga os limites de mensagens")
    conversation_hour: int = Field(ge=5, le=500, description="Mensagens de uma conversa por hora")
    ip_hour: int = Field(ge=5, le=2000, description="Mensagens de um mesmo IP por hora")
    sessions_ip_hour: int = Field(ge=1, le=500, description="Conversas novas por IP por hora")
    daily_total: int = Field(ge=10, le=100000, description="Mensagens por dia no total; acima disso, sem IA")


DOMAIN = re.compile(r"^(\*\.)?[a-z0-9-]+(\.[a-z0-9-]+)*(:\d{1,5})?$")


def normalize_domain(raw: str) -> str:
    """'https://www.site.com.br/imoveis' -> 'www.site.com.br' (mantém porta e curinga *.site.com.br)."""
    value = raw.strip().lower()
    value = re.sub(r"^[a-z]+://", "", value).split("/")[0].split("?")[0]
    return value


class WidgetConfig(BaseModel):
    restrict: bool = Field(description="Só permite o widget nos domínios da lista")
    allowed_domains: list[str] = Field(max_length=30, description="Domínios (com porta, se houver; *.dominio vale)")

    @field_validator("allowed_domains")
    @classmethod
    def _domains(cls, value: list[str]) -> list[str]:
        domains = []
        for raw in value:
            domain = normalize_domain(raw)
            if not domain:
                continue
            if not DOMAIN.match(domain):
                raise ValueError(f"domínio inválido: {raw}")
            if domain not in domains:
                domains.append(domain)
        return domains

    def allows(self, host: str | None) -> bool:
        """host = 'site.com.br' ou 'localhost:5500' (do Origin ou da URL da página)."""
        if not self.restrict:
            return True
        host = (host or "").lower()
        for domain in self.allowed_domains:
            if domain.startswith("*.") and (host.endswith(domain[1:]) or host == domain[2:]):
                return True
            if host == domain:
                return True
        return False


class TelegramConfig(BaseModel):
    enabled: bool = Field(description="Liga/desliga o atendimento da Laris pelo bot do Telegram")


def followup_defaults() -> FollowupConfig:
    s = get_settings()
    return FollowupConfig(enabled=s.followup_enabled, minutes=s.followup_minutes, max_attempts=s.followup_max_attempts)


def email_defaults() -> EmailConfig:
    s = get_settings()
    return EmailConfig(enabled=s.email_enabled, demo_mode=s.email_demo_mode, demo_recipient=s.email_demo_recipient)


def _load[T: BaseModel](db: Session | None, key: str, defaults: T) -> T:
    if db is None:
        with SessionLocal() as session:
            return _load(session, key, defaults)
    row = db.get(AppSetting, key)
    if row is None:
        return defaults
    try:
        return type(defaults).model_validate({**defaults.model_dump(), **row.value})
    except ValidationError:
        log.warning("Configuração %r inválida no banco; usando os padrões do .env", key)
        return defaults


def _save[T: BaseModel](db: Session, key: str, config: T) -> T:
    row = db.get(AppSetting, key) or AppSetting(key=key)
    row.value = config.model_dump()
    db.add(row)
    db.commit()
    log.info("Configuração %r atualizada: %s", key, row.value)
    return config


def get_followup_config(db: Session | None = None) -> FollowupConfig:
    return _load(db, "followup", followup_defaults())


def save_followup_config(db: Session, config: FollowupConfig) -> FollowupConfig:
    return _save(db, "followup", config)


def get_ai_config(db: Session | None = None) -> AIConfig:
    return _load(db, "ai", AIConfig(enabled=True))


def ai_enabled() -> bool:
    return get_ai_config().enabled


def save_ai_config(db: Session, config: AIConfig) -> AIConfig:
    return _save(db, "ai", config)


def get_rate_limit_config(db: Session | None = None) -> RateLimitConfig:
    s = get_settings()
    defaults = RateLimitConfig(
        enabled=s.rate_limit_enabled,
        conversation_hour=s.rate_limit_conversation_hour,
        ip_hour=s.rate_limit_ip_hour,
        sessions_ip_hour=s.rate_limit_sessions_ip_hour,
        daily_total=s.rate_limit_daily_total,
    )
    return _load(db, "rate_limit", defaults)


def save_rate_limit_config(db: Session, config: RateLimitConfig) -> RateLimitConfig:
    return _save(db, "rate_limit", config)


def get_widget_config(db: Session | None = None) -> WidgetConfig:
    s = get_settings()
    return _load(
        db, "widget", WidgetConfig(restrict=s.widget_restrict_domains, allowed_domains=s.widget_allowed_domains)
    )


def save_widget_config(db: Session, config: WidgetConfig) -> WidgetConfig:
    return _save(db, "widget", config)


def get_telegram_config(db: Session | None = None) -> TelegramConfig:
    return _load(db, "telegram", TelegramConfig(enabled=True))


def save_telegram_config(db: Session, config: TelegramConfig) -> TelegramConfig:
    return _save(db, "telegram", config)


def get_email_config(db: Session | None = None) -> EmailConfig:
    return _load(db, "email", email_defaults())


def save_email_config(db: Session, config: EmailConfig) -> EmailConfig:
    return _save(db, "email", config)

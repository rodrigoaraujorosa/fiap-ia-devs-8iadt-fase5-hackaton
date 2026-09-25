"""Configurações editáveis em tempo real (tela /configuration).

O .env define os padrões; o que for salvo na tabela app_settings sobrescreve, sem reiniciar a API.
Os jobs leem a configuração a cada ciclo, então a mudança vale na próxima rodada (até 30s).
"""

import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from pydantic import BaseModel, EmailStr, Field, ValidationError
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


def get_email_config(db: Session | None = None) -> EmailConfig:
    return _load(db, "email", email_defaults())


def save_email_config(db: Session, config: EmailConfig) -> EmailConfig:
    return _save(db, "email", config)

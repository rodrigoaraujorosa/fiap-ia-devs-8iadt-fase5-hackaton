"""Configurações editáveis em tempo real (tela /configuration).

O .env define os padrões; o que for salvo na tabela app_settings sobrescreve, sem reiniciar a API.
Os jobs leem a configuração a cada ciclo, então a mudança vale na próxima rodada (até 30s).
"""

import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, ValidationError
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


def followup_defaults() -> FollowupConfig:
    s = get_settings()
    return FollowupConfig(enabled=s.followup_enabled, minutes=s.followup_minutes, max_attempts=s.followup_max_attempts)


def get_followup_config(db: Session | None = None) -> FollowupConfig:
    if db is None:
        with SessionLocal() as session:
            return get_followup_config(session)
    row = db.get(AppSetting, "followup")
    if row is None:
        return followup_defaults()
    try:
        return FollowupConfig.model_validate({**followup_defaults().model_dump(), **row.value})
    except ValidationError:
        log.warning("Configuração de follow-up inválida no banco; usando os padrões do .env")
        return followup_defaults()


def save_followup_config(db: Session, config: FollowupConfig) -> FollowupConfig:
    row = db.get(AppSetting, "followup") or AppSetting(key="followup")
    row.value = config.model_dump()
    db.add(row)
    db.commit()
    log.info("Configuração de follow-up atualizada: %s", row.value)
    return config

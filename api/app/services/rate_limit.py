"""Limites de uso do chat (tela /configuration), para o site público não virar uma fonte de gasto com a IA.

- Por conversa e teto diário: contados no banco (mensagens do cliente), valem para o chat, o widget e o Telegram.
- Por IP (mensagens e conversas novas): janela deslizante em memória. Suficiente para uma instância; com várias,
  o próximo passo seria guardar os contadores no Redis.
- Teto diário atingido: a Laris passa a responder como com a IA pausada (recado + formulário de contato).
"""

import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Message
from app.models.enums import MessageRole
from app.services.app_config import ai_enabled, get_rate_limit_config

WINDOW = 3600  # segundos
TOO_FAST = "Você enviou muitas mensagens em pouco tempo 😅 Espere alguns minutos e a gente continua de onde parou."
TOO_MANY_SESSIONS = "Muitas conversas novas a partir da sua conexão. Tente de novo mais tarde."

_hits: defaultdict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str | None:
    """IP do visitante. Atrás do Caddy, o último item do X-Forwarded-For é o que o próprio proxy viu."""
    if get_settings().trust_proxy_headers and (forwarded := request.headers.get("x-forwarded-for")):
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else None


def _take(key: str, limit: int) -> bool:
    """Registra uma ocorrência se ainda couber no limite da última hora."""
    now = time.monotonic()
    with _lock:
        hits = _hits[key]
        while hits and hits[0] <= now - WINDOW:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True


def allow(key: str, limit: int) -> bool:
    """Limite genérico por hora (tentativas de login, pedidos de redefinição de senha...)."""
    return _take(key, limit)


def forget(key: str) -> None:
    with _lock:
        _hits.pop(key, None)


def reset() -> None:
    with _lock:
        _hits.clear()


def _user_messages_since(db: Session, since: datetime, lead_id: uuid.UUID | None = None) -> int:
    stmt = (
        select(func.count()).select_from(Message).where(Message.role == MessageRole.USER, Message.created_at >= since)
    )
    if lead_id:
        stmt = stmt.where(Message.lead_id == lead_id)
    return db.scalar(stmt) or 0


def daily_cap_reached(db: Session | None = None) -> bool:
    if db is None:
        with SessionLocal() as session:
            return daily_cap_reached(session)
    cfg = get_rate_limit_config(db)
    if not cfg.enabled:
        return False
    return _user_messages_since(db, datetime.now(UTC) - timedelta(days=1)) >= cfg.daily_total


def ai_available() -> bool:
    """A Laris pode usar a IA agora? (ligada nas configurações e abaixo do teto diário)"""
    return ai_enabled() and not daily_cap_reached()


def check_message(db: Session, lead_id: uuid.UUID, ip: str | None = None) -> str | None:
    """None se a mensagem pode seguir; senão, o aviso para o visitante."""
    cfg = get_rate_limit_config(db)
    if not cfg.enabled:
        return None
    if _user_messages_since(db, datetime.now(UTC) - timedelta(seconds=WINDOW), lead_id) >= cfg.conversation_hour:
        return TOO_FAST
    if ip and not _take(f"msg:{ip}", cfg.ip_hour):
        return TOO_FAST
    return None


def check_new_session(db: Session, ip: str | None) -> str | None:
    cfg = get_rate_limit_config(db)
    if not cfg.enabled or not ip:
        return None
    return None if _take(f"session:{ip}", cfg.sessions_ip_hour) else TOO_MANY_SESSIONS

import secrets
import uuid

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import get_settings
from app.services import telegram

router = APIRouter(tags=["telegram"])


@router.post("/webhooks/telegram", include_in_schema=False)
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(None)):
    """Recebe os updates do Telegram em produção (modo webhook). O segredo vem no cabeçalho, definido no setWebhook."""
    s = get_settings()
    if s.telegram_mode != "webhook" or not telegram.configured() or not s.telegram_webhook_secret:
        raise HTTPException(404)
    if not secrets.compare_digest(x_telegram_bot_api_secret_token or "", s.telegram_webhook_secret):
        raise HTTPException(401)
    telegram.submit(await request.json())  # responde na hora; o turno roda em segundo plano
    return {"ok": True}


@router.get("/chat/telegram")
def telegram_availability():
    """Para o widget: o bot está disponível? (mostra o botão "Continuar no Telegram")."""
    info = telegram.bot_info()
    return {"available": telegram.available(), "username": info["username"], "link": info["link"]}


@router.post("/chat/{lead_id}/telegram-link")
def telegram_link(lead_id: uuid.UUID):
    """Link t.me que continua esta conversa no Telegram (mesmo lead, mesma memória)."""
    url = telegram.link_url(lead_id)
    if url is None:
        raise HTTPException(503, "Telegram indisponível")
    return {"url": url}

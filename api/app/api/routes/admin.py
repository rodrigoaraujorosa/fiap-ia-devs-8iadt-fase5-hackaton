import smtplib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.db.session import get_db
from app.jobs.followup import run_followups
from app.services import exchange, telegram
from app.services.app_config import (
    AIConfig,
    EmailConfig,
    ExchangeConfig,
    FollowupConfig,
    RateLimitConfig,
    TelegramConfig,
    WidgetConfig,
    get_ai_config,
    get_email_config,
    get_exchange_config,
    get_followup_config,
    get_rate_limit_config,
    get_telegram_config,
    get_widget_config,
    save_ai_config,
    save_email_config,
    save_exchange_config,
    save_followup_config,
    save_rate_limit_config,
    save_telegram_config,
    save_widget_config,
)
from app.services.demo import reset_demo
from app.services.mailer import send_test_email, smtp_info

router = APIRouter(tags=["configuração"], dependencies=[Depends(require_admin)])


class SmtpInfo(BaseModel):
    host: str
    port: int
    security: str
    authenticated: bool
    sender: str
    local_test_inbox: bool


class EmailConfigOut(EmailConfig):
    smtp: SmtpInfo


class TelegramConfigOut(TelegramConfig):
    configured: bool  # há token no .env
    mode: str  # polling | webhook
    status: str  # conectado, conectando, erro: ...
    username: str | None
    name: str | None
    link: str | None


class ExchangeQuote(BaseModel):
    rate: float
    source: str  # ptax | config
    date: str | None


class ExchangeConfigOut(ExchangeConfig):
    current: ExchangeQuote  # cotação em uso agora no painel de observabilidade


@router.get("/config/exchange", response_model=ExchangeConfigOut)
def read_exchange_config(db: Session = Depends(get_db)):
    """Cotação do dólar do painel de observabilidade: busca no Banco Central ligada/desligada e cotação fixa."""
    return {**get_exchange_config(db).model_dump(), "current": exchange.usd_brl(db)}


@router.put("/config/exchange", response_model=ExchangeConfigOut)
def update_exchange_config(config: ExchangeConfig, db: Session = Depends(get_db)):
    """Vale na hora. Desligada, o painel usa a cotação fixa e não consulta o Banco Central."""
    saved = save_exchange_config(db, config)
    return {**saved.model_dump(), "current": exchange.usd_brl(db)}


@router.get("/config/ai", response_model=AIConfig)
def read_ai_config(db: Session = Depends(get_db)):
    """Liga/desliga do atendimento com IA."""
    return get_ai_config(db)


@router.put("/config/ai", response_model=AIConfig)
def update_ai_config(config: AIConfig, db: Session = Depends(get_db)):
    """Desligada, nada chama o Claude: o chat e o Telegram respondem um recado fixo e registram a mensagem,
    e o follow-up e os resumos automáticos param. Vale na hora."""
    return save_ai_config(db, config)


@router.get("/config/rate-limit", response_model=RateLimitConfig)
def read_rate_limit_config(db: Session = Depends(get_db)):
    """Limites de mensagens por conversa, por IP, conversas novas por IP e teto diário."""
    return get_rate_limit_config(db)


@router.put("/config/rate-limit", response_model=RateLimitConfig)
def update_rate_limit_config(config: RateLimitConfig, db: Session = Depends(get_db)):
    return save_rate_limit_config(db, config)


@router.get("/config/widget", response_model=WidgetConfig)
def read_widget_config(db: Session = Depends(get_db)):
    """Domínios autorizados a embutir o widget da Laris."""
    return get_widget_config(db)


@router.put("/config/widget", response_model=WidgetConfig)
def update_widget_config(config: WidgetConfig, db: Session = Depends(get_db)):
    """Vale em até 30s: o app web renova a regra frame-ancestors do /embed a cada 30s."""
    return save_widget_config(db, config)


@router.get("/config/followup", response_model=FollowupConfig)
def read_followup_config(db: Session = Depends(get_db)):
    """Configuração atual do follow-up (banco, ou padrões do .env se nunca foi alterada)."""
    return get_followup_config(db)


@router.put("/config/followup", response_model=FollowupConfig)
def update_followup_config(config: FollowupConfig, db: Session = Depends(get_db)):
    """Altera o follow-up em tempo real: vale a partir do próximo ciclo do job (até 30s)."""
    return save_followup_config(db, config)


@router.get("/config/email", response_model=EmailConfigOut)
def read_email_config(db: Session = Depends(get_db)):
    """Configuração do e-mail aos corretores + dados da conexão SMTP (sem credenciais)."""
    return {**get_email_config(db).model_dump(), "smtp": smtp_info()}


@router.put("/config/email", response_model=EmailConfigOut)
def update_email_config(config: EmailConfig, db: Session = Depends(get_db)):
    return {**save_email_config(db, config).model_dump(), "smtp": smtp_info()}


@router.post("/config/email/test")
def email_test(db: Session = Depends(get_db)):
    """Envia um e-mail de teste para a caixa de demonstração, para validar a conexão SMTP."""
    to_addr = str(get_email_config(db).demo_recipient)
    try:
        send_test_email(to_addr)
    except (smtplib.SMTPException, OSError) as exc:
        raise HTTPException(502, f"Falha no envio: {type(exc).__name__}: {exc}") from exc
    return {"enviado_para": to_addr}


@router.get("/config/telegram", response_model=TelegramConfigOut)
def read_telegram_config(db: Session = Depends(get_db)):
    """Liga/desliga do bot + situação da conexão (sem o token)."""
    return {**telegram.bot_info(), **get_telegram_config(db).model_dump()}


@router.put("/config/telegram", response_model=TelegramConfigOut)
def update_telegram_config(config: TelegramConfig, db: Session = Depends(get_db)):
    """Desligado, o bot para de responder e os follow-ups não são entregues no Telegram."""
    saved = save_telegram_config(db, config)
    return {**telegram.bot_info(), **saved.model_dump()}


@router.post("/followups/run")
def trigger_followups():
    """Dispara o ciclo de follow-up agora, mesmo com o envio automático desligado ou em horário de silêncio."""
    return {"enviados": run_followups(force=True)}


@router.post("/admin/demo/reset")
def demo_reset(db: Session = Depends(get_db)):
    """Apaga leads, conversas, resumos e agenda e recria o cenário de demonstração (imóveis são mantidos)."""
    return reset_demo(db)

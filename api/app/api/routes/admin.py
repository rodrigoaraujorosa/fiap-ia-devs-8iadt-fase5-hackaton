import smtplib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.jobs.followup import run_followups
from app.services.app_config import (
    EmailConfig,
    FollowupConfig,
    get_email_config,
    get_followup_config,
    save_email_config,
    save_followup_config,
)
from app.services.demo import reset_demo
from app.services.mailer import send_test_email, smtp_info

router = APIRouter(tags=["configuração"])


class SmtpInfo(BaseModel):
    host: str
    port: int
    security: str
    authenticated: bool
    sender: str
    local_test_inbox: bool


class EmailConfigOut(EmailConfig):
    smtp: SmtpInfo


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


@router.post("/followups/run")
def trigger_followups():
    """Dispara o ciclo de follow-up agora, mesmo com o envio automático desligado ou em horário de silêncio."""
    return {"enviados": run_followups(force=True)}


@router.post("/admin/demo/reset")
def demo_reset(db: Session = Depends(get_db)):
    """Apaga leads, conversas, resumos e agenda e recria o cenário de demonstração (imóveis são mantidos)."""
    return reset_demo(db)

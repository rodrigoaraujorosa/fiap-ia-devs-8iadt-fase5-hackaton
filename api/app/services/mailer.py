"""Envio do resumo ao corretor por e-mail (SMTP), com convite de calendário e histórico em email_logs.

Destinatário: o corretor da visita agendada ou o responsável pelo lead. No modo demonstração, tudo vai para
uma única caixa (o corretor de destino aparece no assunto e no topo do e-mail). Endereços fictícios
(@*.example) nunca recebem envio real: o e-mail fica registrado como "ignorado", com o motivo.
"""

import logging
import smtplib
import time
import uuid
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import EmailLog, Lead, Property, Summary
from app.services.app_config import get_email_config
from app.services.email_render import (
    EmailContent,
    ics_description,
    render_html,
    render_ics,
    render_text,
    subject_for,
)
from app.services.scheduling import upcoming_appointment

log = logging.getLogger(__name__)

RETRY_DELAYS = (2, 5)  # segundos entre tentativas (3 tentativas no total)


def deliver(msg: EmailMessage) -> None:
    s = get_settings()
    smtp_class = smtplib.SMTP_SSL if s.smtp_ssl else smtplib.SMTP
    with smtp_class(s.smtp_host, s.smtp_port, timeout=20) as smtp:
        if s.smtp_starttls:
            smtp.starttls()
        if s.smtp_user and s.smtp_password:
            smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(msg)


def _deliver_with_retry(msg: EmailMessage) -> None:
    for delay in (*RETRY_DELAYS, None):
        try:
            deliver(msg)
            return
        except (smtplib.SMTPException, OSError) as exc:
            if delay is None or isinstance(exc, smtplib.SMTPAuthenticationError):
                raise
            log.warning("Falha no envio (%s); nova tentativa em %ss", exc, delay)
            time.sleep(delay)


def build_message(content: EmailContent, to_name: str, to_addr: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = get_settings().email_from
    msg["To"] = formataddr((to_name, to_addr))
    msg["Subject"] = content.subject
    msg["Message-ID"] = make_msgid(domain="imobiq.local")
    msg.set_content(content.text)
    msg.add_alternative(content.html, subtype="html")
    if content.ics:
        msg.add_attachment(content.ics.encode(), maintype="text", subtype="calendar", filename="convite.ics",
                           params={"method": "PUBLISH", "charset": "utf-8"})  # fmt: skip
    return msg


def smtp_info() -> dict:
    """Resumo da conexão SMTP para a tela de configurações (sem expor credenciais)."""
    s = get_settings()
    security = "SSL/TLS" if s.smtp_ssl else "STARTTLS" if s.smtp_starttls else "sem criptografia"
    return {
        "host": s.smtp_host,
        "port": s.smtp_port,
        "security": security,
        "authenticated": bool(s.smtp_user and s.smtp_password),
        "sender": s.email_from,
        "local_test_inbox": s.smtp_host in ("mailpit", "127.0.0.1", "localhost"),
    }


def _log(db: Session, **fields) -> EmailLog:
    entry = EmailLog(**fields)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def send_summary_email(
    db: Session, lead_id: uuid.UUID, trigger: str, summary: Summary | None = None
) -> EmailLog | None:
    """Envia o briefing ao corretor. Automático (agendamento/encaminhamento) respeita o liga/desliga; manual não."""
    cfg = get_email_config(db)
    if trigger != "manual" and not cfg.enabled:
        return None
    lead = db.get(Lead, lead_id)
    summary = summary or db.scalar(
        select(Summary).where(Summary.lead_id == lead_id).order_by(Summary.created_at.desc())
    )
    appointment = upcoming_appointment(db, lead_id)
    broker = appointment.broker if appointment else lead.assigned_broker
    subject = subject_for(lead, trigger, appointment)
    base = {"lead_id": lead_id, "summary_id": summary.id if summary else None, "trigger": trigger,
            "demo_mode": cfg.demo_mode, "subject": subject[:200]}  # fmt: skip

    def skip(reason: str) -> EmailLog:
        return _log(db, **base, status="ignorado", detail=reason)

    if summary is None:
        return skip("O lead ainda não tem resumo.")
    if broker is None:
        return skip("O lead ainda não tem corretor responsável.")
    base |= {"broker_id": broker.id, "intended_recipient": broker.email}
    if not cfg.demo_mode and broker.email.lower().endswith(".example"):
        return skip("Corretor com e-mail fictício (.example). Ative o modo demonstração ou cadastre um e-mail real.")

    recipient = str(cfg.demo_recipient) if cfg.demo_mode else broker.email
    codes = set(summary.content.get("imoveis_de_interesse", []))
    if appointment and appointment.property_id:
        codes.add(appointment.property_id)
    properties = {p.id: p for p in db.scalars(select(Property).where(Property.id.in_(codes)))} if codes else {}
    render_args = {
        "lead": lead, "summary": summary, "broker": broker, "trigger": trigger, "appointment": appointment,
        "properties": properties, "dashboard_url": f"{get_settings().public_app_url}/dashboard/leads/{lead_id}",
        "demo_recipient": recipient if cfg.demo_mode else None,
    }  # fmt: skip
    if cfg.demo_mode:
        subject = f"[Demo → {broker.name}] {subject}"
    text = render_text(**render_args)
    ics = None
    if appointment:
        prop = properties.get(appointment.property_id or "")
        ics = render_ics(lead=lead, appointment=appointment, prop=prop,
                         description=ics_description(lead, summary, render_args["dashboard_url"]))  # fmt: skip
    content = EmailContent(subject=subject, html=render_html(**render_args), text=text, ics=ics)
    to_name = f"{broker.name} (demonstração)" if cfg.demo_mode else broker.name
    base |= {"recipient": recipient, "subject": subject[:200]}

    try:
        _deliver_with_retry(build_message(content, to_name, recipient))
    except (smtplib.SMTPException, OSError) as exc:
        log.exception("Falha ao enviar o resumo do lead %s", lead_id)
        return _log(db, **base, status="erro", detail=f"{type(exc).__name__}: {exc}"[:500])
    log.info("Resumo do lead %s enviado para %s (%s)", lead_id, recipient, trigger)
    return _log(db, **base, status="enviado")


def send_test_email(to_addr: str) -> None:
    """E-mail simples para validar a conexão SMTP a partir da tela de configurações."""
    s = get_settings()
    content = EmailContent(
        subject="Teste de envio · ImobiQ",
        text=f"Tudo certo! A ImobiQ consegue enviar e-mails por {s.smtp_host}:{s.smtp_port}.",
        html=(
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#1f2933">'
            '<p style="font-size:20px;font-weight:bold;margin:0 0 12px">Imobi<span style="color:#0f766e">Q</span></p>'
            f"<p>Tudo certo! A ImobiQ consegue enviar e-mails por <b>{s.smtp_host}:{s.smtp_port}</b>.</p>"
            "<p>Os resumos dos leads vão chegar assim que a Laris agendar ou encaminhar um atendimento.</p></div>"
        ),
    )
    deliver(build_message(content, "Teste ImobiQ", to_addr))

"""E-mail ao corretor: conteúdo seguro, convite de calendário, modo demonstração e registro de cada envio."""

import smtplib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models import Broker, EmailLog, Lead, Summary
from app.services import mailer
from app.services.app_config import get_email_config, save_email_config
from app.services.email_render import _ics_fold, render_html, render_ics

CONTENT = {
    "resumo": "Cliente quer <script>alert(1)</script> perto do metrô",
    "perfil": "Casal, 1º imóvel",
    "necessidades": ["2 quartos", "até R$ 900 mil"],
    "imoveis_de_interesse": ["IMV-007"],
    "objecoes_e_duvidas": [],
    "proximos_passos": ["Ligar amanhã"],
    "abordagem_sugerida": "Tom acolhedor",
}


def test_html_escapes_lead_content():
    lead = SimpleNamespace(name="Ana <b>", phone=None, intent="compra", temperature="quente", score=80, channel="web")
    broker = SimpleNamespace(name="Mariana Costa", email="mariana@imobiq.example")
    html = render_html(
        lead=lead,
        summary=SimpleNamespace(content=CONTENT),
        broker=broker,
        trigger="manual",
        appointment=None,
        properties={},
        dashboard_url='http://x/"onmouseover=',
        demo_recipient=None,
    )
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "Ana &lt;b&gt;" in html
    assert 'href="http://x/&quot;onmouseover="' in html


def test_ics_is_valid_and_folded():
    start = datetime(2026, 9, 28, 15, tzinfo=UTC)
    appt = SimpleNamespace(
        id="abc", kind="visita", slot=SimpleNamespace(start_at=start, end_at=start + timedelta(hours=1))
    )
    prop = SimpleNamespace(id="IMV-007", neighborhood="Vila Mariana", city="São Paulo")
    lead = SimpleNamespace(name="Ana Souza")
    ics = render_ics(lead=lead, appointment=appt, prop=prop, description="Linha longa, com vírgula; " * 10)
    lines = ics.split("\r\n")
    assert lines[0] == "BEGIN:VCALENDAR" and "DTSTART:20260928T150000Z" in lines
    assert "LOCATION:Vila Mariana\\, São Paulo" in lines
    assert all(len(line.encode()) <= 75 for line in lines)
    assert _ics_fold("x" * 200).count("\r\n ") >= 2


@pytest.fixture
def lead_with_summary(db):
    broker = db.scalar(select(Broker).order_by(Broker.id))
    lead = Lead(channel="web", name="Teste E-mail", regions=[], extra={}, intent="compra", assigned_broker_id=broker.id,
                last_message_at=datetime.now(UTC))  # fmt: skip
    db.add(lead)
    db.flush()
    db.add(Summary(lead_id=lead.id, content=CONTENT, text="resumo"))
    db.commit()
    yield lead
    db.delete(lead)
    db.commit()


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "deliver", sent.append)
    monkeypatch.setattr(mailer, "RETRY_DELAYS", ())
    return sent


@pytest.fixture
def email_config(db):
    original = get_email_config(db)
    yield original
    save_email_config(db, original)


def test_demo_mode_delivers_to_demo_inbox(db, lead_with_summary, outbox, email_config):
    save_email_config(db, email_config.model_copy(update={"enabled": True, "demo_mode": True}))
    entry = mailer.send_summary_email(db, lead_with_summary.id, "encaminhamento")
    assert entry.status == "enviado"
    assert entry.recipient == email_config.demo_recipient
    assert entry.intended_recipient.endswith(".example")
    msg = outbox[0]
    assert email_config.demo_recipient in msg["To"]
    assert msg["Subject"].startswith("[Demo → ")
    assert msg.get_body(("html",)) is not None and msg.get_body(("plain",)) is not None


def test_real_mode_never_sends_to_fictitious_address(db, lead_with_summary, outbox, email_config):
    save_email_config(db, email_config.model_copy(update={"enabled": True, "demo_mode": False}))
    entry = mailer.send_summary_email(db, lead_with_summary.id, "manual")
    assert entry.status == "ignorado" and ".example" in entry.detail
    assert not outbox


def test_disabled_skips_automatic_but_not_manual(db, lead_with_summary, outbox, email_config):
    save_email_config(db, email_config.model_copy(update={"enabled": False, "demo_mode": True}))
    assert mailer.send_summary_email(db, lead_with_summary.id, "agendamento") is None
    assert mailer.send_summary_email(db, lead_with_summary.id, "manual").status == "enviado"
    assert len(outbox) == 1


def test_smtp_failure_is_logged(db, lead_with_summary, email_config, monkeypatch):
    def boom(msg):
        raise smtplib.SMTPServerDisconnected("conexão caiu")

    monkeypatch.setattr(mailer, "deliver", boom)
    monkeypatch.setattr(mailer, "RETRY_DELAYS", ())
    save_email_config(db, email_config.model_copy(update={"enabled": True, "demo_mode": True}))
    entry = mailer.send_summary_email(db, lead_with_summary.id, "manual")
    assert entry.status == "erro" and "conexão caiu" in entry.detail
    assert db.scalar(select(EmailLog).where(EmailLog.lead_id == lead_with_summary.id)).status == "erro"


def test_email_config_api(client, email_config):
    body = {"enabled": True, "demo_mode": True, "demo_recipient": "outra@arrtsoftware.com.br"}
    res = client.put("/config/email", json=body)
    assert res.status_code == 200
    data = client.get("/config/email").json()
    assert data["demo_recipient"] == "outra@arrtsoftware.com.br"
    assert "password" not in str(data["smtp"]).lower()  # credenciais nunca saem da API
    assert client.put("/config/email", json={**body, "demo_recipient": "não é e-mail"}).status_code == 422

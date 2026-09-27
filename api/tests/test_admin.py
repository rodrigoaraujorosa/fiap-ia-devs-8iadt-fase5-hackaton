"""Senha de administrador e liga/desliga da IA (sem LLM: com a IA desligada nada chama o Claude)."""

import pytest

from app.core.config import get_settings
from app.models import Lead, Message
from app.services import chat
from app.services.app_config import AIConfig, get_ai_config, save_ai_config


@pytest.fixture
def password(monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_password", "senha-da-demo")
    return "senha-da-demo"


def test_config_is_open_without_password(client):
    assert client.get("/auth/status").json() == {"required": False, "authenticated": True}
    assert client.get("/config/ai").status_code == 200


def test_config_requires_login_with_password(client, password):
    assert client.get("/config/ai").status_code == 401
    assert client.put("/config/ai", json={"enabled": False}).status_code == 401
    assert client.post("/admin/demo/reset").status_code == 401
    assert client.post("/auth/login", json={"password": "errada"}).status_code == 401

    token = client.post("/auth/login", json={"password": password}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/auth/status", headers=headers).json() == {"required": True, "authenticated": True}
    assert client.get("/config/ai", headers=headers).status_code == 200
    assert client.get("/chat/telegram").status_code == 200  # o chat do visitante continua aberto

    get_settings().admin_password = "outra-senha"  # trocar a senha invalida os tokens emitidos
    assert client.get("/config/ai", headers=headers).status_code == 401


@pytest.fixture
def ai_off(db):
    before = get_ai_config(db)
    save_ai_config(db, AIConfig(enabled=False))
    yield
    save_ai_config(db, before)


def test_paused_ai_answers_without_llm(db, ai_off, monkeypatch):
    def no_llm():
        raise AssertionError("não deveria chamar o Claude com a IA desligada")

    monkeypatch.setattr(chat, "get_graph", no_llm)
    lead = Lead(channel="web", regions=[], requirements=[], extra={})
    db.add(lead)
    db.commit()
    try:
        events = list(chat.run_turn(lead.id, "Oi, quero alugar um andar na Faria Lima"))
        assert events[-1]["type"] == "done" and events[-1]["reply"] == chat.PAUSED_REPLY
        events = list(chat.run_turn(lead.id, "Sou o Pedro, meu telefone é (11) 97777-6666"))
        assert events[-1]["reply"] == chat.PAUSED_THANKS
        assert events[-1]["lead"]["phone"] == "+55 11 97777-6666"
        assert events[-1]["lead"]["name"] == "Pedro"
        db.expire_all()
        contents = [m.content for m in db.query(Message).filter(Message.lead_id == lead.id).order_by(Message.id)]
        assert contents[0].startswith("Oi, quero alugar")  # o recado do visitante fica para o corretor
        assert db.get(Lead, lead.id).next_followup_at is None
    finally:
        db.delete(db.get(Lead, lead.id))
        db.commit()


def test_paused_ai_blocks_followups_and_summaries(db, client, ai_off):
    from app.jobs.followup import run_followups

    assert run_followups(force=True) == 0
    lead_id = db.query(Lead.id).first()[0]
    response = client.post(f"/leads/{lead_id}/summary")
    assert response.status_code == 409 and "pausado" in response.json()["detail"]
    assert client.get("/dashboard/metrics").json()["ai_enabled"] is False


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("Juliano, 51999991234", "Juliano"),
        ("juliano silva 51 99999-1234", "Juliano Silva"),
        ("Oi, meu nome é ana e meu whatsapp é 11 98888-7777", "Ana"),
        ("Sou a Camila", "Camila"),
        ("Boa tarde", None),
        ("11 98888-7777", None),
        ("quero alugar um andar corporativo na faria lima 11 98888-7777", None),
    ],
)
def test_guess_name_without_llm(text, name):
    assert chat.guess_name(text) == name


def test_contact_form_saves_name_and_phone(db, client, ai_off):
    assert client.get("/chat/status").json() == {"ai_enabled": False}
    lead_id = client.post("/chat/sessions", json={}).json()["id"]
    try:
        bad = client.post(f"/chat/{lead_id}/contact", json={"name": "Juliano", "phone": "1234-5678"})
        assert bad.status_code == 422
        ok = client.post(f"/chat/{lead_id}/contact", json={"name": "juliano souza", "phone": "(51) 99999-1234"})
        assert ok.status_code == 200
        assert ok.json()["name"] == "Juliano Souza" and ok.json()["phone"] == "+55 51 99999-1234"
        messages = client.get(f"/chat/{lead_id}/messages").json()
        assert messages[0]["content"] == "Nome: Juliano Souza · Telefone: +55 51 99999-1234"
        assert messages[-1]["content"] == chat.PAUSED_THANKS
    finally:
        db.delete(db.get(Lead, lead_id))
        db.commit()

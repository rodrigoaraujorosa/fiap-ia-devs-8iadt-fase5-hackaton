"""Bot do Telegram sem rede nem LLM: um Bot falso registra as chamadas à API do Telegram."""

import random
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import Lead, Message, Slot
from app.models.enums import Channel
from app.services import telegram
from app.services.app_config import TelegramConfig
from app.services.telegram_format import md_to_html, property_block, split_message


class FakeBot:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def call(self, method, **params):
        self.calls.append((method, params))
        return {"message_id": len(self.calls)} if method == "sendMessage" else True

    def sent(self) -> list[str]:
        return [p["text"] for m, p in self.calls if m == "sendMessage"]


@pytest.fixture
def bot(db, monkeypatch):
    fake = FakeBot()
    monkeypatch.setattr(telegram, "_bot", fake)
    monkeypatch.setattr(telegram, "_info", {"username": "laris_teste_bot", "first_name": "Laris"})
    monkeypatch.setattr(telegram, "_status", "conectado")
    monkeypatch.setattr(get_settings(), "telegram_bot_token", "123:fake")
    telegram._seen.clear()
    yield fake


@pytest.fixture
def chat_id(db):
    cid = random.randint(5 * 10**9, 9 * 10**9)  # ids reais do Telegram passam de 2^31
    yield cid
    for lead in db.scalars(select(Lead).where(telegram.chat_filter(cid))):
        db.delete(lead)
    db.commit()


def _message(chat_id: int, text: str, update_id: int | None = None) -> dict:
    return {
        "update_id": update_id or random.randint(1, 10**9),
        "message": {"chat": {"id": chat_id, "type": "private"}, "from": {"first_name": "rodrigo"}, "text": text},
    }


# ------------------------------------------------------------------ formatação


def test_markdown_to_telegram_html():
    text = "### Opções\n- **IMV-025** · Faria Lima, *AAA*\n- Veja [o site](https://x.com/a?b=1&c=2)\nPreço < R$ 300 mil"
    out = md_to_html(text)
    assert "<b>Opções</b>" in out
    assert "• <b>IMV-025</b> · Faria Lima, <i>AAA</i>" in out
    assert '<a href="https://x.com/a?b=1&amp;c=2">o site</a>' in out
    assert "Preço &lt; R$ 300 mil" in out  # o que não é marcação é escapado
    assert md_to_html("2 * 3 = 6 e snake_case_aqui") == "2 * 3 = 6 e snake_case_aqui"


def test_split_long_message():
    parts = split_message("\n\n".join(["parágrafo " * 50] * 20), limit=1000)
    assert len(parts) > 1 and all(len(p) <= 1000 for p in parts)


def test_property_block_shows_total_cost_and_link():
    p = {"id": "IMV-025", "property_type": "andar corporativo", "neighborhood": "Itaim Bibi", "city": "São Paulo",
         "area_m2": 1100, "parking": 22, "purpose": "aluguel", "price": 270400, "condo_fee": 32410, "iptu": 25660,
         "features": {}}  # fmt: skip
    block = property_block(p, "http://site")
    assert "IMV-025 · Andar corporativo" in block and "1.100 m²" in block
    assert "R$ 270.400/mês" in block and "total R$ 328.470" in block
    assert 'href="http://site/imovel-imv-025.html"' in block


# ------------------------------------------------------------------ conversa


def test_start_creates_telegram_lead_and_greets(db, bot, chat_id):
    telegram.handle_update(_message(chat_id, "/start"))
    lead = db.scalars(select(Lead).where(telegram.chat_filter(chat_id))).one()
    assert lead.channel == Channel.TELEGRAM
    assert lead.extra["source"]["brand"] == get_settings().telegram_brand
    assert "Eu sou a Laris" in bot.sent()[-1]
    assert db.scalar(select(Message.content).where(Message.lead_id == lead.id)).startswith("Oi!")  # vai ao dashboard

    telegram.handle_update(_message(chat_id, "/start"))  # voltou: não cria outro lead nem repete a apresentação
    assert db.scalar(
        select(Lead.id).where(telegram.chat_filter(chat_id)).where(Lead.id != lead.id)
    ) is None  # fmt: skip
    assert "de novo" in bot.sent()[-1]


def test_text_goes_to_the_same_lead_once(db, bot, chat_id, monkeypatch):
    turns = []
    monkeypatch.setattr(telegram, "_run", lambda cid, lead_id, text: turns.append((cid, lead_id, text)))
    update = _message(chat_id, "Procuro um andar corporativo na Faria Lima", update_id=424242)
    telegram.handle_update(update)
    telegram.handle_update(update)  # o webhook pode reenviar o mesmo update
    assert len(turns) == 1 and turns[0][2] == "Procuro um andar corporativo na Faria Lima"
    telegram.handle_update(_message(chat_id, "até 300 mil"))
    assert turns[1][1] == turns[0][1]  # mesma conversa, mesmo lead (mesma memória)


def test_restart_command_starts_a_new_lead(db, bot, chat_id):
    telegram.handle_update(_message(chat_id, "/start"))
    first = telegram._chat_lead(db, chat_id).id
    telegram.handle_update(_message(chat_id, "/nova"))
    db.expire_all()
    assert telegram._chat_lead(db, chat_id).id != first
    old = db.get(Lead, first)
    assert "telegram" not in old.extra  # o lead antigo não recebe mais nada pelo Telegram
    db.delete(old)  # já não tem o chat_id: a fixture não o encontraria
    db.commit()


def test_non_text_and_groups(db, bot, chat_id):
    telegram.handle_update({"update_id": 1, "message": {"chat": {"id": chat_id, "type": "private"}, "photo": [{}]}})
    assert "só mensagens de texto" in bot.sent()[-1]
    count = len(bot.calls)
    telegram.handle_update({"update_id": 2, "message": {"chat": {"id": -5, "type": "group"}, "text": "oi"}})
    assert len(bot.calls) == count  # grupos são ignorados


def test_site_conversation_continues_on_telegram(db, bot, chat_id):
    lead = Lead(channel=Channel.SITE, regions=[], requirements=[], extra={}, name="Camila")
    db.add(lead)
    db.commit()
    url = telegram.link_url(lead.id)
    assert url.startswith("https://t.me/laris_teste_bot?start=lk_")
    telegram.handle_update(_message(chat_id, f"/start {url.split('start=')[1]}"))
    db.refresh(lead)
    assert lead.extra["telegram"]["chat_id"] == chat_id and "telegram_link" not in lead.extra
    assert lead.channel == Channel.SITE  # origem preservada; o dashboard mostra que continuou no Telegram
    assert "Oi, Camila" in bot.sent()[-1]
    telegram.handle_update(_message(chat_id, f"/start {url.split('start=')[1]}"))  # token é de uso único
    assert "expirou" in bot.sent()[-2]


def test_expired_link_is_refused(db, bot, chat_id):
    lead = Lead(channel=Channel.SITE, regions=[], requirements=[], extra={})
    db.add(lead)
    db.commit()
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    lead.extra = {"telegram_link": {"token": "velho", "expires_at": past}}
    db.commit()
    telegram.handle_update(_message(chat_id, "/start lk_velho"))
    db.refresh(lead)
    assert "telegram" not in lead.extra
    db.delete(lead)
    db.commit()


def test_slot_button_books_through_the_agent(db, bot, chat_id, monkeypatch):
    turns = []
    monkeypatch.setattr(telegram, "_run", lambda cid, lead_id, text: turns.append(text))
    telegram.handle_update(_message(chat_id, "/start"))
    slot = db.scalars(select(Slot).where(Slot.is_booked.is_(False)).limit(1)).first()
    telegram.handle_update({"update_id": random.randint(1, 10**9), "callback_query": {
        "id": "cb1", "data": f"slot:{slot.id}", "message": {"message_id": 7, "chat": {"id": chat_id}}}})  # fmt: skip
    assert turns and turns[0].startswith("Pode ser ") and " com " in turns[0]
    methods = [m for m, _ in bot.calls]
    assert "answerCallbackQuery" in methods and "editMessageReplyMarkup" in methods
    assert "Você escolheu" in bot.sent()[-1]


def test_keyboard_labels():
    kb = telegram._slot_keyboard([{"slot_id": 9, "quando": "ter, 30/09 às 10h", "com": "Mariana Costa"}])
    assert kb == {"inline_keyboard": [[{"text": "ter, 30/09 às 10h · Mariana", "callback_data": "slot:9"}]]}


def test_followup_is_delivered_on_telegram(db, bot, chat_id):
    telegram.handle_update(_message(chat_id, "/start"))
    lead_id = telegram._chat_lead(db, chat_id).id
    assert telegram.deliver_followup(lead_id, "Oi! Conseguiu pensar no **orçamento**?")
    assert bot.sent()[-1] == "Oi! Conseguiu pensar no <b>orçamento</b>?"


def test_disabled_bot_ignores_updates(db, bot, chat_id, monkeypatch):
    monkeypatch.setattr(telegram, "get_telegram_config", lambda db=None: TelegramConfig(enabled=False))
    telegram.handle_update(_message(chat_id, "/start"))
    assert bot.calls == []
    assert telegram.deliver_followup(uuid.uuid4(), "oi") is False


def test_webhook_requires_secret(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "telegram_bot_token", "123:fake")
    monkeypatch.setattr(s, "telegram_mode", "webhook")
    monkeypatch.setattr(s, "telegram_webhook_secret", "segredo")
    received = []
    monkeypatch.setattr(telegram, "submit", received.append)
    assert client.post("/webhooks/telegram", json={"update_id": 1}).status_code == 401
    headers = {"X-Telegram-Bot-Api-Secret-Token": "segredo"}
    ok = client.post("/webhooks/telegram", json={"update_id": 1}, headers=headers)
    assert ok.status_code == 200 and received == [{"update_id": 1}]


def test_contact_button_saves_the_phone(db, bot, chat_id, monkeypatch):
    turns = []
    monkeypatch.setattr(telegram, "_run", lambda cid, lead_id, text: turns.append(text))
    telegram.handle_update(_message(chat_id, "/start"))
    telegram.handle_update({"update_id": random.randint(1, 10**9), "message": {
        "chat": {"id": chat_id, "type": "private"}, "from": {"id": chat_id, "first_name": "rodrigo"},
        "contact": {"phone_number": "5511977776666", "user_id": chat_id, "first_name": "rodrigo",
                    "last_name": "rosa"}}})  # fmt: skip
    lead = telegram._chat_lead(db, chat_id)
    assert lead.phone == "+55 11 97777-6666" and lead.name == "Rodrigo Rosa"
    assert turns == ["Meu telefone é 5511977776666"]


def test_phone_request_shows_contact_button(db, bot, chat_id, monkeypatch):
    telegram.handle_update(_message(chat_id, "/start"))
    lead_id = telegram._chat_lead(db, chat_id).id
    done = {"type": "done", "reply": "Me passa seu WhatsApp pra confirmar?", "bubbles": [], "property_ids": [],
            "agent": "agendamento", "lead": {"phone": None, "extra": {}}}  # fmt: skip
    monkeypatch.setattr(telegram, "run_turn", lambda lead_id, text: iter([done]))
    telegram._run(chat_id, lead_id, "pode ser o primeiro")
    last = [p for m, p in bot.calls if m == "sendMessage"][-1]
    assert last["reply_markup"]["keyboard"][0][0]["request_contact"] is True
    telegram._contact_asked.discard(chat_id)

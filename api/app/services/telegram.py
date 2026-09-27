"""Bot do Telegram: a mesma Laris (grafo, memória, qualificação, agenda) atendendo pelo Telegram.

- Cada conversa privada com o bot é ligada a um lead (extra.telegram.chat_id); o thread do LangGraph continua
  sendo o id do lead, então a memória é a mesma do chat web.
- Local: long polling (a API busca as mensagens; não precisa de URL pública). Produção: webhook
  POST /webhooks/telegram, conferindo o segredo no cabeçalho.
- "digitando…" enquanto a Laris pensa, respostas em HTML do Telegram, imóveis citados com link para o site,
  horários de visita como botões e follow-up entregue no próprio Telegram.
- Ponte com o site: /start lk_<token> traz para o Telegram uma conversa que começou no widget.
"""

import html
import logging
import secrets
import threading
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select

from app.agents.runtime import get_graph
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Broker, Lead, Message, Property, Slot
from app.models.enums import Channel, MessageRole
from app.schemas.property import PropertyOut
from app.services.app_config import get_telegram_config
from app.services.chat import _lead_locks, run_turn
from app.services.scheduling import format_slot
from app.services.telegram_format import md_to_html, property_block, split_message, strip_markdown

log = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)  # o httpx registra a URL da requisição, que contém o token

API = "https://api.telegram.org"
LINK_TTL = timedelta(minutes=30)
TYPING_EVERY = 4.5  # o "digitando…" do Telegram some após ~5s: reenviado enquanto a Laris pensa
MAX_TEXT = 2000
ALLOWED_UPDATES = ["message", "callback_query"]
RESTART_COMMANDS = {"/nova", "/novo", "/reiniciar"}

HELP = (
    "Sou a Laris, assistente virtual da {brand} 😊 É só me contar o que você procura, do seu jeito.\n\n"
    "Comandos:\n/nova · começar um novo atendimento"
)
WELCOME = (
    "Oi! Eu sou a Laris, assistente virtual da {brand} 😊\n\n"
    "Posso te ajudar a encontrar um espaço para a sua empresa (conjunto, andar corporativo, prédio ou galpão) "
    "ou um imóvel para investir. Me conta o que você procura?"
)
ONLY_TEXT = "Por enquanto eu entendo só mensagens de texto 😊 Me conta por escrito o que você procura?"


class TelegramError(Exception):
    """Erro da API do Telegram (a mensagem nunca inclui a URL, que contém o token)."""


class Bot:
    def __init__(self, token: str):
        self._client = httpx.Client(base_url=f"{API}/bot{token}/", timeout=httpx.Timeout(40, connect=10))

    def call(self, method: str, **params):
        payload = {k: v for k, v in params.items() if v is not None}
        try:
            response = self._client.post(method, json=payload)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TelegramError(f"{method}: falha de conexão ({type(exc).__name__})") from None
        if not data.get("ok"):
            raise TelegramError(f"{method}: {data.get('description', 'erro desconhecido')}")
        return data["result"]

    def close(self) -> None:
        self._client.close()


# ------------------------------------------------------------------ estado do módulo

_bot: Bot | None = None
_info: dict | None = None  # resposta do getMe (username, first_name)
_status = "desligado"
_stop = threading.Event()
_thread: threading.Thread | None = None
_executor: ThreadPoolExecutor | None = None
_seen: deque[int] = deque(maxlen=2000)  # updates já tratados (o webhook pode reenviar)
_seen_lock = threading.Lock()


def configured() -> bool:
    return bool(get_settings().telegram_bot_token)


def bot_info() -> dict:
    """Situação do bot para a tela de configurações e para o widget."""
    s = get_settings()
    username = (_info or {}).get("username")
    return {
        "configured": configured(),
        "enabled": get_telegram_config().enabled,
        "mode": s.telegram_mode,
        "status": _status,
        "username": username,
        "name": (_info or {}).get("first_name"),
        "link": f"https://t.me/{username}" if username else None,
    }


def available() -> bool:
    return configured() and _info is not None and get_telegram_config().enabled


# ------------------------------------------------------------------ envio


def send(chat_id: int, text: str, *, markdown: bool = False, reply_markup: dict | None = None) -> None:
    """Envia texto (HTML do Telegram). markdown=True converte o Markdown da Laris antes."""
    if _bot is None:
        return
    body = md_to_html(text) if markdown else text
    parts = split_message(body)
    for i, part in enumerate(parts):
        markup = reply_markup if i == len(parts) - 1 else None
        try:
            _bot.call("sendMessage", chat_id=chat_id, text=part, parse_mode="HTML", reply_markup=markup,
                      link_preview_options={"is_disabled": True})  # fmt: skip
        except TelegramError as exc:
            if "can't parse entities" in str(exc):  # HTML inválido: manda sem formatação
                plain = strip_markdown(text) if markdown else html.unescape(part)
                _bot.call("sendMessage", chat_id=chat_id, text=plain[:4096], reply_markup=markup)
            elif "blocked" in str(exc) or "chat not found" in str(exc):
                log.info("Chat %s indisponível no Telegram: %s", chat_id, exc)
                return
            else:
                raise


def _typing(chat_id: int, done: threading.Event) -> None:
    while not done.is_set():
        try:
            _bot.call("sendChatAction", chat_id=chat_id, action="typing")
        except TelegramError:
            pass
        done.wait(TYPING_EVERY)


# ------------------------------------------------------------------ leads


def chat_filter(chat_id: int):
    """Leads ligados a um chat. Compara como texto: ids do Telegram passam do limite de um INTEGER (32 bits)."""
    return Lead.extra["telegram"]["chat_id"].astext == str(chat_id)


def _chat_lead(db, chat_id: int) -> Lead | None:
    stmt = select(Lead).where(chat_filter(chat_id))
    return db.scalars(stmt.order_by(Lead.created_at.desc()).limit(1)).first()


def _profile(chat_id: int, user: dict) -> dict:
    return {"chat_id": chat_id, "username": user.get("username"), "first_name": user.get("first_name")}


def _unlink_chat(db, chat_id: int, keep: uuid.UUID | None = None) -> None:
    for old in db.scalars(select(Lead).where(chat_filter(chat_id))):
        if old.id != keep:
            old.extra = {k: v for k, v in (old.extra or {}).items() if k != "telegram"}


def _create_lead(db, chat_id: int, user: dict) -> Lead:
    _unlink_chat(db, chat_id)
    extra = {"telegram": _profile(chat_id, user), "source": {"brand": get_settings().telegram_brand}}
    lead = Lead(channel=Channel.TELEGRAM, regions=[], requirements=[], extra=extra)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _greet(chat_id: int, lead_id: uuid.UUID) -> None:
    """Boas-vindas: vão para o histórico do dashboard e para a memória da Laris (para ela não se reapresentar)."""
    text = WELCOME.format(brand=get_settings().telegram_brand)
    with SessionLocal() as db:
        db.add(Message(lead_id=lead_id, role=MessageRole.ASSISTANT, content=text, agent="compra_aluguel",
                       meta={"property_ids": []}))  # fmt: skip
        db.get(Lead, lead_id).last_message_at = datetime.now(UTC)
        db.commit()
    try:
        config = {"configurable": {"thread_id": str(lead_id)}}
        memory = {"messages": [{"role": "assistant", "content": text}]}
        get_graph().update_state(config, memory, as_node="compra_aluguel")
    except Exception:  # memória é um bônus: a conversa segue mesmo sem ela
        log.warning("Não foi possível registrar as boas-vindas na memória do lead %s", lead_id, exc_info=True)
    send(chat_id, text, markdown=True)


def link_url(lead_id: uuid.UUID) -> str | None:
    """Link t.me que leva a conversa do site para o Telegram (token de uso único, válido por 30 min)."""
    if not available():
        return None
    token = secrets.token_urlsafe(12)
    with SessionLocal() as db:
        lead = db.get(Lead, lead_id)
        if lead is None:
            return None
        expires = (datetime.now(UTC) + LINK_TTL).isoformat()
        lead.extra = {**(lead.extra or {}), "telegram_link": {"token": token, "expires_at": expires}}
        db.commit()
    return f"https://t.me/{_info['username']}?start=lk_{token}"


def _claim_link(db, token: str, chat_id: int, user: dict) -> Lead | None:
    lead = db.scalars(select(Lead).where(Lead.extra["telegram_link"]["token"].astext == token).limit(1)).first()
    if lead is None:
        return None
    link = lead.extra["telegram_link"]
    extra = {k: v for k, v in lead.extra.items() if k != "telegram_link"}
    if datetime.fromisoformat(link["expires_at"]) < datetime.now(UTC):
        lead.extra = extra
        db.commit()
        return None
    _unlink_chat(db, chat_id, keep=lead.id)
    lead.extra = {**extra, "telegram": _profile(chat_id, user)}
    db.commit()
    return lead


# ------------------------------------------------------------------ conversa


def _slot_keyboard(slots: list[dict]) -> dict:
    rows = [
        [{"text": f"{s['quando']} · {s['com'].split()[0]}"[:60], "callback_data": f"slot:{s['slot_id']}"}]
        for s in slots[:6]
    ]
    return {"inline_keyboard": rows}


def _property_cards(ids: list[str]) -> str | None:
    site = get_settings().public_site_url
    with SessionLocal() as db:
        props = [PropertyOut.model_validate(p).model_dump() for i in ids[:4] if (p := db.get(Property, i))]
    return "\n\n".join(property_block(p, site) for p in props) or None


def _run(chat_id: int, lead_id: uuid.UUID, text: str) -> None:
    """Um turno da Laris: mostra "digitando…", roda o grafo e entrega balões, imóveis e botões de horário."""
    done_typing = threading.Event()
    threading.Thread(target=_typing, args=(chat_id, done_typing), daemon=True).start()
    slots, booked, done, error = [], False, None, None
    try:
        with _lead_locks[lead_id]:  # uma mensagem por vez por conversa (mesma trava do chat web)
            for event in run_turn(lead_id, text[:MAX_TEXT]):
                if event["type"] == "slots":
                    slots = event["items"]
                elif event["type"] == "appointment":
                    booked = True
                elif event["type"] == "error":
                    error = event["message"]
                elif event["type"] == "done":
                    done = event
    finally:
        done_typing.set()

    if not done or not done["reply"]:
        send(chat_id, error or "Não consegui responder agora. Pode tentar de novo em instantes?")
        return
    bubbles = done["bubbles"] or [done["reply"]]
    keyboard = _slot_keyboard(slots) if slots and not booked else None
    for i, bubble in enumerate(bubbles):
        send(chat_id, bubble, markdown=True, reply_markup=keyboard if i == len(bubbles) - 1 else None)
    if done["property_ids"] and (cards := _property_cards(done["property_ids"])):
        send(chat_id, cards)


def _on_start(chat_id: int, user: dict, payload: str) -> None:
    brand = get_settings().telegram_brand
    if payload.startswith("lk_"):
        with SessionLocal() as db:
            lead = _claim_link(db, payload[3:], chat_id, user)
            name = lead.name if lead else None
        if lead:
            hello = f"Oi, {html.escape(name)}! " if name else "Oi! "
            send(chat_id, f"{hello}Trouxe a nossa conversa do site da {html.escape(brand)} para cá 😊 "
                          "Pode continuar de onde parou.")  # fmt: skip
            return
        send(chat_id, "Esse link expirou, mas sem problema: vamos conversar por aqui mesmo 😊")
    with SessionLocal() as db:
        lead = _chat_lead(db, chat_id)
        returning = lead is not None and db.scalar(select(Message.id).where(Message.lead_id == lead.id).limit(1))
        if not returning:
            lead = lead or _create_lead(db, chat_id, user)
        lead_id = lead.id
    if returning:
        send(chat_id, "Que bom te ver de novo! Podemos continuar de onde paramos 😊 "
                      "Se preferir começar do zero, envie /nova.")  # fmt: skip
    else:
        _greet(chat_id, lead_id)


def _on_message(msg: dict) -> None:
    chat = msg.get("chat") or {}
    if chat.get("type") != "private":  # grupos e canais ficam de fora
        return
    chat_id, user = chat["id"], msg.get("from") or {}
    text = (msg.get("text") or "").strip()
    command = text.split(maxsplit=1)[0].split("@")[0].lower() if text.startswith("/") else ""
    if command == "/start":
        _on_start(chat_id, user, text.split(maxsplit=1)[1] if " " in text else "")
        return
    if command in RESTART_COMMANDS:
        with SessionLocal() as db:
            lead_id = _create_lead(db, chat_id, user).id
        _greet(chat_id, lead_id)
        return
    if command:
        send(chat_id, HELP.format(brand=html.escape(get_settings().telegram_brand)))
        return
    if not text:
        send(chat_id, ONLY_TEXT)
        return
    with SessionLocal() as db:
        lead_id = (_chat_lead(db, chat_id) or _create_lead(db, chat_id, user)).id
    _run(chat_id, lead_id, text)


def _on_callback(cb: dict) -> None:
    try:
        _bot.call("answerCallbackQuery", callback_query_id=cb["id"])
    except TelegramError:
        pass
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    data = cb.get("data") or ""
    if not chat_id or not data.startswith("slot:") or not data[5:].isdigit():
        return
    with SessionLocal() as db:
        lead, slot = _chat_lead(db, chat_id), db.get(Slot, int(data[5:]))
        if lead is None or slot is None:
            return
        label = f"{format_slot(slot.start_at)} com {db.get(Broker, slot.broker_id).name}"
        lead_id = lead.id
    try:  # tira os botões: a escolha foi feita
        _bot.call("editMessageReplyMarkup", chat_id=chat_id, message_id=msg["message_id"],
                  reply_markup={"inline_keyboard": []})  # fmt: skip
    except TelegramError:
        pass
    send(chat_id, f"✅ Você escolheu: <b>{html.escape(label)}</b>")
    _run(chat_id, lead_id, f"Pode ser {label}.")


def handle_update(update: dict) -> None:
    """Trata um update do Telegram (vindo do polling ou do webhook). Nunca propaga exceções."""
    if not get_telegram_config().enabled or _bot is None:
        return
    with _seen_lock:
        if update.get("update_id") in _seen:
            return
        _seen.append(update.get("update_id"))
    try:
        if "message" in update:
            _on_message(update["message"])
        elif "callback_query" in update:
            _on_callback(update["callback_query"])
    except Exception:
        log.exception("Erro ao tratar update %s do Telegram", update.get("update_id"))


def submit(update: dict) -> None:
    """Enfileira o update (conversas diferentes em paralelo; a mesma conversa em ordem, pela trava do lead)."""
    if _executor is not None:
        _executor.submit(handle_update, update)


def deliver_followup(lead_id: uuid.UUID, text: str) -> bool:
    """Entrega no Telegram o follow-up de um lead ligado a um chat. False se não houver chat ou o bot estiver off."""
    if not available():
        return False
    with SessionLocal() as db:
        lead = db.get(Lead, lead_id)
        chat_id = ((lead.extra or {}).get("telegram") or {}).get("chat_id") if lead else None
    if not chat_id:
        return False
    try:
        send(chat_id, text, markdown=True)
        return True
    except TelegramError:
        log.exception("Falha ao entregar o follow-up do lead %s no Telegram", lead_id)
        return False


# ------------------------------------------------------------------ ciclo de vida


def _connect() -> bool:
    global _info, _status
    try:
        _info = _bot.call("getMe")
        s = get_settings()
        if s.telegram_mode == "webhook":
            if not (s.telegram_webhook_url and s.telegram_webhook_secret):
                _status = "erro: modo webhook exige TELEGRAM_WEBHOOK_URL e TELEGRAM_WEBHOOK_SECRET"
                return False
            _bot.call("setWebhook", url=s.telegram_webhook_url, secret_token=s.telegram_webhook_secret,
                      allowed_updates=ALLOWED_UPDATES)  # fmt: skip
        else:
            _bot.call("deleteWebhook")  # getUpdates não funciona com webhook ativo
        _status = "conectado"
        log.info("Telegram: conectado como @%s (%s)", _info["username"], s.telegram_mode)
        return True
    except TelegramError as exc:
        _status = f"erro: {exc}"
        log.warning("Telegram: %s", exc)
        return False


def _poll() -> None:
    global _status
    offset = None
    while not _stop.is_set():
        if _info is None or _status != "conectado":
            if not _connect():
                _stop.wait(15)
                continue
        if not get_telegram_config().enabled:
            _stop.wait(5)
            continue
        try:
            updates = _bot.call("getUpdates", offset=offset, timeout=25, allowed_updates=ALLOWED_UPDATES)
        except TelegramError as exc:
            if "Conflict" in str(exc):  # outra instância da API também está fazendo polling com o mesmo token
                _status = "erro: outra instância está usando este bot (Conflict)"
            log.warning("Telegram: %s", exc)
            _stop.wait(5)
            continue
        _status = "conectado"
        for update in updates:
            offset = update["update_id"] + 1
            submit(update)


def start() -> None:
    global _bot, _executor, _thread, _status
    s = get_settings()
    if not s.telegram_bot_token or _bot is not None:
        return
    _bot = Bot(s.telegram_bot_token)
    _executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="telegram")
    _stop.clear()
    _status = "conectando"
    if s.telegram_mode == "webhook":
        threading.Thread(target=_connect, daemon=True, name="telegram-webhook").start()
    else:
        _thread = threading.Thread(target=_poll, daemon=True, name="telegram-polling")
        _thread.start()


def stop() -> None:
    global _bot, _executor, _thread, _info, _status
    _stop.set()
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
    if _bot is not None:
        _bot.close()
    _bot, _executor, _thread, _info, _status = None, None, None, None, "desligado"

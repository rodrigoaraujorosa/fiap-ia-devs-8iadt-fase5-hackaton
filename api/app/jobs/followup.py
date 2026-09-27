"""Follow-up automático: retoma o contato com leads que pararam de responder, mantendo o contexto.

Cadência crescente: 1ª tentativa após N minutos sem resposta, depois 2x, 4x...
Após o máximo de tentativas sem retorno, o lead vai para "perdido".
Parâmetros em app_config (tela /configuration, com padrões no .env): lidos a cada ciclo.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import anthropic
from sqlalchemy import select

from app.agents.llm import claude, transcript, usage_details
from app.agents.prompts import PERSONA, lead_context
from app.agents.qualification import missing_fields
from app.agents.runtime import get_graph
from app.core import observability
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Lead, Message
from app.models.enums import LeadStatus, MessageRole
from app.services import telegram
from app.services.app_config import get_followup_config

log = logging.getLogger(__name__)

ELIGIBLE = (LeadStatus.NOVO, LeadStatus.EM_QUALIFICACAO, LeadStatus.QUALIFICADO)

STRATEGIES = {
    1: "Retome de forma leve exatamente de onde a conversa parou (por exemplo, a pergunta que ficou sem resposta "
    "ou o imóvel que você mostrou). Sem pressão.",
    2: "Agregue valor: traga algo útil ligado ao que o cliente busca (um destaque de um imóvel que você mostrou, "
    "uma característica do bairro, uma dica do mercado) e termine com uma pergunta simples de responder.",
    3: "Última tentativa: seja gentil e breve, diga que vai deixar a conversa em aberto e que ele pode chamar quando "
    "quiser. Pode oferecer uma alternativa leve (por exemplo, receber opções por aqui mais tarde).",
}

FOLLOWUP_INSTRUCTIONS = """
Tarefa atual: FOLLOW-UP. O cliente parou de responder. Escreva a próxima mensagem para reengajá-lo.
- Use o contexto da conversa: chame pelo nome, mencione o que ele procura; nada genérico como "Oi, tudo bem?".
- No máximo 2 frases curtas, tom de WhatsApp. Não repita mensagens de follow-up anteriores.
- Responda apenas com o texto da mensagem, sem aspas nem explicações.
"""


def _claim_due_leads(limit: int = 10) -> list[tuple[uuid.UUID, int, datetime | None]]:
    """Reserva leads vencidos (SKIP LOCKED permite várias instâncias rodando o job sem duplicar)."""
    with SessionLocal() as db:
        leads = db.scalars(
            select(Lead)
            .where(Lead.next_followup_at <= datetime.now(UTC), Lead.status.in_(ELIGIBLE))
            .order_by(Lead.next_followup_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        claimed = [(lead.id, lead.followup_count, lead.last_lead_message_at) for lead in leads]
        for lead in leads:
            lead.next_followup_at = None
        db.commit()
    return claimed


def _generate_message(lead: Lead, history: list[dict], attempt: int, max_attempts: int) -> str:
    settings = get_settings()
    system = [
        {"type": "text", "text": PERSONA + FOLLOWUP_INSTRUCTIONS, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": lead_context(lead, missing_fields(lead))},
    ]
    strategy = STRATEGIES.get(attempt, STRATEGIES[3])
    prompt = (
        f"<conversa>\n{transcript(history, limit=20)}\n</conversa>\n\n"
        f"Follow-up nº {attempt} de {max_attempts}. Estratégia: {strategy}"
    )
    with observability.observation(
        "gerar_follow_up", as_type="generation", model=settings.llm_main_model, input=prompt
    ) as gen:
        response = claude().messages.create(
            model=settings.llm_main_model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "adaptive"},
            output_config={"effort": "low"},
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        gen.update(output=text, usage_details=usage_details(response))
    return text


def send_followup(lead_id: uuid.UUID, attempt_count: int, last_lead_message_at: datetime | None) -> str | None:
    config = {"configurable": {"thread_id": str(lead_id)}}
    with SessionLocal() as db:
        cfg = get_followup_config(db)
        lead = db.get(Lead, lead_id)
        if attempt_count >= cfg.max_attempts:
            lead.status = LeadStatus.PERDIDO
            db.commit()
            log.info("Lead %s marcado como perdido após %s follow-ups", lead_id, attempt_count)
            return None

        attempt = attempt_count + 1
        history = get_graph().get_state(config).values.get("messages", [])
        with observability.trace("follow_up", session_id=str(lead_id), input={"tentativa": attempt}) as root:
            text = _generate_message(lead, history, attempt, cfg.max_attempts)
            root.update(output=text)
        if not text:
            return None

        db.refresh(lead)
        if lead.last_lead_message_at != last_lead_message_at or lead.status not in ELIGIBLE:
            return None  # o lead respondeu enquanto gerávamos a mensagem

        now = datetime.now(UTC)
        db.add(Message(lead_id=lead_id, role=MessageRole.FOLLOWUP, content=text, agent="follow_up",
                       meta={"attempt": attempt}))  # fmt: skip
        lead.followup_count = attempt
        lead.last_message_at = now
        lead.next_followup_at = now + timedelta(minutes=cfg.minutes * 2**attempt)
        db.commit()

    # a mensagem entra na memória do agente, para ele saber o que já foi dito
    get_graph().update_state(config, {"messages": [{"role": "assistant", "content": text}]}, as_node="compra_aluguel")
    via_telegram = telegram.deliver_followup(lead_id, text)  # lead que conversa pelo Telegram recebe lá
    log.info("Follow-up %s enviado ao lead %s%s", attempt, lead_id, " (Telegram)" if via_telegram else "")
    return text


def run_followups(force: bool = False) -> int:
    """Ciclo do job. Respeita liga/desliga e horário de silêncio; force=True (disparo manual) ignora os dois."""
    cfg = get_followup_config()
    if not force and (not cfg.enabled or cfg.in_quiet_hours()):
        return 0
    sent = 0
    for lead_id, count, last_lead_message_at in _claim_due_leads():
        try:
            if send_followup(lead_id, count, last_lead_message_at):
                sent += 1
        except anthropic.APIError:
            log.exception("Falha no follow-up do lead %s; nova tentativa no próximo ciclo", lead_id)
            with SessionLocal() as db:
                db.get(Lead, lead_id).next_followup_at = datetime.now(UTC) + timedelta(minutes=1)
                db.commit()
    return sent

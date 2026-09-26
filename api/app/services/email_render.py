"""Conteúdo do e-mail ao corretor: HTML (estilos inline, compatível com Gmail/Outlook), texto puro e .ics.

Todo texto vindo da conversa passa por html.escape: o lead escreve o que quiser, e isso não pode virar HTML.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape

from app.models import Appointment, Broker, Lead, Property, Summary
from app.services.scheduling import format_slot

BRAND = "#0f766e"
INK = "#1f2933"
MUTED = "#6b7280"
LINE = "#e5e7eb"

INTENT = {"compra": "Compra", "aluguel": "Aluguel", "investimento": "Investimento", "indefinido": "A definir"}
TEMPERATURE = {"quente": "🔥 Quente", "morno": "🌡️ Morno", "frio": "❄️ Frio"}
CHANNEL = {"web": "Chat do site", "telegram": "Telegram", "whatsapp": "WhatsApp"}
KIND = {"visita": "Visita ao imóvel", "reuniao": "Reunião", "videochamada": "Videochamada"}
TRIGGER_LINE = {
    "agendamento": "A Laris agendou um atendimento para você com {name}.",
    "encaminhamento": "A Laris encaminhou {name} para você continuar o atendimento.",
    "manual": "Segue o briefing atualizado de {name}.",
}


@dataclass
class EmailContent:
    subject: str
    html: str
    text: str
    ics: str | None = None


def brl(value: int | None) -> str:
    return f"R$ {value:,.0f}".replace(",", ".") if value else "—"


def _price(prop: Property) -> str:
    return f"{brl(prop.price)}/mês" if prop.purpose == "aluguel" else brl(prop.price)


def subject_for(lead: Lead, trigger: str, appointment: Appointment | None) -> str:
    name = lead.name or "Lead sem nome"
    if trigger == "agendamento" and appointment:
        return (
            f"{KIND.get(appointment.kind, 'Atendimento')} agendada: {name} · {format_slot(appointment.slot.start_at)}"
        )
    if trigger == "encaminhamento":
        return f"Lead encaminhado: {name} · {INTENT.get(lead.intent, lead.intent)} · {lead.temperature}"
    if appointment:
        kind = KIND.get(appointment.kind, "atendimento").lower()
        return f"Resumo do lead: {name} · {kind} {format_slot(appointment.slot.start_at)}"
    return f"Resumo do lead: {name}"


# ---------------------------------------------------------------- HTML


def _section(title: str, body: str) -> str:
    return (
        f'<tr><td style="padding:18px 28px 0">'
        f'<p style="margin:0 0 6px;font-size:12px;font-weight:bold;letter-spacing:.04em;text-transform:uppercase;'
        f'color:{MUTED}">{escape(title)}</p>{body}</td></tr>'
    )


def _list(items: list[str], ordered: bool = False) -> str:
    if not items:
        return f'<p style="margin:0;color:{MUTED}">—</p>'
    tag = "ol" if ordered else "ul"
    lis = "".join(f'<li style="margin:0 0 4px">{escape(i)}</li>' for i in items)
    return f'<{tag} style="margin:0;padding-left:20px;line-height:1.5">{lis}</{tag}>'


def _rows(pairs: list[tuple[str, str]]) -> str:
    rows = "".join(
        f'<tr><td style="padding:4px 12px 4px 0;color:{MUTED};white-space:nowrap;vertical-align:top">{escape(k)}</td>'
        f'<td style="padding:4px 0;color:{INK};font-weight:bold">{escape(v)}</td></tr>'
        for k, v in pairs
    )
    return f'<table role="presentation" cellpadding="0" cellspacing="0" style="font-size:14px">{rows}</table>'


def _appointment_pairs(appointment: Appointment, prop: Property | None) -> list[tuple[str, str]]:
    pairs = [("Quando", format_slot(appointment.slot.start_at)), ("Tipo", KIND.get(appointment.kind, appointment.kind))]
    if prop:
        pairs.append(("Imóvel", f"{prop.id} · {prop.title}"))
        pairs.append(("Onde", f"{prop.neighborhood}, {prop.city}"))
    return pairs


DECISION = {
    "sim": "Sim, decide",
    "compartilhada": "Decide com sócios/diretoria",
    "nao": "Não (pesquisa para outra pessoa)",
}


def _lead_pairs(lead: Lead) -> list[tuple[str, str]]:
    pairs = [
        ("Nome", lead.name or "Não informado"),
        ("Telefone", lead.phone or "Não informado"),
    ]
    if lead.company:
        pairs.append(("Empresa", lead.company + (f" · {lead.job_title}" if lead.job_title else "")))
    if lead.decision_maker:
        pairs.append(("Decisor", DECISION.get(lead.decision_maker, lead.decision_maker)))
    if lead.business_activity:
        pairs.append(("Atividade", lead.business_activity))
    return pairs + [
        ("Intenção", INTENT.get(lead.intent, lead.intent)),
        ("Temperatura", f"{TEMPERATURE.get(lead.temperature, lead.temperature)} ({lead.score}/100)"),
        ("Canal", CHANNEL.get(lead.channel, lead.channel)),
    ]


def render_html(*, lead: Lead, summary: Summary, broker: Broker, trigger: str, appointment: Appointment | None,
                properties: dict[str, Property], dashboard_url: str, demo_recipient: str | None) -> str:  # fmt: skip
    c = summary.content
    first_name = broker.name.split()[0]
    parts: list[str] = []
    if demo_recipient:
        parts.append(
            f'<tr><td style="padding:10px 28px;background:#fff7e6;border-bottom:1px solid #f5deb3;font-size:13px;'
            f'color:#8a5a00">🧪 <b>Modo demonstração</b>: este e-mail seria enviado para {escape(broker.name)} '
            f"({escape(broker.email)}).</td></tr>"
        )
    parts.append(
        f'<tr><td style="padding:22px 28px 0"><span style="font-size:20px;font-weight:bold;color:{INK}">Imobi'
        f'<span style="color:{BRAND}">Q</span></span><span style="font-size:13px;color:{MUTED}">'
        f" &nbsp;·&nbsp; briefing do lead</span></td></tr>"
    )
    line = TRIGGER_LINE.get(trigger, TRIGGER_LINE["manual"]).format(
        name=f"<b>{escape(lead.name or 'um novo lead')}</b>"
    )
    parts.append(
        f'<tr><td style="padding:16px 28px 0"><p style="margin:0 0 4px;font-size:18px;color:{INK}">'
        f"Olá, {escape(first_name)}!</p>"
        f'<p style="margin:0;font-size:15px;line-height:1.5;color:{INK}">{line}</p></td></tr>'
    )
    if appointment:
        prop = properties.get(appointment.property_id or "")
        parts.append(
            f'<tr><td style="padding:16px 28px 0"><div style="border:1px solid {BRAND};border-radius:10px;'
            f'padding:12px 16px;background:#f0fdfa">{_rows(_appointment_pairs(appointment, prop))}</div></td></tr>'
        )
    parts.append(_section("Contato do lead", _rows(_lead_pairs(lead))))
    parts.append(_section("Resumo", f'<p style="margin:0;font-size:15px;line-height:1.55">{escape(c["resumo"])}</p>'))
    parts.append(_section("Perfil", f'<p style="margin:0;font-size:15px">{escape(c["perfil"])}</p>'))
    parts.append(_section("Necessidades", _list(c["necessidades"])))
    interest = [
        f"{code} · {properties[code].title} · {_price(properties[code])}" if code in properties else code
        for code in c["imoveis_de_interesse"]
    ]
    parts.append(_section("Imóveis de interesse", _list(interest)))
    parts.append(_section("Objeções e dúvidas", _list(c["objecoes_e_duvidas"])))
    parts.append(_section("Próximos passos", _list(c["proximos_passos"], ordered=True)))
    parts.append(
        _section(
            "Abordagem sugerida",
            f'<p style="margin:0;padding:10px 14px;border-left:3px solid {BRAND};background:#f8fafc;font-size:15px;'
            f'line-height:1.5">{escape(c["abordagem_sugerida"])}</p>',
        )
    )
    parts.append(
        f'<tr><td style="padding:24px 28px 8px"><a href="{escape(dashboard_url, quote=True)}" '
        f'style="display:inline-block;background:{BRAND};color:#ffffff;text-decoration:none;font-weight:bold;'
        f'font-size:15px;padding:12px 20px;border-radius:8px">Abrir no dashboard</a></td></tr>'
    )
    footer = "Enviado automaticamente pela Laris, SDR virtual da ImobiQ."
    if appointment:
        footer += " O convite de calendário (.ics) está anexado."
    parts.append(
        f'<tr><td style="padding:16px 28px 22px;font-size:12px;color:{MUTED};border-top:1px solid {LINE}">'
        f"{footer}</td></tr>"
    )
    body = "".join(parts)
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        f'<body style="margin:0;padding:0;background:#f4f4f2;font-family:Arial,Helvetica,sans-serif;color:{INK}">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f2">'
        '<tr><td align="center" style="padding:24px 12px">'
        f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;'
        f'background:#ffffff;border:1px solid {LINE};border-radius:12px;overflow:hidden">{body}</table>'
        "</td></tr></table></body></html>"
    )


# ---------------------------------------------------------------- texto puro


def render_text(*, lead: Lead, summary: Summary, broker: Broker, trigger: str, appointment: Appointment | None,
                properties: dict[str, Property], dashboard_url: str, demo_recipient: str | None) -> str:  # fmt: skip
    c = summary.content

    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {i}" for i in items) or "- —"

    lines = []
    if demo_recipient:
        lines += [f"[MODO DEMONSTRAÇÃO] Este e-mail seria enviado para {broker.name} ({broker.email}).", ""]
    lines += [f"Olá, {broker.name.split()[0]}!", TRIGGER_LINE.get(trigger, TRIGGER_LINE["manual"]).format(
        name=lead.name or "um novo lead"), ""]  # fmt: skip
    if appointment:
        prop = properties.get(appointment.property_id or "")
        lines += [f"{k}: {v}" for k, v in _appointment_pairs(appointment, prop)] + [""]
    lines += ["CONTATO DO LEAD"] + [f"{k}: {v}" for k, v in _lead_pairs(lead)] + [""]
    lines += ["RESUMO", c["resumo"], "", "PERFIL", c["perfil"], ""]
    lines += ["NECESSIDADES", bullets(c["necessidades"]), ""]
    lines += ["IMÓVEIS DE INTERESSE", bullets(c["imoveis_de_interesse"]), ""]
    lines += ["OBJEÇÕES E DÚVIDAS", bullets(c["objecoes_e_duvidas"]), ""]
    lines += ["PRÓXIMOS PASSOS", bullets(c["proximos_passos"]), ""]
    lines += ["ABORDAGEM SUGERIDA", c["abordagem_sugerida"], "", f"Abrir no dashboard: {dashboard_url}", ""]
    lines += ["Enviado automaticamente pela Laris, SDR virtual da ImobiQ."]
    return "\n".join(lines)


# ---------------------------------------------------------------- convite de calendário (RFC 5545)


def ics_description(lead: Lead, summary: Summary, dashboard_url: str) -> str:
    c = summary.content
    steps = "\n".join(f"- {step}" for step in c["proximos_passos"])
    return (
        f"Lead: {lead.name or 'sem nome'} · {lead.phone or 'sem telefone'}\n"
        f"{INTENT.get(lead.intent, lead.intent)} · {lead.temperature} ({lead.score}/100)\n\n"
        f"{c['resumo']}\n\nPróximos passos:\n{steps}\n\nDashboard: {dashboard_url}"
    )


def _ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_fold(line: str) -> str:
    """Quebra linhas longas (limite de 75 octetos; continuação começa com espaço)."""
    out, current = [], ""
    for ch in line:
        if len((current + ch).encode()) > 73:
            out.append(current)
            current = " " + ch
        else:
            current += ch
    return "\r\n".join([*out, current])


def _ics_time(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def render_ics(*, lead: Lead, appointment: Appointment, prop: Property | None, description: str) -> str:
    kind = KIND.get(appointment.kind, "Atendimento")
    title = f"{kind}: {lead.name or 'lead'}" + (f" · {prop.id}" if prop else "")
    if appointment.kind == "videochamada":
        location = "Videochamada"
    else:
        location = f"{prop.neighborhood}, {prop.city}" if prop else "A combinar"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ImobiQ//Laris//PT-BR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{appointment.id}@imobiq",
        f"DTSTAMP:{_ics_time(datetime.now(UTC))}",
        f"DTSTART:{_ics_time(appointment.slot.start_at)}",
        f"DTEND:{_ics_time(appointment.slot.end_at)}",
        f"SUMMARY:{_ics_escape(title)}",
        f"LOCATION:{_ics_escape(location)}",
        f"DESCRIPTION:{_ics_escape(description)}",
        "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_ics_fold(line) for line in lines) + "\r\n"

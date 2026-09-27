"""Formatação para o Telegram: Markdown da Laris → HTML aceito pelo Bot API, e mensagens de imóveis.

O Telegram entende um HTML restrito (<b>, <i>, <code>, <a>...), sem listas nem títulos. Tudo o que não é
marcação é escapado, para um "<" digitado pelo modelo não quebrar a mensagem.
"""

import html
import re

MAX_LENGTH = 4096  # limite de caracteres de uma mensagem no Telegram

_HEADING = re.compile(r"^\s*#{1,6}\s+(.*)$")
_BULLET = re.compile(r"^(\s*)[-*•]\s+")
_LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)")
_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*(?!\s)(.+?)(?<!\s)\*\*|__(?!\s)(.+?)(?<!\s)__")
_ITALIC = re.compile(r"(?<![\w*])\*(?![\s*])(.+?)(?<![\s*])\*(?![\w*])|(?<!\w)_(?![\s_])(.+?)(?<![\s_])_(?!\w)")


def md_to_html(text: str) -> str:
    """Converte o Markdown simples que a Laris usa (negrito, itálico, listas, títulos, links)."""
    lines = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if m := _HEADING.match(line):
            line = f"**{m.group(1).strip()}**"
        else:
            line = _BULLET.sub(lambda m: f"{m.group(1)}• ", line)
        lines.append(line)
    out = html.escape("\n".join(lines), quote=False)
    out = _LINK.sub(lambda m: f'<a href="{m.group(2).replace(chr(34), "%22")}">{m.group(1)}</a>', out)
    out = _CODE.sub(r"<code>\1</code>", out)
    out = _BOLD.sub(lambda m: f"<b>{m.group(1) or m.group(2)}</b>", out)
    out = _ITALIC.sub(lambda m: f"<i>{m.group(1) or m.group(2)}</i>", out)
    return out


def strip_markdown(text: str) -> str:
    """Versão sem marcação (plano B se o Telegram recusar o HTML)."""
    text = _LINK.sub(r"\1 (\2)", text)
    text = re.sub(r"\*\*|__|`", "", text)
    return _BULLET.sub(lambda m: f"{m.group(1)}• ", text)


def split_message(text: str, limit: int = MAX_LENGTH) -> list[str]:
    """Quebra textos longos em parágrafos (ou linhas) sem passar do limite do Telegram."""
    if len(text) <= limit:
        return [text]
    parts, current = [], ""
    for block in re.split(r"(\n\n|\n)", text):
        if len(current) + len(block) > limit and current:
            parts.append(current.strip("\n"))
            current = ""
        while len(block) > limit:  # bloco gigante sem quebra de linha
            parts.append(block[:limit])
            block = block[limit:]
        current += block
    if current.strip():
        parts.append(current.strip("\n"))
    return parts


def _brl(value: int | None) -> str:
    return f"R$ {value:,.0f}".replace(",", ".") if value else "—"


def _num(value: float) -> str:
    return f"{value:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".").removesuffix(",0")


def property_block(p: dict, site_url: str | None = None) -> str:
    """Resumo de um imóvel citado pela Laris, no lugar dos cards do chat web."""
    f = p.get("features") or {}
    where = p["neighborhood"] if p["neighborhood"] == p["city"] else f"{p['neighborhood']}, {p['city']}"
    title = f"🏢 <b>{html.escape(p['id'])} · {html.escape(p['property_type'].capitalize())}</b>"
    details = [html.escape(where), f"{_num(p['area_m2'])} m²"]
    if f.get("docas"):
        details.append(f"{f['docas']} docas")
    elif p.get("parking"):
        details.append(f"{p['parking']} vagas")
    lines = [title, " · ".join(details)]
    if p["purpose"] == "aluguel":
        price = f"Aluguel: <b>{_brl(p['price'])}/mês</b>"
        extras = (p.get("condo_fee") or 0) + (p.get("iptu") or 0)
        if extras:
            price += f" (total {_brl(p['price'] + extras)} com condomínio e IPTU)"
        lines.append(price)
    else:
        lines.append(f"Venda: <b>{_brl(p['price'])}</b>")
    if leased := f.get("locado"):
        lines.append(
            f"Locado para {html.escape(leased['inquilino'])} até {leased['contrato_ate']} · "
            f"{_num(p.get('estimated_yield') or 0)}% a.a. estimado"
        )
    if site_url:
        lines.append(f'<a href="{site_url.rstrip("/")}/imovel-{p["id"].lower()}.html">Ver no site</a>')
    return "\n".join(lines)

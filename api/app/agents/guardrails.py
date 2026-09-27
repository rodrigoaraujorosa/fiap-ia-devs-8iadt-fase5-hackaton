"""Detecção de tentativas típicas de prompt injection nas mensagens do cliente.

A defesa principal está no prompt (a mensagem do cliente é conversa, não instrução) e no desenho das ferramentas
(só consultam imóveis, a agenda e o próprio lead). A detecção aqui não bloqueia nada: marca a mensagem, registra no
log e etiqueta o trace no Langfuse, para acompanhar as tentativas.
"""

import re

INJECTION = re.compile(
    r"ignor\w*\s+(?:\w+\s+){0,3}(?:instru\w*|regras|ordens|prompt)"
    r"|ignore\s+(?:\w+\s+){0,3}instructions"
    r"|system\s*prompt|prompt\s+(?:do\s+)?sistema|suas\s+instru\w+|your\s+instructions"
    r"|modo\s+(?:desenvolvedor|dev|deus)|developer\s+mode|jailbreak|\bDAN\b"
    r"|a\s+partir\s+de\s+agora\s+voc[eê]\s+(?:é|e|será|vai)|you\s+are\s+now|act\s+as|finja\s+(?:que|ser)"
    r"|repita\s+(?:o\s+texto|tudo|as\s+mensagens)\s+(?:acima|anterior)"
    r"|</?\s*(?:system|contexto_interno|instructions)\s*>",
    re.IGNORECASE,
)


def suspicious(text: str) -> bool:
    return bool(INJECTION.search(text or ""))

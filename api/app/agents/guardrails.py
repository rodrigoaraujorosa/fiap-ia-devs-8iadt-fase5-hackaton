"""Detecção de tentativas típicas de prompt injection nas mensagens do cliente.

A defesa principal está no prompt (a mensagem do cliente é conversa, não instrução) e no desenho das ferramentas
(só consultam imóveis, a agenda e o próprio lead). A detecção aqui não bloqueia nada: marca a mensagem, registra no
log e etiqueta o trace no Langfuse, para acompanhar as tentativas.
"""

import re
import unicodedata

INJECTION = re.compile(
    r"ignor\w*\s+(?:\w+\s+){0,3}(?:instru\w*|regras|ordens|prompt)"
    r"|ignore\s+(?:\w+\s+){0,3}instructions"
    r"|system\s*prompt|prompt\s+(?:do\s+)?sistema|suas\s+instru\w+|your\s+instructions"
    r"|modo\s+(?:desenvolvedor|dev|deus)|developer\s+mode|jailbreak|\bDAN\b"
    r"|a\s+partir\s+de\s+agora\s+voc[eê]\s+(?:é|e|ser[aá]|vai)|you\s+are\s+now|act\s+as|finja\s+(?:que|ser)"
    r"|repita\s+(?:o\s+texto|tudo|as\s+mensagens)\s+(?:acima|anterior)"
    r"|</?\s*(?:system|contexto_interno|instructions)\s*>",
    re.IGNORECASE,
)


# disfarces comuns: letras "glitch" (acentos empilhados), caracteres invisíveis, letras de largura total e leetspeak
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)
_LEET = str.maketrans("013457@$", "oieastas")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).translate(_INVISIBLE)
    return "".join(c for c in text if not unicodedata.combining(c)).translate(_LEET)


def suspicious(text: str) -> bool:
    text = text or ""
    return bool(INJECTION.search(text) or INJECTION.search(normalize(text)))

"""Mascaramento de dados pessoais antes de enviar traces ao Langfuse (serviço externo).

Telefone, e-mail, CPF e CNPJ viram marcadores. O banco da aplicação guarda os dados completos (o corretor precisa
deles); só a cópia que sai para a observabilidade é mascarada.
"""

import re
from typing import Any

PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[e-mail]"),
    (re.compile(r"(?<![\w/.])\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?![\w/])"), "[cnpj]"),
    (re.compile(r"(?<![\w.])\d{3}\.\d{3}\.\d{3}-\d{2}(?![\w])"), "[cpf]"),  # sem pontuação, cai como telefone
    (re.compile(r"(?<![\w])(?:\+?55[\s-]?)?\(?\d{2}\)?[\s-]?9?\d{4}[\s-]?\d{4}(?![\w])"), "[telefone]"),
]


def mask_text(text: str) -> str:
    for pattern, marker in PATTERNS:
        text = pattern.sub(marker, text)
    return text


def mask_pii(*, data: Any, **_: Any) -> Any:
    """Função de máscara do Langfuse: percorre strings, listas e dicionários."""
    if isinstance(data, str):
        return mask_text(data)
    if isinstance(data, dict):
        return {k: mask_pii(data=v) for k, v in data.items()}
    if isinstance(data, list | tuple):
        return [mask_pii(data=v) for v in data]
    return data

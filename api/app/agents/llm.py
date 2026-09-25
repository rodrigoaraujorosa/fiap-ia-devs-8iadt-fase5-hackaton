"""Cliente do Claude (SDK oficial da Anthropic) e helpers de conversa compartilhados pelos agentes."""

from functools import lru_cache
from typing import Any

import anthropic

from app.core.config import get_settings


@lru_cache
def claude() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)


def text_of(message: dict[str, Any]) -> str:
    content = message["content"]
    if isinstance(content, str):
        return content
    return " ".join(b["text"] for b in content if b.get("type") == "text")


def transcript(messages: list[dict[str, Any]], limit: int = 14) -> str:
    """Conversa em texto corrido (sem blocos de ferramenta), para os agentes auxiliares."""
    lines = []
    for m in messages[-limit:]:
        text = text_of(m).strip()
        if text:
            lines.append(f"{'Cliente' if m['role'] == 'user' else 'SDR'}: {text}")
    return "\n".join(lines)


def usage_details(response: anthropic.types.Message) -> dict[str, int]:
    u = response.usage
    return {
        "input": u.input_tokens,
        "output": u.output_tokens,
        "cache_read_input_tokens": u.cache_read_input_tokens or 0,
        "cache_creation_input_tokens": u.cache_creation_input_tokens or 0,
    }

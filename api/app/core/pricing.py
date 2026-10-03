"""Preços do Claude (API da Anthropic), em US$ por milhão de tokens, para calcular o custo de cada chamada.

Tabela de preços da Anthropic conferida em 03/10/2026. Ao trocar de modelo no .env, inclua o preço aqui:
modelo fora da tabela é registrado com custo zero (e um aviso no log).
"""

import logging

log = logging.getLogger(__name__)

PRICES: dict[str, tuple[float, float]] = {  # modelo: (entrada, saída)
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
CACHE_WRITE = 1.25  # gravar no cache (5 minutos) custa 25% a mais que a entrada normal
CACHE_READ = 0.10  # ler do cache custa 10% da entrada normal
_unknown: set[str] = set()


def rates(model: str | None) -> tuple[float, float] | None:
    """Preço do modelo; aceita o id com data no fim (claude-haiku-4-5-20251001)."""
    for name in sorted(PRICES, key=len, reverse=True):  # o mais específico primeiro (sonnet-5-5 antes de sonnet-5)
        if model and (model == name or model.startswith(f"{name}-")):
            return PRICES[name]
    if model and model not in _unknown:
        _unknown.add(model)
        log.warning("Modelo %s sem preço em app/core/pricing.py: custo registrado como zero", model)
    return None


def cost(model: str | None, usage: dict[str, int]) -> float:
    """Custo em US$ de uma chamada, a partir do uso devolvido pela API (llm.usage_details)."""
    price = rates(model)
    if not price:
        return 0.0
    price_in, price_out = price
    tokens_in = (
        usage.get("input", 0)
        + usage.get("cache_creation_input_tokens", 0) * CACHE_WRITE
        + usage.get("cache_read_input_tokens", 0) * CACHE_READ
    )
    return (tokens_in * price_in + usage.get("output", 0) * price_out) / 1_000_000


def cache_savings(model: str | None, cache_read_tokens: int) -> float:
    """Quanto as leituras do cache teriam custado a mais a preço cheio de entrada."""
    price = rates(model)
    return cache_read_tokens * price[0] * (1 - CACHE_READ) / 1_000_000 if price else 0.0

"""Cotação do dólar para o painel de observabilidade: PTAX de venda do Banco Central (API pública, sem chave).

A PTAX sai uma vez por dia útil, então a cotação fica em memória por algumas horas. Se o Banco Central não
responder, vale a última cotação obtida; sem nenhuma, a cotação fixa. A busca pode ser desligada na tela de
configurações, que também define a cotação fixa (o .env traz os valores iniciais: USD_BRL_LIVE e USD_BRL).
"""

import logging
import threading
import time
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.services.app_config import get_exchange_config

log = logging.getLogger(__name__)

PTAX_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarPeriodo(dataInicial=@inicio,dataFinalCotacao=@fim)"
)
CACHE_SECONDS = 6 * 3600
RETRY_SECONDS = 600  # depois de uma falha, espera antes de tentar de novo (o painel não fica lento)
LOOKBACK_DAYS = 10  # cobre fins de semana e feriados prolongados, quando não há cotação

_lock = threading.Lock()
_quote: dict | None = None  # última cotação obtida
_next_try = 0.0


def _fetch() -> dict:
    today = datetime.now()
    # a URL vai montada à mão: o serviço do Banco Central recusa o espaço codificado como "+" (padrão do httpx)
    query = (
        f"?@inicio='{today - timedelta(days=LOOKBACK_DAYS):%m-%d-%Y}'&@fim='{today:%m-%d-%Y}'"
        "&$top=1&$orderby=dataHoraCotacao%20desc&$format=json&$select=cotacaoVenda,dataHoraCotacao"
    )
    response = httpx.get(PTAX_URL + query, timeout=5)
    response.raise_for_status()
    latest = response.json()["value"][0]
    return {"rate": float(latest["cotacaoVenda"]), "source": "ptax", "date": latest["dataHoraCotacao"][:10]}


def usd_brl(db: Session | None = None) -> dict:
    """{"rate", "source": "ptax" | "config", "date": dia da cotação ou None, "live": busca ligada}."""
    global _quote, _next_try
    config = get_exchange_config(db)
    fixed = {"rate": config.rate, "source": "config", "date": None, "live": config.live}
    if not config.live:
        return fixed
    with _lock:
        if time.monotonic() >= _next_try:
            try:
                _quote = _fetch()
                _next_try = time.monotonic() + CACHE_SECONDS
            except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
                log.warning("Cotação do dólar indisponível no Banco Central (%s)", type(exc).__name__)
                _next_try = time.monotonic() + RETRY_SECONDS
        return {**_quote, "live": True} if _quote else fixed


def reset() -> None:
    """Esquece a cotação em memória (testes)."""
    global _quote, _next_try
    with _lock:
        _quote, _next_try = None, 0.0

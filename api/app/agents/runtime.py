"""Ciclo de vida do grafo: pool de conexões + checkpointer Postgres (memória conversacional)."""

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.agents.graph import build_graph
from app.core.config import get_settings

_pool: ConnectionPool | None = None
_graph = None


def start() -> None:
    global _pool, _graph
    if _graph is not None:
        return
    _pool = ConnectionPool(
        conninfo=get_settings().checkpoint_db_url,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
    )
    checkpointer = PostgresSaver(_pool)
    checkpointer.setup()  # cria as tabelas de checkpoint (idempotente)
    _graph = build_graph(checkpointer)


def stop() -> None:
    global _pool, _graph
    if _pool is not None:
        _pool.close()
    _pool, _graph = None, None


def get_graph():
    if _graph is None:
        start()
    return _graph

import os
from pathlib import Path

from sqlalchemy import create_engine, make_url, text

from app.core.config import Settings

# testes nunca enviam e-mail de verdade: o SMTP do .env (ex.: Hostinger) é trocado pelo Mailpit local.
# Variáveis de ambiente têm prioridade sobre o .env; isso precisa rodar antes de importar o app.
os.environ.update(SMTP_HOST="127.0.0.1", SMTP_PORT="1025", SMTP_USER="", SMTP_PASSWORD="", SMTP_SSL="false",
                  SMTP_STARTTLS="false")  # fmt: skip
os.environ["ENVIRONMENT"] = "test"  # traces dos testes separados no Langfuse (o painel mostra só o ambiente do app)
os.environ["USD_BRL_LIVE"] = "false"  # sem consulta ao Banco Central nos testes (test_insights simula a resposta)
# o login do .env (senha de administrador, Google) não vale nos testes: tudo aberto, e cada teste liga o que precisa
os.environ.update(ADMIN_PASSWORD="", GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="", ADMIN_EMAILS="", SESSION_SECRET="")

# Banco próprio dos testes (<banco>_test, no mesmo Postgres): nenhum teste mexe nos leads nem nas configurações
# do app que está rodando. Criado, migrado e semeado na primeira execução (sem LLM: os embeddings são locais).
APP_DB = make_url(Settings().database_url)
TEST_DB = APP_DB.set(database=f"{APP_DB.database}_test")
os.environ["DATABASE_URL"] = TEST_DB.render_as_string(hide_password=False)
DB_READY: str | None = None  # motivo para pular os testes de integração, se o banco não estiver disponível


def _prepare_test_database() -> str | None:
    try:
        admin = create_engine(APP_DB, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_DB.database})
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{TEST_DB.database}"'))
        admin.dispose()
    except Exception:
        return "Banco indisponível — rode `docker compose up -d db`"

    from alembic.config import Config

    from alembic import command

    api_dir = Path(__file__).resolve().parents[1]
    cfg = Config(str(api_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(api_dir / "alembic"))
    command.upgrade(cfg, "head")

    from sqlalchemy import func, select

    from app.db.session import SessionLocal
    from app.models import Lead, Property
    from app.services.demo import reset_demo
    from scripts.seed import seed_brokers, seed_properties, seed_slots

    with SessionLocal() as db:
        seed_properties(db)  # idempotente: só na primeira vez insere e gera embeddings
        seed_brokers(db)
        seed_slots(db)
        if not db.scalar(select(func.count()).select_from(Lead)):
            reset_demo(db)  # alguns testes precisam de leads existentes
        if not db.scalar(select(func.count()).select_from(Property)):
            return "Base de imóveis vazia no banco de testes"
    return None


DB_READY = _prepare_test_database()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def db():
    """Testes de integração: usam o banco <banco>_test do Postgres do docker compose."""
    if DB_READY:
        pytest.skip(DB_READY)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="session")
def client(db):
    return TestClient(app)

import os

# testes nunca enviam e-mail de verdade: o SMTP do .env (ex.: Hostinger) é trocado pelo Mailpit local.
# Variáveis de ambiente têm prioridade sobre o .env; isso precisa rodar antes de importar o app.
os.environ.update(SMTP_HOST="127.0.0.1", SMTP_PORT="1025", SMTP_USER="", SMTP_PASSWORD="", SMTP_SSL="false",
                  SMTP_STARTTLS="false")  # fmt: skip

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select, text  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Property  # noqa: E402


@pytest.fixture(scope="session")
def db():
    """Testes de integração: exigem o Postgres do docker compose rodando e o seed aplicado."""
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("Banco indisponível — rode `docker compose up -d db`")
    if not session.scalar(select(func.count()).select_from(Property)):
        pytest.skip("Base vazia — rode `uv run python -m scripts.seed`")
    yield session
    session.close()


@pytest.fixture(scope="session")
def client(db):
    return TestClient(app)

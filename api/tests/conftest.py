import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.db.session import SessionLocal
from app.main import app
from app.models import Property


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

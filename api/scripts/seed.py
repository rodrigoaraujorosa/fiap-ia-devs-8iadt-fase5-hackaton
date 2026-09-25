"""Popula o banco com a base simulada: imóveis (+ embeddings), corretores e agenda.

Uso:
    uv run python -m scripts.seed            # idempotente (só insere o que falta)
    uv run python -m scripts.seed --reset    # apaga tudo (inclusive leads) e recria
    uv run python -m scripts.seed --demo     # + recria os leads de demonstração (data/demo_leads.json)
"""

import argparse
import json

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Broker, Property
from app.services.demo import PREBOOKED_RATIO, SLOT_SEED, reset_demo
from app.services.embeddings import embed_texts
from app.services.scheduling import ensure_future_slots


def load_json(name: str) -> list[dict]:
    return json.loads((get_settings().data_dir / name).read_text(encoding="utf-8"))


def reset(db: Session) -> None:
    tables = "appointments, slots, brokers, summaries, messages, leads, properties"
    db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    db.commit()
    print("Banco limpo.")


def seed_properties(db: Session) -> None:
    existing = set(db.scalars(select(Property.id)))
    new = [Property(**p) for p in load_json("properties.json") if p["id"] not in existing]
    db.add_all(new)
    db.commit()
    print(f"Imóveis: {len(new)} inseridos ({len(existing)} já existiam).")

    pending = db.scalars(select(Property).where(Property.embedding.is_(None))).all()
    if pending:
        print(f"Gerando embeddings de {len(pending)} imóveis (primeira execução baixa o modelo ~220 MB)...")
        for prop, vec in zip(pending, embed_texts([p.search_text() for p in pending]), strict=True):
            prop.embedding = vec
        db.commit()
        print("Embeddings gerados.")


def seed_brokers(db: Session) -> None:
    existing = {b.email for b in db.scalars(select(Broker))}
    new = [Broker(**b) for b in load_json("brokers.json") if b["email"] not in existing]
    db.add_all(new)
    db.commit()
    print(f"Corretores: {len(new)} inseridos ({len(existing)} já existiam).")


def seed_slots(db: Session) -> None:
    created = ensure_future_slots(db, prebooked_ratio=PREBOOKED_RATIO, seed=SLOT_SEED)
    print(f"Horários: {created} criados para os próximos {get_settings().slot_days_ahead} dias úteis.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="apaga todos os dados antes de popular")
    parser.add_argument("--demo", action="store_true", help="recria os leads de demonstração (apaga os atuais)")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.reset:
            reset(db)
        seed_properties(db)
        seed_brokers(db)
        seed_slots(db)
        if args.demo:
            result = reset_demo(db)
            print(f"Demo: {result['leads']} leads e {result['appointments']} agendamentos criados.")
    print("Seed concluído ✅")


if __name__ == "__main__":
    main()

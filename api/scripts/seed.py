"""Popula o banco com a base simulada: imóveis (+ embeddings), corretores e agenda.

Uso:
    uv run python -m scripts.seed            # idempotente (só insere o que falta)
    uv run python -m scripts.seed --reset    # apaga tudo (inclusive leads) e recria
"""

import argparse
import json
import os
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Broker, Property, Slot
from app.services.embeddings import embed_texts

# Local: <repo>/data | Docker: /data (volume montado)
DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
TZ = ZoneInfo("America/Sao_Paulo")
SLOT_DAYS = 10
SLOT_HOURS = range(9, 18)
PREBOOKED_RATIO = 0.25


def load_json(name: str) -> list[dict]:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


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


def seed_brokers(db: Session) -> list[Broker]:
    existing = {b.email for b in db.scalars(select(Broker))}
    new = [Broker(**b) for b in load_json("brokers.json") if b["email"] not in existing]
    db.add_all(new)
    db.commit()
    print(f"Corretores: {len(new)} inseridos ({len(existing)} já existiam).")
    return list(db.scalars(select(Broker)))


def business_days(start: date, count: int) -> list[date]:
    days, d = [], start
    while len(days) < count:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days.append(d)
    return days


def seed_slots(db: Session, brokers: list[Broker]) -> None:
    rng = random.Random(7)
    existing = {(s.broker_id, s.start_at) for s in db.scalars(select(Slot))}
    created = 0
    for broker in brokers:
        for day in business_days(datetime.now(TZ).date(), SLOT_DAYS):
            for hour in SLOT_HOURS:
                start = datetime.combine(day, time(hour), tzinfo=TZ)
                if (broker.id, start) in existing:
                    continue
                db.add(
                    Slot(
                        broker_id=broker.id,
                        start_at=start,
                        end_at=start + timedelta(hours=1),
                        is_booked=rng.random() < PREBOOKED_RATIO,
                    )
                )
                created += 1
    db.commit()
    print(f"Horários: {created} criados para os próximos {SLOT_DAYS} dias úteis.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="apaga todos os dados antes de popular")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.reset:
            reset(db)
        seed_properties(db)
        brokers = seed_brokers(db)
        seed_slots(db, brokers)
    print("Seed concluído ✅")


if __name__ == "__main__":
    main()

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents import runtime
from app.api.routes import chat, health, leads, properties
from app.core import observability
from app.core.config import get_settings
from app.jobs import scheduler

settings = get_settings()
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    runtime.start()  # grafo + checkpointer Postgres
    scheduler.start()  # follow-up automático + reposição da agenda
    yield
    scheduler.stop()
    runtime.stop()
    observability.flush()


app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(properties.router)
app.include_router(chat.router)
app.include_router(leads.router)

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents import runtime
from app.agents.llm import AIPausedError
from app.api.routes import admin, auth, chat, health, leads, properties, telegram, widget
from app.core import observability
from app.core.config import get_settings
from app.jobs import scheduler
from app.services import telegram as telegram_bot

settings = get_settings()
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    runtime.start()  # grafo + checkpointer Postgres
    scheduler.start()  # follow-up automático + reposição da agenda
    telegram_bot.start()  # bot do Telegram (polling local ou webhook), se houver token
    yield
    telegram_bot.stop()
    scheduler.stop()
    runtime.stop()
    observability.flush()


app = FastAPI(title=settings.app_name, version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AIPausedError)
async def ai_paused(_: Request, exc: AIPausedError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(properties.router)
app.include_router(chat.router)
app.include_router(leads.router)
app.include_router(admin.router)
app.include_router(telegram.router)
app.include_router(widget.router)

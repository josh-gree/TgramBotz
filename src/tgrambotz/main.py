import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from tgrambotz.bot.handlers import (
    cmd_demo,
    cmd_demo_diff,
    cmd_new,
    cmd_start,
    cmd_switch,
    cmd_workspaces,
    on_message,
)
from tgrambotz.config import settings
from tgrambotz.db.database import create_tables
from tgrambotz.db.models import ChatState, Event, Session  # noqa: F401 — register models

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_ptb_app: Application | None = None


def _build_app() -> Application:
    builder = Application.builder().token(settings.telegram_token)
    if settings.webhook_url:
        builder = builder.updater(None)  # webhook mode — disable built-in polling
    app = builder.build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("workspaces", cmd_workspaces))
    app.add_handler(CommandHandler("switch", cmd_switch))
    app.add_handler(CommandHandler("demo", cmd_demo))
    app.add_handler(CommandHandler("demo_diff", cmd_demo_diff))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    return app


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    global _ptb_app

    await create_tables()
    _ptb_app = _build_app()
    await _ptb_app.initialize()
    await _ptb_app.start()

    if settings.webhook_url:
        webhook_url = f"{settings.webhook_url.rstrip('/')}/webhook"
        await _ptb_app.bot.set_webhook(url=webhook_url)
        logger.info("Webhook registered: %s", webhook_url)
    else:
        logger.info("No WEBHOOK_URL set — running in webhook-receive-only mode (use polling entrypoint for local dev)")

    yield

    await _ptb_app.stop()
    await _ptb_app.shutdown()


app = FastAPI(lifespan=lifespan)


@app.post("/webhook")
async def webhook(request: Request) -> Response:
    if _ptb_app is None:
        return Response(status_code=503)
    data = await request.json()
    update = Update.de_json(data, _ptb_app.bot)
    await _ptb_app.process_update(update)
    return Response(status_code=200)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}

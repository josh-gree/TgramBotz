"""Polling-mode entrypoint for local development.

Usage:
    uv run python -m tgrambotz
"""
import asyncio
import logging

from telegram.ext import Application

from tgrambotz.db.database import create_tables
from tgrambotz.db.models import ChatState, Event, Session  # noqa: F401
from tgrambotz.main import _build_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


async def on_error(update, context) -> None:
    logger.exception("Unhandled exception in handler", exc_info=context.error)


async def main() -> None:
    await create_tables()

    ptb_app: Application = _build_app()
    ptb_app.add_error_handler(on_error)

    logger.info("Starting bot in polling mode…")
    async with ptb_app:
        await ptb_app.start()
        await ptb_app.updater.start_polling(drop_pending_updates=True)
        logger.info("Bot is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()
        await ptb_app.updater.stop()
        await ptb_app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped.")

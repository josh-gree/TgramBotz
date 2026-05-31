import asyncio
import logging
import os

from telegram import Update
from telegram.ext import Application, MessageHandler, filters

from tgrambotz.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


async def main() -> None:
    if os.environ.get("SANDBOX_MODE"):
        from tgrambotz.local_agent import LocalOpenCodeAgent
        agent = LocalOpenCodeAgent()
    else:
        from tgrambotz.agent import OpenCodeAgent
        agent = OpenCodeAgent()

    await agent.start()

    app = Application.builder().token(settings.telegram_token).build()

    async def on_message(update: Update, context) -> None:
        text = update.message.text
        chat_id = update.effective_chat.id
        log.info("chat=%s: %s", chat_id, text[:120])

        await context.bot.send_chat_action(chat_id, "typing")

        async def on_tool(msg: str) -> None:
            await context.bot.send_message(chat_id, msg, parse_mode="Markdown")

        async def on_text(text: str) -> None:
            await update.message.reply_text(text)

        await agent.chat(text, on_tool=on_tool, on_text=on_text)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        log.info("Bot running — press Ctrl+C to stop")
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()
        await agent.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped.")

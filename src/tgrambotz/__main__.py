import asyncio
import logging
import os
import time

from telegram import Update
from telegram.ext import Application, MessageHandler, filters

from tgrambotz.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

_EDIT_INTERVAL = 0.5  # seconds between Telegram edits


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
        msg_text = update.message.text
        chat_id = update.effective_chat.id
        log.info("chat=%s: %s", chat_id, msg_text[:120])

        await context.bot.send_chat_action(chat_id, "typing")

        # Keep typing indicator alive every 4s until first message arrives
        first_output = asyncio.Event()
        async def _keep_typing():
            while not first_output.is_set():
                await asyncio.sleep(4)
                if not first_output.is_set():
                    try:
                        await context.bot.send_chat_action(chat_id, "typing")
                    except Exception:
                        pass
        typing_task = asyncio.create_task(_keep_typing())

        # Streaming state for reasoning and response
        reasoning_msg_id = None
        reasoning_buf: list[str] = []
        reasoning_last_edit = 0.0

        response_msg_id = None
        response_buf: list[str] = []
        response_last_edit = 0.0

        async def on_reasoning_delta(delta: str) -> None:
            nonlocal reasoning_msg_id, reasoning_last_edit
            first_output.set()
            reasoning_buf.append(delta)
            html = f"<blockquote>💭 {_esc(''.join(reasoning_buf))}</blockquote>"
            now = time.monotonic()
            if reasoning_msg_id is None:
                sent = await context.bot.send_message(chat_id, html, parse_mode="HTML")
                reasoning_msg_id = sent.message_id
                reasoning_last_edit = now
            elif now - reasoning_last_edit >= _EDIT_INTERVAL:
                try:
                    await context.bot.edit_message_text(html, chat_id, reasoning_msg_id, parse_mode="HTML")
                    reasoning_last_edit = now
                except Exception:
                    pass

        async def on_text_delta(delta: str) -> None:
            nonlocal response_msg_id, response_last_edit
            first_output.set()
            response_buf.append(delta)
            full = "".join(response_buf)
            now = time.monotonic()
            if response_msg_id is None:
                sent = await update.message.reply_text(full)
                response_msg_id = sent.message_id
                response_last_edit = now
            elif now - response_last_edit >= _EDIT_INTERVAL:
                try:
                    await context.bot.edit_message_text(full, chat_id, response_msg_id)
                    response_last_edit = now
                except Exception:
                    pass

        await agent.chat(
            msg_text,
            on_reasoning_delta=on_reasoning_delta,
            on_text_delta=on_text_delta,
        )
        typing_task.cancel()

        # Final edits to ensure complete content is shown
        if reasoning_msg_id and reasoning_buf:
            try:
                html = f"<blockquote>💭 {_esc(''.join(reasoning_buf))}</blockquote>"
                await context.bot.edit_message_text(html, chat_id, reasoning_msg_id, parse_mode="HTML")
            except Exception:
                pass
        if response_msg_id and response_buf:
            try:
                await context.bot.edit_message_text(
                    "".join(response_buf), chat_id, response_msg_id
                )
            except Exception:
                pass

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

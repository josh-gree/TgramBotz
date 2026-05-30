import asyncio

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from tgrambotz.db.database import async_session_factory
from tgrambotz.db.models import ChatState, Event, Session


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Welcome to TgramBotz!\n\n"
        "Commands:\n"
        "  /new <name> — create a workspace\n"
        "  /workspaces — list workspaces\n"
        "  /switch <n> — switch active workspace\n\n"
        "Send any message to interact with your active workspace."
    )


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    name = " ".join(context.args) if context.args else ""
    if not name:
        await update.message.reply_text("Usage: /new <workspace-name>")
        return

    async with async_session_factory() as db:
        session = Session(name=name, telegram_chat_id=chat_id)
        db.add(session)
        await db.commit()
        await db.refresh(session)

        state = await db.get(ChatState, chat_id)
        if state is None:
            state = ChatState(chat_id=chat_id, active_session_id=session.id)
            db.add(state)
        else:
            state.active_session_id = session.id
        await db.commit()

    await update.message.reply_text(f"✅ Workspace <b>{name}</b> created and activated.", parse_mode="HTML")


async def cmd_workspaces(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    async with async_session_factory() as db:
        result = await db.execute(
            select(Session).where(Session.telegram_chat_id == chat_id)
        )
        sessions = result.scalars().all()
        state = await db.get(ChatState, chat_id)
        active_id = state.active_session_id if state else None

    if not sessions:
        await update.message.reply_text("No workspaces yet. Use /new <name> to create one.")
        return

    lines = []
    for i, s in enumerate(sessions, 1):
        marker = "▶️" if s.id == active_id else "  "
        lines.append(f"{marker} {i}. {s.name}")
    await update.message.reply_text("\n".join(lines))


async def cmd_switch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Usage: /switch <number>")
        return
    try:
        n = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please provide a number.")
        return

    async with async_session_factory() as db:
        result = await db.execute(
            select(Session).where(Session.telegram_chat_id == chat_id)
        )
        sessions = result.scalars().all()
        if n < 1 or n > len(sessions):
            await update.message.reply_text(f"Invalid number. You have {len(sessions)} workspace(s).")
            return
        target = sessions[n - 1]
        state = await db.get(ChatState, chat_id)
        if state is None:
            state = ChatState(chat_id=chat_id, active_session_id=target.id)
            db.add(state)
        else:
            state.active_session_id = target.id
        await db.commit()

    await update.message.reply_text(f"✅ Switched to workspace <b>{target.name}</b>.", parse_mode="HTML")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    text = update.message.text

    # Persist — don't let a DB failure block the reply
    try:
        async with async_session_factory() as db:
            state = await db.get(ChatState, chat_id)
            session_id = state.active_session_id if state else None
            db.add(Event(session_id=session_id, chat_id=chat_id, type="USER_MESSAGE", payload=text))
            await db.commit()
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Failed to persist message")

    await update.message.reply_text(f"Echo: {text}")


async def cmd_demo_diff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    bot = context.bot

    # 1 — Compact summary card (what we'd show inline in the event stream)
    await bot.send_message(chat_id, parse_mode=ParseMode.HTML, text=(
        "✏️ <b>3 files changed</b>\n\n"
        "📄 <code>auth.py</code>          <b>+42</b> <s>-8</s>\n"
        "📄 <code>tests/test_auth.py</code>  <b>+91</b> <s>-12</s>\n"
        "📄 <code>config.py</code>         <b>+6</b> <s>-1</s>"
    ))
    await asyncio.sleep(0.5)

    # 2 — Single file diff in a code block (short enough to fit)
    await bot.send_message(chat_id, parse_mode=ParseMode.HTML, text=(
        "📄 <code>config.py</code>  <b>+6 -1</b>\n\n"
        "<pre><code class=\"language-diff\">"
        " from pydantic_settings import BaseSettings\n"
        " \n"
        " class Settings(BaseSettings):\n"
        "     telegram_token: str\n"
        "     webhook_url: str = \"\"\n"
        "-    api_key: str = \"\"\n"
        "+    e2b_api_key: str = \"\"\n"
        "+    openrouter_api_key: str = \"\"\n"
        "+    openrouter_model: str = \"anthropic/claude-sonnet-4-5\"\n"
        "+    database_url: str = \"sqlite+aiosqlite:///./tgrambotz.db\"\n"
        "+    max_sandbox_idle_mins: int = 30\n"
        "+    snapshot_on_complete: bool = True"
        "</code></pre>"
    ))
    await asyncio.sleep(0.5)

    # 3 — Bigger diff with View Full button
    diff_preview = (
        "📄 <code>auth.py</code>  <b>+42 -8</b>\n\n"
        "<pre><code class=\"language-diff\">"
        "-def authenticate(token: str) -> bool:\n"
        "-    return token == SECRET\n"
        "+async def authenticate(\n"
        "+    token: str,\n"
        "+    db: AsyncSession,\n"
        "+) -> User | None:\n"
        "+    result = await db.execute(\n"
        "+        select(User).where(User.token == token)\n"
        "+    )\n"
        "+    return result.scalar_one_or_none()\n"
        " \n"
        "-def require_auth(f):\n"
        "-    def wrapper(*args, **kwargs):\n"
        "-        if not authenticate(args[0]):\n"
        "-            raise PermissionError\n"
        "-        return f(*args, **kwargs)\n"
        "-    return wrapper\n"
        "+def require_auth(f):\n"
        "+    async def wrapper(*args, **kwargs):\n"
        "+        user = await authenticate(args[0], args[1])\n"
        "+        if user is None:\n"
        "+            raise HTTPException(401)\n"
        "+        return await f(*args, user=user, **kwargs)\n"
        "+    return wrapper"
        "</code></pre>"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📋 Full diff", callback_data="full_diff:auth.py"),
        InlineKeyboardButton("↩️ Revert", callback_data="revert:auth.py"),
    ]])
    await bot.send_message(chat_id, parse_mode=ParseMode.HTML, text=diff_preview, reply_markup=keyboard)
    await asyncio.sleep(0.5)

    # 4 — Long bash output (what streaming looks like)
    await bot.send_message(chat_id, parse_mode=ParseMode.HTML, text=(
        "🧪 <code>pytest tests/ -v</code>\n\n"
        "<pre>"
        "PASSED tests/test_auth.py::test_valid_token\n"
        "PASSED tests/test_auth.py::test_expired_token\n"
        "PASSED tests/test_auth.py::test_missing_token\n"
        "PASSED tests/test_auth.py::test_revoked_token\n"
        "PASSED tests/test_auth.py::test_admin_role\n"
        "PASSED tests/test_auth.py::test_user_role\n"
        "PASSED tests/test_auth.py::test_guest_role\n"
        "PASSED tests/test_sessions.py::test_create\n"
        "PASSED tests/test_sessions.py::test_list\n"
        "PASSED tests/test_sessions.py::test_switch\n"
        "PASSED tests/test_sessions.py::test_delete\n"
        "PASSED tests/test_api.py::test_health\n"
        "PASSED tests/test_api.py::test_webhook\n"
        "\n"
        "124 passed in 3.41s"
        "</pre>"
    ))


async def cmd_demo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    bot = context.bot

    # 1 — Text styles
    await bot.send_message(chat_id, parse_mode=ParseMode.HTML, text=(
        "<b>Bold</b>  <i>Italic</i>  <u>Underline</u>  <s>Strikethrough</s>\n"
        "<b><i>Bold italic</i></b>  <tg-spoiler>Spoiler text</tg-spoiler>"
    ))
    await asyncio.sleep(0.4)

    # 2 — Inline code + code block
    await bot.send_message(chat_id, parse_mode=ParseMode.HTML, text=(
        "Inline: <code>git commit -m \"fix\"</code>\n\n"
        "Block:\n"
        "<pre>def hello():\n"
        "    print(\"Hello, world!\")</pre>"
    ))
    await asyncio.sleep(0.4)

    # 3 — Syntax-highlighted block
    await bot.send_message(chat_id, parse_mode=ParseMode.HTML, text=(
        "<pre><code class=\"language-python\">"
        "async def on_message(update):\n"
        "    text = update.message.text\n"
        "    await update.message.reply_text(text)"
        "</code></pre>"
    ))
    await asyncio.sleep(0.4)

    # 4 — Agent event stream mock
    await bot.send_message(chat_id, parse_mode=ParseMode.HTML, text=(
        "🧠 <i>Thinking…</i>\n\n"
        "📖 <code>auth.py</code>\n"
        "📖 <code>tests/test_auth.py</code>\n\n"
        "✏️ <code>auth.py</code>  <b>+42 -8</b>\n\n"
        "🧪 <code>pytest tests/</code>\n\n"
        "✅ <b>Done</b> — 124 passed, 0 failed"
    ))
    await asyncio.sleep(0.4)

    # 5 — Blockquote
    await bot.send_message(chat_id, parse_mode=ParseMode.HTML, text=(
        "<blockquote>The user said:\nFix the failing auth tests</blockquote>\n\n"
        "On it."
    ))
    await asyncio.sleep(0.4)

    # 6 — Link + mention styles
    await bot.send_message(chat_id, parse_mode=ParseMode.HTML, text=(
        '📎 <a href="https://github.com/josh-gree/TgramBotz">TgramBotz repo</a>\n\n'
        "Workspace: <b>backend</b>\n"
        "Status: <i>Running tests</i>\n"
        "Tool calls: <code>17</code>"
    ))
    await asyncio.sleep(0.4)

    # 7 — Inline keyboard buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data="approve"),
            InlineKeyboardButton("❌ Reject", callback_data="reject"),
        ],
        [
            InlineKeyboardButton("👁 View Diff", callback_data="diff"),
            InlineKeyboardButton("📋 Full Log", callback_data="log"),
        ],
    ])
    await bot.send_message(
        chat_id,
        parse_mode=ParseMode.HTML,
        text=(
            "⚠️ <b>Approval Required</b>\n\n"
            "The agent wants to run:\n"
            "<pre>docker compose down --volumes</pre>"
        ),
        reply_markup=keyboard,
    )
    await asyncio.sleep(0.4)

    # 8 — Status bar (the live edit-in-place style)
    msg = await bot.send_message(chat_id, parse_mode=ParseMode.HTML, text=(
        "┌ <b>Workspace:</b> backend\n"
        "│\n"
        "├ <b>Status:</b> Running pytest…\n"
        "│\n"
        "├ <b>Tool calls:</b> 17\n"
        "└ <b>Cost:</b> $0.14"
    ))
    await asyncio.sleep(1.2)
    # Edit it in place to show live update feel
    await msg.edit_text(parse_mode=ParseMode.HTML, text=(
        "┌ <b>Workspace:</b> backend\n"
        "│\n"
        "├ <b>Status:</b> ✅ Complete\n"
        "│\n"
        "├ <b>Tool calls:</b> 17\n"
        "└ <b>Cost:</b> $0.14"
    ))

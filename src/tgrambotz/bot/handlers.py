import asyncio
import time

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from tgrambotz.db.database import async_session_factory
from tgrambotz.db.models import ChatState, Event, Session


async def cmd_demo_grammar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Walk through the full design grammar — every event type and composition pattern."""
    chat_id = update.effective_chat.id
    bot = context.bot
    H = ParseMode.HTML
    GAP = 0.6

    async def section(title: str) -> None:
        await bot.send_message(chat_id, parse_mode=H,
            text=f"─────────────────────\n<b>{title}</b>")
        await asyncio.sleep(GAP)

    # ═══════════════════════════════════════════════════════════════════
    # 1. STATUS BAR — lives at the top, edited in place, never re-sent
    # ═══════════════════════════════════════════════════════════════════
    await section("1 · Status Bar  (edited in place)")

    s = await bot.send_message(chat_id, parse_mode=H, text=(
        "┌ <b>Workspace:</b> backend\n"
        "├ <b>Status:</b> Idle\n"
        "└ <b>Tools:</b> 0"
    ))
    await asyncio.sleep(1.0)
    await s.edit_text(parse_mode=H, text=(
        "┌ <b>Workspace:</b> backend\n"
        "├ <b>Status:</b> 🧠 Thinking…\n"
        "└ <b>Tools:</b> 0"
    ))
    await asyncio.sleep(1.0)
    await s.edit_text(parse_mode=H, text=(
        "┌ <b>Workspace:</b> backend\n"
        "├ <b>Status:</b> 📖 Reading files…\n"
        "└ <b>Tools:</b> 3"
    ))
    await asyncio.sleep(1.0)
    await s.edit_text(parse_mode=H, text=(
        "┌ <b>Workspace:</b> backend\n"
        "├ <b>Status:</b> 🧪 Running tests…\n"
        "└ <b>Tools:</b> 7"
    ))
    await asyncio.sleep(1.0)
    await s.edit_text(parse_mode=H, text=(
        "┌ <b>Workspace:</b> backend\n"
        "├ <b>Status:</b> ✅ Complete\n"
        "└ <b>Tools:</b> 9"
    ))
    await asyncio.sleep(GAP)

    # ═══════════════════════════════════════════════════════════════════
    # 2. THINK — brief inline reasoning, italic
    # ═══════════════════════════════════════════════════════════════════
    await section("2 · Think")

    await bot.send_message(chat_id, parse_mode=H, text=(
        "🧠 <i>Investigating the auth flow…</i>"
    ))
    await asyncio.sleep(GAP)
    # Longer thought
    await bot.send_message(chat_id, parse_mode=H, text=(
        "🧠 <i>The test is calling <code>authenticate()</code> with <code>await</code> "
        "but the function is synchronous. I need to make it async and fix the token "
        "comparison to use constant-time compare.</i>"
    ))
    await asyncio.sleep(GAP)

    # ═══════════════════════════════════════════════════════════════════
    # 3. READ — one line per file, View button opens Telegraph Instant View
    # ═══════════════════════════════════════════════════════════════════
    await section("3 · Read  (tap View to see content)")

    from tgrambotz.bot.telegraph import create_file_page

    auth_content = '''\
import hmac
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException
from .models import User

SECRET = "super-secret-key"

async def authenticate(token: str, db: AsyncSession) -> User | None:
    result = await db.execute(
        select(User).where(User.token == token)
    )
    return result.scalar_one_or_none()

def require_auth(f):
    async def wrapper(*args, **kwargs):
        user = await authenticate(args[0], args[1])
        if user is None:
            raise HTTPException(status_code=401)
        return await f(*args, user=user, **kwargs)
    return wrapper

async def revoke_token(token: str, db: AsyncSession) -> None:
    await db.execute(
        update(User)
        .where(User.token == token)
        .values(token=None)
    )
    await db.commit()
'''

    test_content = '''\
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_valid_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/me", headers={"Authorization": "Bearer valid"})
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_expired_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/me", headers={"Authorization": "Bearer expired"})
    assert r.status_code == 401

@pytest.mark.asyncio
async def test_missing_token():
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/me")
    assert r.status_code == 401
'''

    url_auth = await create_file_page("auth.py", auth_content)
    url_test = await create_file_page("tests/test_auth.py", test_content)

    await bot.send_message(chat_id, parse_mode=H,
        text="📖 <code>auth.py</code>  <i>28 lines</i>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("👁 View", url=url_auth),
        ]]),
    )
    await asyncio.sleep(0.5)

    await bot.send_message(chat_id, parse_mode=H,
        text="📖 <code>tests/test_auth.py</code>  <i>31 lines</i>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("👁 View", url=url_test),
        ]]),
    )
    await asyncio.sleep(0.5)

    # Read with line range — smaller View scope
    await bot.send_message(chat_id, parse_mode=H,
        text="📖 <code>auth.py</code>  <i>lines 9–22</i>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("👁 View", url=url_auth),
        ]]),
    )
    await asyncio.sleep(GAP)

    # ═══════════════════════════════════════════════════════════════════
    # 4. SEARCH
    # ═══════════════════════════════════════════════════════════════════
    await section("4 · Search")

    await bot.send_message(chat_id, parse_mode=H, text=(
        "🔍 <code>authenticate</code>\n"
        "<i>6 matches across 3 files</i>"
    ))
    await asyncio.sleep(GAP)
    await bot.send_message(chat_id, parse_mode=H, text=(
        "🔍 <code>TODO|FIXME|HACK</code>\n"
        "<i>14 matches</i>"
    ))
    await asyncio.sleep(GAP)

    # ═══════════════════════════════════════════════════════════════════
    # 5. BASH — streams in place: pending → live output → done
    # ═══════════════════════════════════════════════════════════════════
    await section("5 · Bash  (streams in place)")

    # 5a. Short command
    b1 = await bot.send_message(chat_id, parse_mode=H, text=(
        "🧪 <code>pytest tests/ -v</code>\n<pre>running…</pre>"
    ))
    await asyncio.sleep(1.0)
    await b1.edit_text(parse_mode=H, text=(
        "🧪 <code>pytest tests/ -v</code>\n"
        "<pre>3 passed in 0.41s ✓</pre>"
    ))
    await asyncio.sleep(GAP)

    # 5b. Failing output
    b2 = await bot.send_message(chat_id, parse_mode=H, text=(
        "🧪 <code>pytest tests/ -v</code>\n<pre>running…</pre>"
    ))
    await asyncio.sleep(1.0)
    await b2.edit_text(parse_mode=H, text=(
        "🧪 <code>pytest tests/ -v</code>\n"
        "<pre>"
        "FAILED test_auth.py::test_valid_token\n"
        "FAILED test_auth.py::test_expired_token\n"
        "PASSED test_auth.py::test_missing_token\n"
        "\n"
        "2 failed, 1 passed in 0.41s ✗"
        "</pre>"
    ))
    await asyncio.sleep(GAP)

    # 5c. Long output — truncated with line count
    await bot.send_message(chat_id, parse_mode=H, text=(
        "🧪 <code>npm run build</code>\n"
        "<pre>"
        "… 847 lines\n"
        "webpack 5.91 compiled successfully\n"
        "Build time: 12.4s"
        "</pre>"
    ))
    await asyncio.sleep(GAP)

    # ═══════════════════════════════════════════════════════════════════
    # 6. PATCH — small diffs inline, large diffs → button
    # ═══════════════════════════════════════════════════════════════════
    await section("6 · Patch")

    diff_url = "https://diffshub.com/josh-gree/TgramBotz/commit/87c31a5"

    # 6a. Tiny change — show inline
    await bot.send_message(chat_id, parse_mode=H, text=(
        "✏️ <code>config.py</code>  <b>+1 -1</b>\n\n"
        "<pre><code class=\"language-diff\">"
        "-    api_key: str = \"\"\n"
        "+    e2b_api_key: str = \"\""
        "</code></pre>"
    ))
    await asyncio.sleep(GAP)

    # 6b. Medium change — summary + button
    await bot.send_message(chat_id, parse_mode=H,
        text=(
            "✏️ <code>auth.py</code>  <b>+12 -4</b>\n\n"
            "<pre><code class=\"language-diff\">"
            "-def authenticate(token: str) -> bool:\n"
            "-    return token == SECRET\n"
            "+async def authenticate(token: str) -> bool:\n"
            "+    return hmac.compare_digest(token, SECRET)"
            "</code></pre>"
        ),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔍 Full Diff", url=diff_url),
            InlineKeyboardButton("↩️ Revert", callback_data="revert:auth.py"),
        ]]),
    )
    await asyncio.sleep(GAP)

    # 6c. Multi-file summary card
    await bot.send_message(chat_id, parse_mode=H,
        text=(
            "✏️ <b>4 files changed</b>\n\n"
            "  <code>auth.py</code>              <b>+42</b> <s>-8</s>\n"
            "  <code>tests/test_auth.py</code>    <b>+91</b> <s>-12</s>\n"
            "  <code>models/user.py</code>        <b>+18</b> <s>-3</s>\n"
            "  <code>config.py</code>             <b>+1</b> <s>-1</s>"
        ),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔍 View All Changes", url=diff_url),
        ]]),
    )
    await asyncio.sleep(GAP)

    # ═══════════════════════════════════════════════════════════════════
    # 7. RESULT
    # ═══════════════════════════════════════════════════════════════════
    await section("7 · Result")

    # 7a. Simple
    await bot.send_message(chat_id, parse_mode=H, text="✅ Done")
    await asyncio.sleep(GAP)

    # 7b. With stats
    await bot.send_message(chat_id, parse_mode=H, text=(
        "✅ <b>Done</b>\n\n"
        "Fixed <code>authenticate()</code> — now async with constant-time compare.\n\n"
        "Tests: <b>124 passed</b>   Files: <b>3 modified</b>"
    ))
    await asyncio.sleep(GAP)

    # 7c. Error
    await bot.send_message(chat_id, parse_mode=H, text=(
        "❌ <b>Failed</b>\n\n"
        "<code>ImportError: cannot import name 'compare_digest' from 'hmac'</code>\n\n"
        "<i>Python version in sandbox is 3.8 — upgrading and retrying.</i>"
    ))
    await asyncio.sleep(GAP)

    # ═══════════════════════════════════════════════════════════════════
    # 8. APPROVAL — agent pauses, waits for user
    # ═══════════════════════════════════════════════════════════════════
    await section("8 · Approval  (agent pauses)")

    # 8a. Simple confirm
    await bot.send_message(chat_id, parse_mode=H,
        text=(
            "⚠️ <b>Approval Required</b>\n\n"
            "Delete 15 generated files from <code>dist/</code>"
        ),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data="approve"),
            InlineKeyboardButton("❌ Reject", callback_data="reject"),
        ]]),
    )
    await asyncio.sleep(GAP)

    # 8b. Destructive command
    await bot.send_message(chat_id, parse_mode=H,
        text=(
            "⚠️ <b>Approval Required</b>\n\n"
            "Run:\n"
            "<pre>docker compose down --volumes</pre>\n"
            "<i>This will delete all local database data.</i>"
        ),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data="approve"),
            InlineKeyboardButton("❌ Reject", callback_data="reject"),
        ]]),
    )
    await asyncio.sleep(GAP)

    # 8c. Push to remote
    await bot.send_message(chat_id, parse_mode=H,
        text=(
            "⚠️ <b>Approval Required</b>\n\n"
            "Push <b>3 commits</b> to <code>main</code>\n\n"
            "<code>fix: async authenticate\n"
            "fix: constant-time token compare\n"
            "test: add revocation tests</code>"
        ),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Push", callback_data="approve"),
            InlineKeyboardButton("❌ Cancel", callback_data="reject"),
        ]]),
    )
    await asyncio.sleep(GAP)

    # ═══════════════════════════════════════════════════════════════════
    # DONE
    # ═══════════════════════════════════════════════════════════════════
    await bot.send_message(chat_id, parse_mode=H, text=(
        "─────────────────────\n"
        "<b>Grammar summary</b>\n\n"
        "  Status bar  — edited in place, always visible\n"
        "  🧠 Think     — italic, brief or explanatory\n"
        "  📖 Read      — one line + View button → Telegraph Instant View\n"
        "  🔍 Search    — query + match count\n"
        "  🧪 Bash      — streams in place, truncates long output\n"
        "  ✏️ Patch     — inline for small, button for large\n"
        "  ✅ Result    — plain or with stats\n"
        "  ❌ Error     — with error text + next action\n"
        "  ⚠️ Approval  — inline buttons, agent paused"
    ))


async def cmd_demo_agent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Simulate a full agent turn: fix failing auth tests."""
    chat_id = update.effective_chat.id
    bot = context.bot
    H = ParseMode.HTML

    # ── User prompt ──────────────────────────────────────────────────────────
    await bot.send_message(chat_id, parse_mode=H, text=(
        "💬 <b>You</b>\n"
        "Fix the failing auth tests"
    ))
    await asyncio.sleep(0.6)

    # ── Status bar (will be edited in place throughout) ──────────────────────
    status = await bot.send_message(chat_id, parse_mode=H, text=(
        "┌ <b>Workspace:</b> backend\n"
        "├ <b>Status:</b> Thinking…\n"
        "└ <b>Tools:</b> 0"
    ))
    await asyncio.sleep(0.8)

    # ── Thinking ─────────────────────────────────────────────────────────────
    await bot.send_message(chat_id, parse_mode=H, text=(
        "🧠 <i>Let me look at the failing tests and the auth module to understand what's broken.</i>"
    ))
    await asyncio.sleep(1.0)

    # ── Read files ───────────────────────────────────────────────────────────
    await status.edit_text(parse_mode=H, text=(
        "┌ <b>Workspace:</b> backend\n"
        "├ <b>Status:</b> Reading files…\n"
        "└ <b>Tools:</b> 1"
    ))
    await bot.send_message(chat_id, parse_mode=H, text="📖 <code>auth.py</code>")
    await asyncio.sleep(0.5)

    await status.edit_text(parse_mode=H, text=(
        "┌ <b>Workspace:</b> backend\n"
        "├ <b>Status:</b> Reading files…\n"
        "└ <b>Tools:</b> 2"
    ))
    await bot.send_message(chat_id, parse_mode=H, text="📖 <code>tests/test_auth.py</code>")
    await asyncio.sleep(0.5)

    await status.edit_text(parse_mode=H, text=(
        "┌ <b>Workspace:</b> backend\n"
        "├ <b>Status:</b> Reading files…\n"
        "└ <b>Tools:</b> 3"
    ))
    await bot.send_message(chat_id, parse_mode=H, text="📖 <code>models/user.py</code>")
    await asyncio.sleep(1.0)

    # ── Thinking again ────────────────────────────────────────────────────────
    await status.edit_text(parse_mode=H, text=(
        "┌ <b>Workspace:</b> backend\n"
        "├ <b>Status:</b> Thinking…\n"
        "└ <b>Tools:</b> 3"
    ))
    await bot.send_message(chat_id, parse_mode=H, text=(
        "🧠 <i>Found it. <code>authenticate()</code> is synchronous but the test is calling it with <code>await</code>. "
        "Also the token comparison uses <code>==</code> directly instead of a constant-time compare. I'll fix both.</i>"
    ))
    await asyncio.sleep(1.2)

    # ── Run failing tests first ───────────────────────────────────────────────
    await status.edit_text(parse_mode=H, text=(
        "┌ <b>Workspace:</b> backend\n"
        "├ <b>Status:</b> Running tests…\n"
        "└ <b>Tools:</b> 4"
    ))
    bash_msg = await bot.send_message(chat_id, parse_mode=H, text=(
        "🧪 <code>pytest tests/test_auth.py -v</code>\n\n"
        "<pre>collecting…</pre>"
    ))
    await asyncio.sleep(1.0)
    await bash_msg.edit_text(parse_mode=H, text=(
        "🧪 <code>pytest tests/test_auth.py -v</code>\n\n"
        "<pre>"
        "FAILED test_auth.py::test_valid_token\n"
        "FAILED test_auth.py::test_expired_token\n"
        "PASSED test_auth.py::test_missing_token\n"
        "\n"
        "2 failed, 1 passed in 0.41s"
        "</pre>"
    ))
    await asyncio.sleep(1.0)

    # ── Edit file ─────────────────────────────────────────────────────────────
    await status.edit_text(parse_mode=H, text=(
        "┌ <b>Workspace:</b> backend\n"
        "├ <b>Status:</b> Editing auth.py…\n"
        "└ <b>Tools:</b> 5"
    ))

    diff_url = "https://diffshub.com/josh-gree/TgramBotz/commit/57e2bbe"
    await bot.send_message(chat_id, parse_mode=H,
        text=(
            "✏️ <code>auth.py</code>  <b>+12 -4</b>\n\n"
            "<pre><code class=\"language-diff\">"
            "-def authenticate(token: str) -> bool:\n"
            "-    return token == SECRET\n"
            "+async def authenticate(token: str) -> bool:\n"
            "+    return hmac.compare_digest(token, SECRET)"
            "</code></pre>"
        ),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔍 View Full Diff", url=diff_url),
        ]]),
    )
    await asyncio.sleep(1.2)

    # ── Run tests again ───────────────────────────────────────────────────────
    await status.edit_text(parse_mode=H, text=(
        "┌ <b>Workspace:</b> backend\n"
        "├ <b>Status:</b> Running tests…\n"
        "└ <b>Tools:</b> 6"
    ))
    bash_msg2 = await bot.send_message(chat_id, parse_mode=H, text=(
        "🧪 <code>pytest tests/test_auth.py -v</code>\n\n"
        "<pre>collecting…</pre>"
    ))
    await asyncio.sleep(1.2)
    await bash_msg2.edit_text(parse_mode=H, text=(
        "🧪 <code>pytest tests/test_auth.py -v</code>\n\n"
        "<pre>"
        "PASSED test_auth.py::test_valid_token\n"
        "PASSED test_auth.py::test_expired_token\n"
        "PASSED test_auth.py::test_missing_token\n"
        "\n"
        "3 passed in 0.38s ✓"
        "</pre>"
    ))
    await asyncio.sleep(0.8)

    # ── Done ──────────────────────────────────────────────────────────────────
    await status.edit_text(parse_mode=H, text=(
        "┌ <b>Workspace:</b> backend\n"
        "├ <b>Status:</b> ✅ Complete\n"
        "└ <b>Tools:</b> 6"
    ))
    await bot.send_message(chat_id, parse_mode=H, text=(
        "✅ <b>Done</b>\n\n"
        "Fixed <code>authenticate()</code> — was synchronous, tests expected async.\n"
        "Also switched to <code>hmac.compare_digest</code> to prevent timing attacks.\n\n"
        "Tests: <b>3 passed</b>   Files: <b>1 modified</b>"
    ))


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

    # Shell passthrough — messages starting with $
    if text.startswith("$"):
        await on_shell(update, context, text[1:].strip())
        return

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


async def on_shell(update: Update, context: ContextTypes.DEFAULT_TYPE, cmd: str) -> None:
    from tgrambotz.bot.shell import INLINE_MAX, get_session
    from tgrambotz.bot.telegraph import create_output_page

    if not cmd:
        await update.message.reply_text("Usage: <code>$ &lt;command&gt;</code>", parse_mode=ParseMode.HTML)
        return

    chat_id = update.effective_chat.id
    session = get_session(chat_id)

    msg = await update.message.reply_text(
        parse_mode=ParseMode.HTML,
        text=f"<code>$ {cmd}</code>\n\n<pre>…</pre>",
    )

    last_edit = 0.0
    all_lines: list[str] = []
    exit_code: int | None = None
    start = time.monotonic()

    def visible_lines(lines: list[str]) -> list[str]:
        return [l for l in lines if not l.startswith("\x00")]

    def live_text(lines: list[str]) -> str:
        vis = visible_lines(lines)
        tail = vis[-15:] if len(vis) > 15 else vis
        prefix = f"… {len(vis) - len(tail)} lines\n" if len(vis) > len(tail) else ""
        body = prefix + "\n".join(tail) if tail else "…"
        return f"<code>$ {cmd}</code>\n\n<pre>{body}</pre>"

    async for all_lines, done in session.run(cmd):
        # Extract exit code from sentinel lines
        for l in all_lines:
            if l.startswith("\x00exit:"):
                try:
                    exit_code = int(l[6:])
                except ValueError:
                    pass

        if not done:
            now = time.monotonic()
            if now - last_edit >= 1.0:
                try:
                    await msg.edit_text(parse_mode=ParseMode.HTML, text=live_text(all_lines))
                    last_edit = now
                except Exception:
                    pass

    # ── Final render ────────────────────────────────────────────────────
    elapsed = time.monotonic() - start
    vis = visible_lines(all_lines)
    status = "✅" if (exit_code == 0 or exit_code is None) else "❌"
    meta = f"{status}  exit {exit_code if exit_code is not None else '?'}  ·  {len(vis)} lines  ·  {elapsed:.1f}s"

    if len(vis) <= INLINE_MAX:
        # Short output — show inline
        body = "\n".join(vis) if vis else "(no output)"
        await msg.edit_text(
            parse_mode=ParseMode.HTML,
            text=f"<code>$ {cmd}</code>\n\n<pre>{body}</pre>\n\n{meta}",
        )
    else:
        # Long output — Telegraph page + summary card
        tail = vis[-10:]
        tail_text = "\n".join(tail)
        try:
            url = await create_output_page(cmd, "\n".join(vis), exit_code, elapsed)
            await msg.edit_text(
                parse_mode=ParseMode.HTML,
                text=(
                    f"<code>$ {cmd}</code>\n\n"
                    f"<pre>{tail_text}</pre>\n\n"
                    f"{meta}"
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👁 View Full Output", url=url),
                ]]),
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Telegraph failed for shell output: %s", e)
            await msg.edit_text(
                parse_mode=ParseMode.HTML,
                text=f"<code>$ {cmd}</code>\n\n<pre>{tail_text}</pre>\n\n{meta}\n<i>⚠️ Full output unavailable</i>",
            )


SAMPLE_DIFF = """\
--- a/auth.py
+++ b/auth.py
@@ -1,18 +1,32 @@
-def authenticate(token: str) -> bool:
-    return token == SECRET
+async def authenticate(
+    token: str,
+    db: AsyncSession,
+) -> User | None:
+    result = await db.execute(
+        select(User).where(User.token == token)
+    )
+    return result.scalar_one_or_none()

-def require_auth(f):
-    def wrapper(*args, **kwargs):
-        if not authenticate(args[0]):
-            raise PermissionError
-        return f(*args, **kwargs)
-    return wrapper
+def require_auth(f):
+    async def wrapper(*args, **kwargs):
+        user = await authenticate(args[0], args[1])
+        if user is None:
+            raise HTTPException(status_code=401)
+        return await f(*args, user=user, **kwargs)
+    return wrapper
+
+async def revoke_token(token: str, db: AsyncSession) -> None:
+    await db.execute(
+        update(User)
+        .where(User.token == token)
+        .values(token=None, revoked_at=datetime.utcnow())
+    )
+    await db.commit()
"""


def diffshub_url(github_url: str) -> str:
    return github_url.replace("https://github.com", "https://diffshub.com", 1)


async def cmd_demo_telegraph(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from tgrambotz.bot.telegraph import create_diff_page

    msg = await update.message.reply_text("📡 Publishing diff to Telegraph…")

    url = await create_diff_page(
        filename="auth.py",
        additions=42,
        deletions=8,
        diff_text=SAMPLE_DIFF,
    )

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📋 View Diff", url=url),
        InlineKeyboardButton("↩️ Revert", callback_data="revert:auth.py"),
    ]])

    await msg.edit_text(
        parse_mode=ParseMode.HTML,
        text=(
            "✏️ <code>auth.py</code>  <b>+42 -8</b>\n\n"
            "Switched to async authentication with DB lookup.\n"
            "Added token revocation."
        ),
        reply_markup=keyboard,
    )


async def cmd_demo_diffshub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Demo using the actual TgramBotz PR #1
    pr_url = "https://github.com/josh-gree/TgramBotz/pull/1"
    commit_url = "https://github.com/josh-gree/TgramBotz/commit/7093fee"

    await update.message.reply_text(
        parse_mode=ParseMode.HTML,
        text=(
            "✏️ <code>auth.py</code>  <b>+42 -8</b>\n\n"
            "Switched to async authentication with DB lookup.\n"
            "Added token revocation."
        ),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔍 View Diff", url=diffshub_url(commit_url)),
            InlineKeyboardButton("↩️ Revert", callback_data="revert:auth.py"),
        ]]),
    )
    await asyncio.sleep(0.3)
    await update.message.reply_text(
        parse_mode=ParseMode.HTML,
        text="Or view the full PR:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 PR #1 on DiffsHub", url=diffshub_url(pr_url)),
        ]]),
    )


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

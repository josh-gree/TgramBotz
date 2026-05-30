from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession
from telegram import Update
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

    async with async_session_factory() as db:
        state = await db.get(ChatState, chat_id)
        session_id = state.active_session_id if state else None

        event = Event(
            session_id=session_id,
            chat_id=chat_id,
            type="USER_MESSAGE",
            payload=text,
        )
        db.add(event)
        await db.commit()

    # Echo back — will be replaced by agent invocation in Ticket 8
    await update.message.reply_text(f"Echo: {text}")

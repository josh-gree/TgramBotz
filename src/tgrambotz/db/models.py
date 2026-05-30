from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel


class Session(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    telegram_chat_id: int
    e2b_sandbox_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatState(SQLModel, table=True):
    chat_id: int = Field(primary_key=True)
    active_session_id: Optional[int] = Field(default=None, foreign_key="session.id")
    status_message_id: Optional[int] = None


class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: Optional[int] = Field(default=None, foreign_key="session.id")
    chat_id: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    type: str
    payload: str = ""

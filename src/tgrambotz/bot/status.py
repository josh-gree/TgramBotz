import asyncio
import time
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError


class LiveStatusMessage:
    """Single Telegram message that is edited in-place as the agent works."""

    def __init__(self, bot: Bot, chat_id: int, message_id: Optional[int] = None):
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self._workspace: str = ""
        self._status: str = "Idle"
        self._tool_calls: int = 0
        self._last_edit: float = 0.0
        self._min_interval: float = 1.0  # Telegram rate limit: ~1 edit/sec

    def _render(self) -> str:
        lines = []
        if self._workspace:
            lines.append(f"<b>Workspace:</b> {self._workspace}")
            lines.append("")
        lines.append(f"<b>Status:</b>\n{self._status}")
        lines.append("")
        lines.append(f"<b>Tool Calls:</b>\n{self._tool_calls}")
        return "\n".join(lines)

    async def send_or_edit(self) -> None:
        text = self._render()
        now = time.monotonic()
        if now - self._last_edit < self._min_interval:
            return
        try:
            if self.message_id is None:
                msg = await self.bot.send_message(
                    chat_id=self.chat_id, text=text, parse_mode="HTML"
                )
                self.message_id = msg.message_id
            else:
                await self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text=text,
                    parse_mode="HTML",
                )
            self._last_edit = time.monotonic()
        except TelegramError:
            pass

    async def update(
        self,
        *,
        workspace: Optional[str] = None,
        status: Optional[str] = None,
        increment_tools: bool = False,
    ) -> None:
        if workspace is not None:
            self._workspace = workspace
        if status is not None:
            self._status = status
        if increment_tools:
            self._tool_calls += 1
        await self.send_or_edit()

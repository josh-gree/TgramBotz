"""OpenCode agent running inside an E2B sandbox via OpenRouter.

Stub implementation — wired up in Ticket 8.
"""
from typing import AsyncIterator

from tgrambotz.agent.base import Agent
from tgrambotz.events.types import Event, ResultEvent


class OpenCodeAgent(Agent):
    async def prompt(self, session_id: str, message: str) -> AsyncIterator[Event]:
        # TODO: connect to E2B sandbox, run opencode CLI, stream events
        yield ResultEvent(summary="Agent not yet connected. Coming in Ticket 8.")

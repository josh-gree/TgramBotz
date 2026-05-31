from abc import ABC, abstractmethod
from typing import AsyncIterator

from tgrambotz.events.types import Event


class Agent(ABC):
    @abstractmethod
    async def prompt(self, session_id: str, message: str) -> AsyncIterator[Event]:
        ...

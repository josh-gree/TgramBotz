from abc import ABC, abstractmethod
from typing import AsyncIterator


class Sandbox(ABC):
    @abstractmethod
    async def create(self) -> str:
        """Create sandbox, return sandbox_id."""
        ...

    @abstractmethod
    async def connect(self, sandbox_id: str) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def exec(self, command: str) -> AsyncIterator[str]:
        """Yield stdout lines as they arrive."""
        ...

    @abstractmethod
    async def upload(self, path: str, content: bytes) -> None:
        ...

    @abstractmethod
    async def download(self, path: str) -> bytes:
        ...

    @abstractmethod
    async def snapshot(self) -> str:
        """Pause sandbox and return snapshot_id."""
        ...

    @abstractmethod
    async def restore(self, snapshot_id: str) -> None:
        ...

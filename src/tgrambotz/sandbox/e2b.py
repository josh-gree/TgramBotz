"""E2B sandbox implementation.

Stub implementation — wired up in Ticket 6.
"""
from typing import AsyncIterator

from tgrambotz.sandbox.base import Sandbox


class E2BSandbox(Sandbox):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._sandbox = None

    async def create(self) -> str:
        raise NotImplementedError("E2B integration coming in Ticket 6")

    async def connect(self, sandbox_id: str) -> None:
        raise NotImplementedError("E2B integration coming in Ticket 6")

    async def stop(self) -> None:
        raise NotImplementedError("E2B integration coming in Ticket 6")

    async def exec(self, command: str) -> AsyncIterator[str]:
        raise NotImplementedError("E2B integration coming in Ticket 6")

    async def upload(self, path: str, content: bytes) -> None:
        raise NotImplementedError("E2B integration coming in Ticket 6")

    async def download(self, path: str) -> bytes:
        raise NotImplementedError("E2B integration coming in Ticket 6")

    async def snapshot(self) -> str:
        raise NotImplementedError("E2B integration coming in Ticket 7")

    async def restore(self, snapshot_id: str) -> None:
        raise NotImplementedError("E2B integration coming in Ticket 7")

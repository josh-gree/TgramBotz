"""E2B sandbox implementation."""
import asyncio
import logging
import uuid
from typing import AsyncIterator

from e2b import AsyncSandbox

from tgrambotz.config import settings
from tgrambotz.sandbox.base import Sandbox

log = logging.getLogger(__name__)

SANDBOX_TIMEOUT = 3600  # 1 hour idle timeout


class E2BSandbox(Sandbox):
    def __init__(self) -> None:
        self._sandbox: AsyncSandbox | None = None
        self.sandbox_id: str | None = None

    async def create(self) -> str:
        log.info("Creating E2B sandbox…")
        self._sandbox = await AsyncSandbox.create(
            api_key=settings.e2b_api_key,
            timeout=SANDBOX_TIMEOUT,
        )
        self.sandbox_id = self._sandbox.sandbox_id
        log.info("E2B sandbox created: %s", self.sandbox_id)
        return self.sandbox_id

    async def connect(self, sandbox_id: str) -> None:
        log.info("Connecting to E2B sandbox: %s", sandbox_id)
        self._sandbox = await AsyncSandbox.connect(
            sandbox_id,
            api_key=settings.e2b_api_key,
        )
        self.sandbox_id = sandbox_id

    async def stop(self) -> None:
        if self._sandbox:
            await self._sandbox.kill()
            self._sandbox = None

    async def exec(self, command: str, timeout: float = 60.0) -> AsyncIterator[str]:
        assert self._sandbox, "Not connected to a sandbox"
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def on_out(output) -> None:
            queue.put_nowait(output.line)

        handle = await self._sandbox.commands.run(
            command,
            background=True,
            on_stdout=on_out,
            on_stderr=on_out,
            timeout=0,  # no connection timeout — we handle it ourselves
        )

        async def _collect():
            await handle.wait()
            queue.put_nowait(None)  # sentinel

        task = asyncio.create_task(_collect())
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    yield "⏱ timed out"
                    task.cancel()
                    return
                if item is None:
                    return
                yield item
        finally:
            task.cancel()

    async def upload(self, path: str, content: bytes) -> None:
        assert self._sandbox
        await self._sandbox.files.write(path, content)

    async def download(self, path: str) -> bytes:
        assert self._sandbox
        data = await self._sandbox.files.read(path, format="bytes")
        return data

    async def snapshot(self) -> str:
        assert self._sandbox
        log.info("Pausing sandbox %s for snapshot…", self.sandbox_id)
        await self._sandbox.pause()
        log.info("Snapshot complete: %s", self.sandbox_id)
        return self.sandbox_id

    async def restore(self, snapshot_id: str) -> None:
        log.info("Restoring sandbox from snapshot: %s", snapshot_id)
        self._sandbox = await AsyncSandbox.connect(
            snapshot_id,
            api_key=settings.e2b_api_key,
        )
        self.sandbox_id = snapshot_id


# ── Per-session sandbox registry ─────────────────────────────────────────────

_sandboxes: dict[int, E2BSandbox] = {}  # session_id → sandbox


async def get_or_create_sandbox(session_id: int, e2b_sandbox_id: str | None) -> E2BSandbox:
    """Return the sandbox for this session, creating or reconnecting as needed."""
    if session_id in _sandboxes:
        return _sandboxes[session_id]

    sb = E2BSandbox()
    if e2b_sandbox_id:
        try:
            await sb.connect(e2b_sandbox_id)
            log.info("Reconnected to sandbox %s for session %s", e2b_sandbox_id, session_id)
        except Exception as exc:
            log.warning("Failed to reconnect sandbox %s (%s) — creating new one", e2b_sandbox_id, exc)
            await sb.create()
    else:
        await sb.create()

    _sandboxes[session_id] = sb
    return sb

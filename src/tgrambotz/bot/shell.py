"""Shell sessions — local (dev) or E2B-backed (production)."""
import asyncio
import time
import uuid
from typing import AsyncIterator

LIVE_TAIL = 15
INLINE_MAX = 30


class LocalShellSession:
    """Persistent bash process running locally — used when no workspace/sandbox."""

    def __init__(self):
        self._proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()

    async def _ensure(self) -> None:
        if self._proc is None or self._proc.returncode is not None:
            self._proc = await asyncio.create_subprocess_exec(
                "bash", "--norc", "--noprofile",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={"TERM": "dumb", "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
            )

    async def run(self, cmd: str, timeout: float = 60.0) -> AsyncIterator[tuple[list[str], bool]]:
        async with self._lock:
            await self._ensure()
            marker = f"__END_{uuid.uuid4().hex}__"
            exit_marker = f"__EXIT_{uuid.uuid4().hex}__"
            payload = f"{cmd}\necho {exit_marker}$?\necho {marker}\n".encode()
            self._proc.stdin.write(payload)
            await self._proc.stdin.drain()

            lines: list[str] = []
            deadline = time.monotonic() + timeout

            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    lines.append("⏱ timed out")
                    yield lines, True
                    return
                try:
                    raw = await asyncio.wait_for(self._proc.stdout.readline(), timeout=min(remaining, 5.0))
                except asyncio.TimeoutError:
                    yield lines, False
                    continue
                if not raw:
                    yield lines, True
                    return
                text = raw.decode(errors="replace").rstrip("\n")
                if text == marker:
                    yield lines, True
                    return
                elif text.startswith(exit_marker):
                    try:
                        lines.append(f"\x00exit:{int(text[len(exit_marker):])}")
                    except ValueError:
                        pass
                else:
                    lines.append(text)
                    yield lines, False

    async def kill(self) -> None:
        if self._proc and self._proc.returncode is None:
            self._proc.kill()
            await self._proc.wait()
            self._proc = None


class E2BShellSession:
    """Shell session backed by an E2B sandbox."""

    def __init__(self, session_id: int, e2b_sandbox_id: str | None):
        self.session_id = session_id
        self.e2b_sandbox_id = e2b_sandbox_id
        self._lock = asyncio.Lock()

    async def run(self, cmd: str, timeout: float = 60.0) -> AsyncIterator[tuple[list[str], bool]]:
        from tgrambotz.sandbox.e2b import get_or_create_sandbox
        from tgrambotz.db.database import async_session_factory
        from tgrambotz.db.models import Session as DBSession
        from sqlmodel import select

        async with self._lock:
            sb = await get_or_create_sandbox(self.session_id, self.e2b_sandbox_id)

            # Persist new sandbox_id back to DB if it was just created
            if sb.sandbox_id and sb.sandbox_id != self.e2b_sandbox_id:
                self.e2b_sandbox_id = sb.sandbox_id
                try:
                    async with async_session_factory() as db:
                        result = await db.execute(select(DBSession).where(DBSession.id == self.session_id))
                        sess = result.scalar_one_or_none()
                        if sess:
                            sess.e2b_sandbox_id = sb.sandbox_id
                            await db.commit()
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception("Failed to persist sandbox_id")

            lines: list[str] = []
            # Wrap exec() into the (lines, done) tuple format
            async for line in sb.exec(cmd, timeout=timeout):
                lines.append(line)
                yield lines, False
            yield lines, True

    async def kill(self) -> None:
        from tgrambotz.sandbox.e2b import _sandboxes
        sb = _sandboxes.pop(self.session_id, None)
        if sb:
            await sb.stop()


# ── Session registry ──────────────────────────────────────────────────────────

_local_sessions: dict[int, LocalShellSession] = {}  # chat_id → session (no workspace)
_e2b_sessions: dict[int, E2BShellSession] = {}      # session_id → E2B session


def get_local_session(chat_id: int) -> LocalShellSession:
    if chat_id not in _local_sessions:
        _local_sessions[chat_id] = LocalShellSession()
    return _local_sessions[chat_id]


def get_e2b_session(session_id: int, e2b_sandbox_id: str | None) -> E2BShellSession:
    if session_id not in _e2b_sessions:
        _e2b_sessions[session_id] = E2BShellSession(session_id, e2b_sandbox_id)
    return _e2b_sessions[session_id]

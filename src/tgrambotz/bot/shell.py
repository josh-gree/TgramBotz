"""Persistent bash shell session — one per chat."""
import asyncio
import time
import uuid
from typing import AsyncIterator


class ShellSession:
    def __init__(self):
        self._proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()

    async def ensure_started(self) -> None:
        if self._proc is None or self._proc.returncode is not None:
            self._proc = await asyncio.create_subprocess_exec(
                "bash", "--norc", "--noprofile",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={"TERM": "dumb", "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
            )

    async def run(self, cmd: str, timeout: float = 30.0) -> AsyncIterator[str]:
        async with self._lock:
            await self.ensure_started()
            marker = f"__END_{uuid.uuid4().hex}__"
            payload = f"{cmd}\necho {marker}\n".encode()
            self._proc.stdin.write(payload)
            await self._proc.stdin.drain()

            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    yield "\n⏱ timed out"
                    break
                try:
                    line = await asyncio.wait_for(
                        self._proc.stdout.readline(), timeout=min(remaining, 5.0)
                    )
                except asyncio.TimeoutError:
                    continue
                if not line:
                    break
                text = line.decode(errors="replace").rstrip("\n")
                if text == marker:
                    break
                yield text

    async def kill(self) -> None:
        if self._proc and self._proc.returncode is None:
            self._proc.kill()
            await self._proc.wait()
            self._proc = None


# One session per chat_id
_sessions: dict[int, ShellSession] = {}


def get_session(chat_id: int) -> ShellSession:
    if chat_id not in _sessions:
        _sessions[chat_id] = ShellSession()
    return _sessions[chat_id]

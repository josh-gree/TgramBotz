"""Persistent bash shell session — one per chat."""
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator


LIVE_TAIL = 15       # lines shown live during streaming
INLINE_MAX = 30      # lines shown inline in final message (no button needed)


@dataclass
class RunResult:
    cmd: str
    lines: list[str] = field(default_factory=list)
    exit_code: int | None = None
    elapsed: float = 0.0

    @property
    def output(self) -> str:
        return "\n".join(self.lines)

    @property
    def tail(self) -> str:
        return "\n".join(self.lines[-LIVE_TAIL:])

    @property
    def needs_telegraph(self) -> bool:
        return len(self.lines) > INLINE_MAX


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

    async def run(self, cmd: str, timeout: float = 60.0) -> AsyncIterator[tuple[list[str], bool]]:
        """Yields (all_lines_so_far, is_done) as output arrives."""
        async with self._lock:
            await self.ensure_started()

            marker = f"__END_{uuid.uuid4().hex}__"
            exit_marker = f"__EXIT_{uuid.uuid4().hex}__"
            payload = (
                f"{cmd}\n"
                f"echo {exit_marker}$?\n"
                f"echo {marker}\n"
            ).encode()
            self._proc.stdin.write(payload)
            await self._proc.stdin.drain()

            lines: list[str] = []
            exit_code: int | None = None
            start = time.monotonic()
            deadline = start + timeout

            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    lines.append("⏱ timed out")
                    yield lines, True
                    return
                try:
                    raw = await asyncio.wait_for(
                        self._proc.stdout.readline(), timeout=min(remaining, 5.0)
                    )
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
                        exit_code = int(text[len(exit_marker):])
                    except ValueError:
                        pass
                    # attach exit code as last pseudo-line so callers can read it
                    lines.append(f"\x00exit:{exit_code}")
                else:
                    lines.append(text)
                    yield lines, False

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

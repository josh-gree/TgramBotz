import asyncio
import logging
import re
import shlex

from e2b import AsyncSandbox

from tgrambotz.config import settings

log = logging.getLogger(__name__)

# Pre-built E2B template with opencode-ai already installed
E2B_TEMPLATE = "owngk1zv1374s7wd8y6f"
RESPONSE_TIMEOUT = 120

# Strip ANSI escape codes and the opencode UI header line ("› build · model")
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mKGHJA-Za-z]|\x1b\].*?\x07|\x1b[()][AB012]')


def _clean(text: str) -> str:
    text = _ANSI_RE.sub("", text)
    lines = [
        l for l in text.splitlines()
        if not l.strip().startswith(">") and l.strip() != ""
    ]
    return "\n".join(lines).strip()


class OpenCodeAgent:
    def __init__(self) -> None:
        self._sandbox: AsyncSandbox | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        log.info("Creating E2B sandbox from template %s…", E2B_TEMPLATE)
        self._sandbox = await AsyncSandbox.create(
            template=E2B_TEMPLATE,
            api_key=settings.e2b_api_key,
        )
        log.info("Sandbox ready: %s", self._sandbox.sandbox_id)
        # Trigger the one-time DB migration now so the first chat isn't slow
        await self._exec("opencode --version 2>&1", timeout=30)

    async def _exec(self, cmd: str, timeout: float = RESPONSE_TIMEOUT) -> str:
        lines: list[str] = []
        handle = await self._sandbox.commands.run(
            cmd,
            background=True,
            on_stdout=lambda l: lines.append(l),
            on_stderr=lambda l: lines.append(l),
            timeout=0,
            envs={"OPENROUTER_API_KEY": settings.openrouter_api_key},
        )
        try:
            await asyncio.wait_for(handle.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            log.warning("Command timed out: %s", cmd[:80])
        except Exception as e:
            log.warning("Command error: %s", e)
        return "\n".join(lines)

    async def chat(self, message: str) -> str:
        async with self._lock:
            quoted = shlex.quote(message)
            cmd = f"opencode run --continue -m {settings.openrouter_model} {quoted} 2>&1"
            raw = await self._exec(cmd, timeout=RESPONSE_TIMEOUT)
            return _clean(raw) or "(no response)"

    async def stop(self) -> None:
        if self._sandbox:
            await self._sandbox.kill()
            self._sandbox = None

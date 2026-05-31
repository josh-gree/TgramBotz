import asyncio
import logging

from e2b import AsyncSandbox

from tgrambotz.config import settings

log = logging.getLogger(__name__)

# Adjust these once you've confirmed the exact opencode install/launch commands
# and what prompt string opencode prints when ready for input.
INSTALL_CMD = "npm install -g opencode@latest"
LAUNCH_CMD = "opencode"
READY_PROMPT = ">"       # the prompt opencode shows when waiting for input
STARTUP_TIMEOUT = 60     # seconds to wait for opencode to be ready after launch
RESPONSE_TIMEOUT = 120   # seconds to wait for a response to a message


class OpenCodeAgent:
    def __init__(self) -> None:
        self._sandbox: AsyncSandbox | None = None
        self._handle = None
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        log.info("Creating E2B sandbox…")
        self._sandbox = await AsyncSandbox.create(api_key=settings.e2b_api_key)
        log.info("Sandbox created: %s", self._sandbox.sandbox_id)

        log.info("Installing opencode (this may take a minute)…")
        await self._sandbox.commands.run(INSTALL_CMD, timeout=180)
        log.info("opencode installed")

        log.info("Starting opencode…")
        self._handle = await self._sandbox.commands.run(
            LAUNCH_CMD,
            background=True,
            on_stdout=self._enqueue,
            on_stderr=self._enqueue,
            timeout=0,
            envs={
                "OPENROUTER_API_KEY": settings.openrouter_api_key,
                "OPENROUTER_MODEL": settings.openrouter_model,
            },
        )

        log.info("Waiting for opencode ready prompt…")
        startup_output = await self._read_until_prompt(timeout=STARTUP_TIMEOUT)
        log.info("opencode ready. Startup output:\n%s", startup_output)

    def _enqueue(self, line: str) -> None:
        self._queue.put_nowait(line)

    async def _read_until_prompt(self, timeout: float) -> str:
        lines: list[str] = []
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout

        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                line = await asyncio.wait_for(
                    self._queue.get(), timeout=min(remaining, 1.0)
                )
                stripped = line.strip()
                # Detect the ready prompt — opencode prints it when awaiting input.
                # Adjust this check if the actual prompt differs.
                if stripped == READY_PROMPT or stripped.endswith(f" {READY_PROMPT}"):
                    break
                lines.append(line)
            except asyncio.TimeoutError:
                # No output for 1s — if we've seen something, assume done
                if lines:
                    break

        return "\n".join(lines).strip()

    async def chat(self, message: str) -> str:
        async with self._lock:
            await self._handle.send_stdin(message + "\n")
            response = await self._read_until_prompt(timeout=RESPONSE_TIMEOUT)
            return response or "(no response)"

    async def stop(self) -> None:
        if self._sandbox:
            await self._sandbox.kill()
            self._sandbox = None

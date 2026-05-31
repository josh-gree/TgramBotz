import asyncio
import json
import logging
import shlex
from typing import Awaitable, Callable

from e2b import AsyncSandbox

from tgrambotz.config import settings

log = logging.getLogger(__name__)

E2B_TEMPLATE = "7orp1t31nayml8ndjkhf"
SANDBOX_TIMEOUT = 3600   # 1 hour idle timeout
RESPONSE_TIMEOUT = 120

_TOOL_ICONS = {
    "bash": "🔧",
    "read": "📖",
    "write": "✏️",
    "edit": "✏️",
    "glob": "🔍",
    "grep": "🔍",
    "patch": "✏️",
}


def _format_tool_event(event: dict) -> str | None:
    part = event.get("part", {})
    tool = part.get("tool", "")
    state = part.get("state", {})
    inp = state.get("input", {})
    title = state.get("title", "")
    icon = _TOOL_ICONS.get(tool, "⚙️")

    if tool == "bash":
        detail = inp.get("command", title)[:120]
        return f"{icon} `{detail}`"
    elif tool in ("read", "write", "edit", "patch"):
        detail = inp.get("filePath", inp.get("path", title))
        return f"{icon} `{detail}`"
    elif tool in ("glob", "grep"):
        detail = inp.get("pattern", inp.get("query", title))
        return f"{icon} `{detail}`"
    elif tool:
        return f"{icon} {tool}: {title or str(inp)[:80]}"
    return None


class OpenCodeAgent:
    def __init__(self) -> None:
        self._sandbox: AsyncSandbox | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        log.info("Creating E2B sandbox from template %s…", E2B_TEMPLATE)
        self._sandbox = await AsyncSandbox.create(
            template=E2B_TEMPLATE,
            api_key=settings.e2b_api_key,
            timeout=SANDBOX_TIMEOUT,
        )
        log.info("Sandbox ready: %s", self._sandbox.sandbox_id)
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
        except (asyncio.TimeoutError, Exception) as e:
            log.warning("exec error (%s): %s", cmd[:60], e)
        return "\n".join(lines)

    async def chat(
        self,
        message: str,
        on_tool: Callable[[str], Awaitable[None]] | None = None,
        on_text: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        async with self._lock:
            quoted = shlex.quote(message)
            cmd = (
                f"opencode run --continue --dangerously-skip-permissions "
                f"--format json -m {settings.openrouter_model} {quoted} 2>&1"
            )

            loop = asyncio.get_running_loop()
            queue: asyncio.Queue[str | None] = asyncio.Queue()

            def enqueue(line: str) -> None:
                loop.call_soon_threadsafe(queue.put_nowait, line)

            handle = await self._sandbox.commands.run(
                cmd,
                background=True,
                on_stdout=enqueue,
                on_stderr=enqueue,
                timeout=0,
                envs={"OPENROUTER_API_KEY": settings.openrouter_api_key},
            )

            async def _wait_done():
                try:
                    await asyncio.wait_for(handle.wait(), timeout=RESPONSE_TIMEOUT)
                except Exception as e:
                    log.warning("opencode wait error: %s", e)
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            asyncio.create_task(_wait_done())

            turns = 0

            while True:
                line = await queue.get()
                if line is None:
                    break
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                etype = event.get("type")

                if etype == "step_finish":
                    turns += 1
                    if turns >= settings.max_turns:
                        log.warning("max_turns=%d reached, killing opencode", settings.max_turns)
                        try:
                            await handle.kill()
                        except Exception:
                            pass
                        break

                if etype == "tool_use" and on_tool:
                    msg = _format_tool_event(event)
                    if msg:
                        try:
                            await on_tool(msg)
                        except Exception as e:
                            log.warning("on_tool error: %s", e)

                elif etype == "text" and on_text:
                    text = event.get("part", {}).get("text", "")
                    if text:
                        try:
                            await on_text(text)
                        except Exception as e:
                            log.warning("on_text error: %s", e)

    async def stop(self) -> None:
        if self._sandbox:
            await self._sandbox.kill()
            self._sandbox = None

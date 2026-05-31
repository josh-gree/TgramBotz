import asyncio
import json
import logging
import os

from tgrambotz.config import settings

log = logging.getLogger(__name__)

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
        return f"{icon} `{inp.get('command', title)[:120]}`"
    elif tool in ("read", "write", "edit", "patch"):
        return f"{icon} `{inp.get('filePath', inp.get('path', title))}`"
    elif tool in ("glob", "grep"):
        return f"{icon} `{inp.get('pattern', inp.get('query', title))}`"
    elif tool:
        return f"{icon} {tool}: {title or str(inp)[:80]}"
    return None


class LocalOpenCodeAgent:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        proc = await asyncio.create_subprocess_exec(
            "opencode", "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        log.info("opencode: %s", stdout.decode().strip())

    async def chat(self, message: str, on_tool=None, on_text=None) -> None:
        async with self._lock:
            proc = await asyncio.create_subprocess_exec(
                "opencode", "run",
                "--continue",
                "--dangerously-skip-permissions",
                "--format", "json",
                "-m", settings.openrouter_model,
                message,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, "OPENROUTER_API_KEY": settings.openrouter_api_key},
            )

            turns = 0
            async for raw in proc.stdout:
                line = raw.decode(errors="replace").strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                etype = event.get("type")

                if etype == "step_finish":
                    turns += 1
                    if turns >= settings.max_turns:
                        log.warning("max_turns=%d reached, killing opencode", settings.max_turns)
                        proc.kill()
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

            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()

    async def stop(self) -> None:
        pass

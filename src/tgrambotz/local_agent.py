import asyncio
import json
import logging
import os

import httpx

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

_PORT = 7701
_DIR = "/home/user"
_BASE = f"http://127.0.0.1:{_PORT}"


class LocalOpenCodeAgent:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._proc = None
        self._session_id: str | None = None

    async def start(self) -> None:
        # Kill any stale opencode serve process
        try:
            kill = await asyncio.create_subprocess_exec(
                "pkill", "-f", "opencode serve",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await kill.wait()
        except Exception:
            pass
        await asyncio.sleep(0.5)

        self._proc = await asyncio.create_subprocess_exec(
            "opencode", "serve", "--port", str(_PORT),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env={**os.environ, "OPENROUTER_API_KEY": settings.openrouter_api_key},
        )

        async with httpx.AsyncClient() as client:
            for _ in range(40):
                try:
                    r = await client.get(f"{_BASE}/global/health")
                    if r.status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.25)
            else:
                raise RuntimeError("opencode server failed to start")

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{_BASE}/session",
                params={"directory": _DIR},
                json={},
            )
            self._session_id = r.json()["id"]

        log.info("opencode server ready, session=%s", self._session_id)

    async def chat(self, message: str, on_tool=None, on_text=None) -> None:
        async with self._lock:
            done = asyncio.Event()
            text_parts: list[str] = []

            async def _listen() -> None:
                async with httpx.AsyncClient(timeout=httpx.Timeout(300)) as client:
                    async with client.stream(
                        "GET",
                        f"{_BASE}/event",
                        params={"sessionID": self._session_id, "directory": _DIR},
                    ) as resp:
                        saw_busy = False
                        async for line in resp.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            try:
                                evt = json.loads(line[6:])
                            except json.JSONDecodeError:
                                continue

                            etype = evt.get("type")
                            props = evt.get("properties", {})

                            if etype == "session.status":
                                if props.get("status", {}).get("type") == "busy":
                                    saw_busy = True

                            elif etype == "message.part.delta" and saw_busy:
                                if props.get("field") == "text":
                                    delta = props.get("delta", "")
                                    if delta:
                                        text_parts.append(delta)

                            elif etype == "message.part.updated" and saw_busy:
                                part = props.get("part", {})
                                if part.get("type") == "tool-invocation" and on_tool:
                                    tool = part.get("toolName", "")
                                    icon = _TOOL_ICONS.get(tool.lower(), "⚙️")
                                    args = part.get("args", {})
                                    detail = (
                                        args.get("command")
                                        or args.get("filePath")
                                        or args.get("path")
                                        or tool
                                    )
                                    try:
                                        await on_tool(f"{icon} `{str(detail)[:120]}`")
                                    except Exception as e:
                                        log.warning("on_tool error: %s", e)

                            elif etype == "session.idle" and saw_busy:
                                done.set()
                                return

            listener = asyncio.create_task(_listen())
            await asyncio.sleep(0.3)

            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{_BASE}/session/{self._session_id}/prompt_async",
                    params={"directory": _DIR},
                    json={"parts": [{"type": "text", "text": message}]},
                )

            try:
                await asyncio.wait_for(done.wait(), timeout=120)
            except asyncio.TimeoutError:
                log.warning("chat timeout after 120s")
            finally:
                listener.cancel()
                try:
                    await listener
                except asyncio.CancelledError:
                    pass

            if text_parts and on_text:
                try:
                    await on_text("".join(text_parts))
                except Exception as e:
                    log.warning("on_text error: %s", e)

    async def stop(self) -> None:
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()

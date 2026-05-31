import asyncio
import json
import logging
import os

import httpx

from tgrambotz.config import settings

log = logging.getLogger(__name__)

_PORT = 7701
_DIR = "/home/user"
_BASE = f"http://127.0.0.1:{_PORT}"


class LocalOpenCodeAgent:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._proc = None
        self._session_id: str | None = None

    async def start(self) -> None:
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
            raw_events: list[str] = []

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
                                log.debug("SSE non-JSON line: %s", line[:200])
                                continue

                            etype = evt.get("type", "")
                            log.debug("SSE event: %s", json.dumps(evt)[:500])

                            # Skip heartbeats
                            if etype in ("server.heartbeat", "server.connected"):
                                continue

                            raw_events.append(json.dumps(evt))

                            props = evt.get("properties", {})

                            if etype == "session.status":
                                if props.get("status", {}).get("type") == "busy":
                                    saw_busy = True

                            elif etype == "session.idle" and saw_busy:
                                done.set()
                                return

            listener = asyncio.create_task(_listen())
            await asyncio.sleep(0.3)

            model_str = settings.openrouter_model
            parts = model_str.split("/", 1)
            provider_id = parts[0]
            model_id = parts[1] if len(parts) > 1 else model_str

            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{_BASE}/session/{self._session_id}/prompt_async",
                    params={"directory": _DIR},
                    json={
                        "parts": [{"type": "text", "text": message}],
                        "model": {"providerID": provider_id, "modelID": model_id},
                    },
                )
                log.debug("prompt_async status=%s body=%s", r.status_code, r.text[:200])

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

            # Send all raw events to Telegram for inspection
            if on_text and raw_events:
                chunk: list[str] = []
                chunk_len = 0
                for evt_str in raw_events:
                    line = evt_str + "\n"
                    if chunk_len + len(line) > 3800:
                        try:
                            await on_text("```\n" + "".join(chunk) + "```")
                        except Exception as e:
                            log.warning("on_text error: %s", e)
                        chunk = []
                        chunk_len = 0
                    chunk.append(line)
                    chunk_len += len(line)
                if chunk:
                    try:
                        await on_text("```\n" + "".join(chunk) + "```")
                    except Exception as e:
                        log.warning("on_text error: %s", e)
            elif on_text:
                await on_text("(no events received)")

    async def stop(self) -> None:
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()

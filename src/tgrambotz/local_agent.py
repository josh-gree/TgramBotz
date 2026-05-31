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
            reasoning_events: list[str] = []
            text_events: list[str] = []
            # map partID → "reasoning" | "text"
            part_types: dict[str, str] = {}

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

                            etype = evt.get("type", "")
                            log.debug("SSE event: %s", json.dumps(evt)[:500])

                            if etype in ("server.heartbeat", "server.connected"):
                                continue

                            props = evt.get("properties", {})

                            if etype == "session.status":
                                if props.get("status", {}).get("type") == "busy":
                                    saw_busy = True

                            elif etype == "message.part.updated" and saw_busy:
                                part = props.get("part", {})
                                ptype = part.get("type", "")
                                pid = part.get("id", "")
                                if ptype in ("reasoning", "text") and pid:
                                    part_types[pid] = ptype
                                    bucket = reasoning_events if ptype == "reasoning" else text_events
                                    bucket.append(json.dumps(evt))

                            elif etype == "message.part.delta" and saw_busy:
                                pid = props.get("partID", "")
                                ptype = part_types.get(pid, "")
                                if ptype == "reasoning":
                                    reasoning_events.append(json.dumps(evt))
                                elif ptype == "text":
                                    text_events.append(json.dumps(evt))

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

            async def _send_bucket(label: str, events: list[str]) -> None:
                if not events or not on_text:
                    return
                chunk: list[str] = []
                chunk_len = 0
                for evt_str in events:
                    line = evt_str + "\n"
                    if chunk_len + len(line) > 3800:
                        await on_text(f"*{label}*\n```\n" + "".join(chunk) + "```")
                        chunk = []
                        chunk_len = 0
                    chunk.append(line)
                    chunk_len += len(line)
                if chunk:
                    await on_text(f"*{label}*\n```\n" + "".join(chunk) + "```")

            await _send_bucket("reasoning", reasoning_events)
            await _send_bucket("response", text_events)

    async def stop(self) -> None:
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()

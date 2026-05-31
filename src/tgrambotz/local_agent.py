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
        self._http: httpx.AsyncClient | None = None

    async def start(self) -> None:
        # Write opencode config to auto-approve all permissions
        cfg_dir = os.path.expanduser("~/.config/opencode")
        os.makedirs(cfg_dir, exist_ok=True)
        with open(os.path.join(cfg_dir, "opencode.json"), "w") as f:
            json.dump({"permission": "allow"}, f)

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

        # Persistent client — reuses TCP connections for all requests
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(300))

        for _ in range(40):
            try:
                r = await self._http.get(f"{_BASE}/global/health")
                if r.status_code == 200:
                    break
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.25)
        else:
            raise RuntimeError("opencode server failed to start")

        r = await self._http.post(
            f"{_BASE}/session",
            params={"directory": _DIR},
            json={},
        )
        self._session_id = r.json()["id"]

        log.info("opencode server ready, session=%s", self._session_id)

    async def chat(
        self,
        message: str,
        on_reasoning_delta=None,
        on_text_delta=None,
        on_tool=None,
    ) -> None:
        async with self._lock:
            done = asyncio.Event()
            connected = asyncio.Event()
            part_types: dict[str, str] = {}  # partID → "reasoning" | "text"

            async def _listen() -> None:
                async with self._http.stream(
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
                        props = evt.get("properties", {})

                        if etype not in ("server.heartbeat", "message.part.delta"):
                            log.info("SSE %s %s", etype, str(props)[:200])

                        if etype == "server.connected":
                            connected.set()
                            continue
                        if etype == "server.heartbeat":
                            continue

                        if etype == "session.status":
                            if props.get("status", {}).get("type") == "busy":
                                saw_busy = True

                        elif etype == "message.part.updated" and saw_busy:
                            part = props.get("part", {})
                            ptype = part.get("type", "")
                            pid = part.get("id", "")
                            if ptype in ("reasoning", "text") and pid:
                                part_types[pid] = ptype
                            elif ptype == "tool-invocation" and pid and on_tool:
                                try:
                                    await on_tool(part)
                                except Exception as e:
                                    log.warning("on_tool error: %s", e)

                        elif etype == "message.part.delta" and saw_busy:
                            pid = props.get("partID", "")
                            ptype = part_types.get(pid, "")
                            delta = props.get("delta", "")
                            if not delta:
                                continue
                            if ptype == "reasoning" and on_reasoning_delta:
                                try:
                                    await on_reasoning_delta(delta)
                                except Exception as e:
                                    log.warning("on_reasoning_delta error: %s", e)
                            elif ptype == "text" and on_text_delta:
                                try:
                                    await on_text_delta(delta)
                                except Exception as e:
                                    log.warning("on_text_delta error: %s", e)

                        elif etype == "session.idle" and saw_busy:
                            done.set()
                            return

            listener = asyncio.create_task(_listen())
            # Wait for SSE handshake before sending prompt
            await asyncio.wait_for(connected.wait(), timeout=5)

            model_str = settings.openrouter_model
            parts = model_str.split("/", 1)
            provider_id = parts[0]
            model_id = parts[1] if len(parts) > 1 else model_str

            await self._http.post(
                f"{_BASE}/session/{self._session_id}/prompt_async",
                params={"directory": _DIR},
                json={
                    "parts": [{"type": "text", "text": message}],
                    "model": {"providerID": provider_id, "modelID": model_id},
                },
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

    async def stop(self) -> None:
        if self._http:
            await self._http.aclose()
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()

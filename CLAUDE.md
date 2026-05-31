# TgramBotz

## Start of every session — do this first

```bash
just init       # installs Doppler CLI (required for all secret-bearing commands)
just install    # uv sync — install/update Python deps
```

Then check the active sandbox is still running:

```bash
cat .sandbox-id                   # confirm sandbox ID is present
just bot-status                   # should say "running" or "paused"
just bot-resume                   # if paused
just bot-logs                     # confirm bot is polling Telegram
```

If `.sandbox-id` is missing (new session, file not committed), recreate it:

```bash
echo "inv8w825em5hs1ej2nu9k" > .sandbox-id
just bot-status
```

---

## What this project is

A Telegram bot that gives users access to an AI coding agent. The user sends a message; the bot runs `opencode-ai` to handle it with full tool use (Bash, Read, Write, Edit, Grep, etc.) and streams results back in real time — reasoning in a blockquote, tool calls as they execute, and the final response as plain text.

---

## Architecture

```
User (Telegram) → Telegram servers
                       ↓ long-polling
              E2B Sandbox (inv8w825em5hs1ej2nu9k)
              ┌────────────────────────────────────────┐
              │  python3 -u -m tgrambotz               │
              │  (SANDBOX_MODE=1)                      │
              │  → LocalOpenCodeAgent                  │
              │    → opencode serve --port 7701        │
              │      (persistent HTTP + SSE server)    │
              │      → OpenRouter (LLM via API)        │
              └────────────────────────────────────────┘
```

**Key point:** `opencode serve` runs as a long-lived HTTP server (not spawned per message). Each user message opens an SSE stream to `/event`, sends the prompt via `POST /session/{id}/prompt_async`, and streams events back until `session.idle` fires.

The local CLI (`sandbox_ctl.py`) only manages lifecycle — it never runs inside the sandbox.

---

## Key files

| File | Purpose |
|---|---|
| `src/tgrambotz/__main__.py` | Entry point. Switches between `OpenCodeAgent` (E2B relay mode) and `LocalOpenCodeAgent` (sandbox mode) via `SANDBOX_MODE=1`. Handles streaming: reasoning blockquote, tool call messages, response text. |
| `src/tgrambotz/local_agent.py` | `LocalOpenCodeAgent` — starts `opencode serve`, creates a session, streams SSE events per message. Writes `~/.config/opencode/opencode.json` with `{"permission": "allow"}` at startup to suppress all permission prompts. |
| `src/tgrambotz/agent.py` | `OpenCodeAgent` — original E2B relay mode (not currently used). |
| `src/tgrambotz/config.py` | Pydantic settings: `TELEGRAM_TOKEN`, `E2B_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`. |
| `scripts/sandbox_ctl.py` | Sandbox lifecycle: `start / pause / resume / status / logs / stop`. Saves sandbox ID to `.sandbox-id`. Has SSL patch at top (intentional — see SSL section). |
| `scripts/build_template.py` | Rebuilds the E2B sandbox template via Python SDK. |
| `scripts/sandboxes.py` | List/kill/new E2B sandboxes. |
| `scripts/check_auth.py` | Smoke-tests all credentials. |
| `Justfile` | All commands. The primary operational reference. |
| `.sandbox-id` | Persists the current sandbox ID locally. **Gitignored** — recreate manually if missing. |

---

## opencode SSE event structure

The SSE stream (`GET /event?sessionID=...&directory=...`) emits these relevant event types:

| Event type | When | What to do |
|---|---|---|
| `server.connected` | SSE handshake complete | Signal that it's safe to send the prompt |
| `server.heartbeat` | Every ~30s | Ignore |
| `session.status` | `status.type == "busy"` | Start processing events |
| `session.status` | `status.type == "idle"` | Precedes `session.idle` |
| `message.part.updated` | Part created/updated | Track part type; call on_tool for `type=="tool"` |
| `message.part.delta` | Streaming text chunk | `props.partID` → look up part type → call callback |
| `session.idle` | Turn complete | Set done event, exit listener |
| `permission.asked` | **Never fires** (auto-approved via config) | Would have blocked forever if not suppressed |

**Part types in `message.part.updated`:**
- `type == "reasoning"` or `type == "text"` — has `id` field; track `id → type` for delta routing
- `type == "tool"` — has `callID` (not `id`), `tool` (name), `state.status` (`"running"` → `"completed"`), `state.input` (args), `state.output` (result)

**Critical:** Always send the prompt AFTER `server.connected` fires, not after a fixed sleep.

---

## opencode permission system

By default, opencode asks for user approval before accessing the filesystem. In headless/server mode this blocks forever (no human to click "Allow"). 

**Fix:** `local_agent.py` writes `~/.config/opencode/opencode.json` with `{"permission": "allow"}` before starting the server. This must happen before `opencode serve` starts — the config is read at startup.

If you see the bot hang after receiving a message with no further output, check the SSE log for `permission.asked` events.

---

## SSL errors

The remote execution environment (Claude Code on the web) intercepts TLS via a proxy with a self-signed certificate. This causes `CERTIFICATE_VERIFY_FAILED` errors on outbound HTTPS calls made by the **local** Python process.

**What's affected:** Any code running locally that makes HTTPS calls to E2B — i.e. `sandbox_ctl.py` and any inline scripts that use the E2B SDK.

**Fix in `sandbox_ctl.py`:** The SSL patch at the top is intentional:
```python
ssl._create_default_https_context = ssl._create_unverified_context
```
Do not remove it.

**For inline scripts** (e.g. one-off upload/restart scripts): add the same patch at the top, or just retry — SSL errors from this proxy are often transient and a second attempt usually succeeds.

**Not affected:** Code running *inside* the sandbox (the bot itself, opencode) — those make outbound calls from E2B's network, not through the local proxy.

---

## Uploading source and restarting the bot

`just bot-start` only works for a fresh sandbox. For iterative development, upload + restart manually:

```python
# Run with: doppler run -- uv run python -c "..."
import asyncio, ssl, pathlib
ssl._create_default_https_context = ssl._create_unverified_context
from e2b import AsyncSandbox
from tgrambotz.config import settings

BOT_SRC_LOCAL = pathlib.Path('src/tgrambotz')
REMOTE_PKG = '/home/user/bot/src/tgrambotz'

async def upload_and_restart():
    sandbox_id = pathlib.Path('.sandbox-id').read_text().strip()
    sb = await AsyncSandbox.connect(sandbox_id, api_key=settings.e2b_api_key)
    for f in BOT_SRC_LOCAL.glob('*.py'):
        await sb.files.write(f'{REMOTE_PKG}/{f.name}', f.read_bytes())
    try:
        await sb.commands.run('pkill -f "python3 -m tgrambotz"', timeout=5)
    except Exception:
        pass
    await asyncio.sleep(1)
    await sb.commands.run(
        'python3 -u -m tgrambotz > /home/user/bot.log 2>&1',
        background=True, timeout=0,
        envs={'PYTHONPATH': '/home/user/bot/src', 'SANDBOX_MODE': '1'},
    )
    await asyncio.sleep(4)
    r = await sb.commands.run('tail -8 /home/user/bot.log', timeout=5)
    print(r.stdout)

asyncio.run(upload_and_restart())
```

**Important:** Use `python3 -u` (unbuffered) when starting the bot, otherwise log output is buffered and `just bot-logs` shows nothing.

---

## Active sandbox

**Sandbox ID:** `istllf6mvuac02ngv8a9u`  
**Template ID:** `7orp1t31nayml8ndjkhf`

The sandbox was created with `lifecycle={"on_timeout": "pause", "auto_resume": True}` — it auto-pauses on idle rather than terminating. `just bot-stop` permanently kills it; avoid unless starting fresh.

**Known E2B bug (#884):** Filesystem writes may not persist after the 2nd+ pause/resume cycle. The bot process (in memory) survives fine; only new file writes are affected.

---

## E2B template

**Template ID:** `7orp1t31nayml8ndjkhf`  
**Based on:** `owngk1zv1374s7wd8y6f`

Pre-installed:
- `opencode-ai` (via npm)
- `uv` (at `/home/user/.local/bin`)
- `python-telegram-bot`, `pydantic-settings`, `httpx` (via `uv pip install --system`)

**Note:** The opencode permission config (`~/.config/opencode/opencode.json`) is NOT baked into the template — it is written at runtime by `local_agent.py`. If you rebuild the template, this still works correctly.

To rebuild after `e2b.Dockerfile` changes:
```bash
just template-build
```
Never use `e2b template build` — it requires a separate browser OAuth token that doesn't work with the Doppler `E2B_API_KEY`.

---

## Secrets (Doppler project `claude-mobilr`, config `dev`)

| Variable | Purpose |
|---|---|
| `TELEGRAM_TOKEN` | Telegram bot API token |
| `E2B_API_KEY` | E2B sandbox SDK key (`e2b_...`) |
| `OPENROUTER_API_KEY` | OpenRouter LLM inference key |
| `OPENROUTER_MODEL` | Model string, format `providerID/modelID` e.g. `openrouter/deepseek/deepseek-v4-flash` |

The model string is split on the first `/` to produce `providerID` and `modelID` for the opencode API. A string like `openrouter/deepseek/deepseek-v4-flash` becomes `providerID=openrouter`, `modelID=deepseek/deepseek-v4-flash`.

---

## Common operations

```bash
# Bootstrap
just init                  # install Doppler CLI
just install               # uv sync
just auth                  # verify all credentials

# Sandbox-hosted bot
just bot-start             # create new sandbox, upload source, start bot
just bot-pause             # freeze (billing stops, state preserved)
just bot-resume            # thaw
just bot-status            # running / paused
just bot-logs              # tail last 50 lines from inside sandbox
just bot-stop              # PERMANENTLY kill sandbox + remove .sandbox-id

# Sandbox utilities
just sandboxes             # list all running sandboxes
just kill-sandboxes        # kill all sandboxes

# Template
just template-build        # rebuild E2B template via Python SDK
```

---

## What does not exist yet

- No test suite
- No multi-user isolation (one shared opencode session for all users)
- No restart-on-crash for the bot process inside the sandbox (if it dies, resume won't help — need to manually run upload_and_restart)
- No webhook mode (Telegram long-polling only)
- opencode permission config not baked into the E2B template (written at runtime instead)

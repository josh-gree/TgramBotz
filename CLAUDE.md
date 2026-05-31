# TgramBotz

## Start of every session — do this first

### Step 1 — Make `just` available

`just` is pre-installed at `~/.cargo/bin/just` but is not on PATH by default:

```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

Add this to your shell rc if needed, or use `~/.cargo/bin/just` everywhere below.

### Step 2 — Install Doppler CLI

```bash
just init       # downloads and installs the Doppler CLI via curl
```

### Step 3 — Configure Doppler project scope

`just init` installs the CLI but does not point it at a project. Without this step, all `doppler run --` commands fail with "You must specify a project":

```bash
doppler setup --project claude-mobilr --config dev --no-interactive
```

Verify it worked:

```bash
doppler whoami          # should show your workspace
doppler secrets --only-names   # should list TELEGRAM_TOKEN etc.
```

### Step 4 — Install Python deps

```bash
just install    # runs: uv sync
```

### Step 5 — Check sandbox status

```bash
cat .sandbox-id                   # must exist — see below if missing
just bot-status                   # should say "running" or "paused"
```

**If `.sandbox-id` is missing** (gitignored; not committed):

```bash
echo "inxeeydhxa10wh83vppbg" > .sandbox-id
just bot-status
```

**If `bot-status` returns 404 / "unreachable"** — the sandbox is gone and must be recreated:

```bash
rm .sandbox-id
just bot-start    # creates a new sandbox, uploads source, starts bot (~60s)
```

`just bot-start` saves the new sandbox ID to `.sandbox-id` automatically. Update the ID in this file's "Active sandbox" section and commit.

**If `bot-status` says "paused":**

```bash
just bot-resume
```

### Step 6 — Confirm the bot is polling Telegram

`just bot-logs` may appear empty due to an E2B filesystem read-caching quirk (the bot writes correctly; the SDK file-read API sometimes returns stale data). Use a shell cat instead:

```bash
doppler run -- uv run python -c "
import asyncio, ssl, pathlib
ssl._create_default_https_context = ssl._create_unverified_context
from e2b import AsyncSandbox
from tgrambotz.config import settings

async def check():
    sid = pathlib.Path('.sandbox-id').read_text().strip()
    sb = await AsyncSandbox.connect(sid, api_key=settings.e2b_api_key)
    r = await sb.commands.run('tail -20 /home/user/bot.log', timeout=10)
    print(r.stdout or '(empty)')
    r2 = await sb.commands.run('ps aux | grep -E \"tgrambotz|opencode\" | grep -v grep', timeout=5)
    print(r2.stdout)
asyncio.run(check())
"
```

A healthy bot shows log lines like:
```
INFO tgrambotz.local_agent — opencode server ready, session=ses_...
INFO telegram.ext.Application — Application started
INFO __main__ — Bot running — press Ctrl+C to stop
INFO httpx — HTTP Request: POST https://api.telegram.org/.../getUpdates "HTTP/1.1 200 OK"
```

And two processes: `python3 -u -m tgrambotz` and `opencode serve --port 7701`.

---

## What this project is

A Telegram bot that gives users access to an AI coding agent. The user sends a message; the bot runs `opencode-ai` to handle it with full tool use (Bash, Read, Write, Edit, Grep, etc.) and streams results back in real time — reasoning in a blockquote, tool calls as they execute, and the final response as plain text.

---

## Architecture

```
User (Telegram) → Telegram servers
                       ↓ long-polling
              E2B Sandbox (inxeeydhxa10wh83vppbg)
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

**Sandbox ID:** `inxeeydhxa10wh83vppbg`  
**Template ID:** `7orp1t31nayml8ndjkhf`

The sandbox was created with `lifecycle={"on_timeout": "pause", "auto_resume": True}` — it auto-pauses on idle rather than terminating. `just bot-stop` permanently kills it; avoid unless starting fresh.

**Known E2B bug (#884):** Filesystem writes may not persist after the 2nd+ pause/resume cycle. The bot process (in memory) survives fine; only new file writes are affected.

**Known E2B log-read caching quirk:** `sb.files.read('/home/user/bot.log')` and even `sb.commands.run('cat /home/user/bot.log')` can return stale (empty) content for a minute or more after the bot starts writing. The bot IS writing correctly (confirmed via `readlink /proc/<pid>/fd/1`). Work around this by triggering a shell-side write first (`echo "" >> /home/user/bot.log`) or just wait and retry with `tail -20`.

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

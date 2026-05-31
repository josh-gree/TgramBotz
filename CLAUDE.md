# TgramBotz

IMPORTANT: Run `just init` first before anything else in every new session. This installs the Doppler CLI, which is required for all commands that need secrets.

Start here: run `just` to see all available commands.

The `Justfile` is the primary reference for how to run, test, and manage the project.

---

## What this project is

A Telegram bot that gives users access to an AI coding agent. The user sends a message; the bot runs `opencode-ai` to handle it with full tool use (Bash, Read, Write, Edit, Grep, etc.) and streams the results back.

There are two deployment modes:

**Mode 1 — Local relay (original):** `just run`
- A Python process runs locally, polls Telegram, and proxies messages into an E2B sandbox running opencode.
- Requires the local machine to stay up.

**Mode 2 — Sandbox-hosted bot (current):** `just bot-start`
- The Telegram bot runs *inside* the E2B sandbox alongside opencode. No local process needed once started.
- The sandbox auto-pauses when idle and auto-resumes on Telegram activity.
- Managed with `just bot-start / bot-pause / bot-resume / bot-status / bot-logs / bot-stop`.

---

## Architecture

```
User (Telegram) → Telegram servers
                       ↓ polling
              E2B Sandbox (ig7a2ec0z5jhoek5tc6z9)
              ┌────────────────────────────────┐
              │  python3 -m tgrambotz          │
              │  (SANDBOX_MODE=1)              │
              │  → LocalOpenCodeAgent          │
              │    → opencode CLI (subprocess) │
              │      → OpenRouter (LLM)        │
              └────────────────────────────────┘
```

In sandbox mode, `local_agent.py` runs opencode as a plain subprocess — no E2B SDK calls from inside the sandbox. The local CLI (`sandbox_ctl.py`) only manages lifecycle (create/pause/resume/kill).

---

## Key files

| File | Purpose |
|---|---|
| `src/tgrambotz/__main__.py` | Entry point. Switches between `OpenCodeAgent` (E2B relay) and `LocalOpenCodeAgent` (sandbox-local) via `SANDBOX_MODE=1` env var. |
| `src/tgrambotz/agent.py` | `OpenCodeAgent` — creates E2B sandbox, runs opencode inside it, streams JSON events. Used by `just run` (local relay mode). |
| `src/tgrambotz/local_agent.py` | `LocalOpenCodeAgent` — runs opencode as a local asyncio subprocess. Used when `SANDBOX_MODE=1`. |
| `src/tgrambotz/config.py` | Pydantic settings: `TELEGRAM_TOKEN`, `E2B_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `MAX_TURNS`. |
| `scripts/sandbox_ctl.py` | CLI for sandbox-hosted bot: `start / pause / resume / status / logs / stop`. Saves sandbox ID to `.sandbox-id`. |
| `scripts/build_template.py` | Rebuilds the E2B sandbox template via Python SDK (no e2b CLI needed). Run via `just template-build`. |
| `scripts/sandboxes.py` | List/kill/new E2B sandboxes. Used by `just sandboxes` etc. |
| `scripts/check_auth.py` | Smoke-tests all credentials (Doppler, E2B, Telegram, OpenRouter). Run via `just auth`. |
| `e2b.Dockerfile` | Defines the sandbox image. Currently documents the layers — actual builds use `scripts/build_template.py` via the Python SDK, not the CLI, because the CLI requires a separate OAuth token. |
| `Justfile` | All commands. The primary operational reference. |
| `.sandbox-id` | Persists the current sandbox ID locally. Gitignored. |
| `doppler.yaml` | Points to Doppler project `claude-mobilr`, config `dev`. |

---

## E2B template

**Current template ID:** `7orp1t31nayml8ndjkhf`  
**Template name:** `tgrambotz`  
**Based on:** `owngk1zv1374s7wd8y6f` (original `e2b/code-interpreter-v1` equivalent)

Pre-installed in template:
- `opencode-ai` (via npm)
- `uv` (installed to `/home/user/.local/bin`)
- `python-telegram-bot`, `pydantic-settings` (via `uv pip install --system`)

To rebuild the template after Dockerfile changes:
```bash
just template-build   # uses scripts/build_template.py + E2B Python SDK
```
The E2B CLI (`e2b template build`) requires a separate browser-based OAuth token and does NOT work with the `E2B_API_KEY` from Doppler. Always use `just template-build` instead.

---

## Secrets (via Doppler, project `claude-mobilr`, config `dev`)

| Variable | Purpose |
|---|---|
| `TELEGRAM_TOKEN` | Telegram bot API token |
| `E2B_API_KEY` | E2B sandbox SDK key (prefix: `e2b_...`) |
| `OPENROUTER_API_KEY` | OpenRouter LLM inference key |
| `OPENROUTER_MODEL` | Model name (default: `openrouter/deepseek/deepseek-v4-flash`) |

These are injected at runtime via `doppler run --`. All `just` recipes that need secrets already wrap commands with this.

---

## E2B pause/resume behaviour

- `pause()` freezes full sandbox state (filesystem + memory + running processes). Billing stops.
- `connect(sandbox_id)` resumes a paused sandbox in ~1 second.
- Sandbox created with `lifecycle={"on_timeout": "pause", "auto_resume": True}` — it auto-pauses on idle and auto-resumes when the SDK touches it.
- **Known E2B bug:** file changes after the 2nd+ pause/resume cycle may not persist (E2B issue #884). The bot process itself (in memory) survives fine; only filesystem writes are affected.

---

## SSL in this environment

The remote execution environment intercepts TLS via a proxy with a self-signed cert. `scripts/sandbox_ctl.py` patches this at startup:
```python
ssl._create_default_https_context = ssl._create_unverified_context
```
This is intentional and scoped to that script only. Do not remove it.

---

## Common operations

```bash
just init           # install Doppler CLI (required first in every session)
just install        # uv sync — install/update Python deps
just auth           # verify all credentials work

# Sandbox-hosted bot (recommended)
just bot-start      # create sandbox, upload source, start bot, exit
just bot-pause      # freeze sandbox (billing stops)
just bot-resume     # thaw sandbox (bot continues)
just bot-status     # show sandbox state
just bot-logs       # tail last 50 lines of bot log from inside sandbox
just bot-stop       # kill sandbox permanently, remove .sandbox-id

# Local relay bot (original mode, requires local process to stay up)
just run            # start bot locally (logs to bot.log)
just logs           # tail bot.log

# Template management
just template-build # rebuild E2B sandbox template via Python SDK

# Sandbox utilities
just sandboxes      # list all running sandboxes
just kill-sandboxes # kill all sandboxes
```

---

## Tech stack

- **Python 3.11**, **uv** (package manager)
- **python-telegram-bot ^21** — Telegram long-polling
- **e2b ^2.25** — sandbox SDK (AsyncSandbox, AsyncTemplate)
- **opencode-ai CLI** — agentic tool use inside sandbox
- **OpenRouter** — LLM inference
- **Doppler** — secrets management
- **Pydantic Settings** — config

---

## What does not exist yet

- No test suite (only ad-hoc `check_auth.py` and `diagnose.py`)
- No multi-user isolation (one shared sandbox, one opencode session)
- No restart-on-crash for the bot process inside the sandbox
- No webhook mode (currently uses Telegram long-polling)

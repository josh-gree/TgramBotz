# TgramBotz — common tasks
# Usage: just <recipe>

set dotenv-load := false

# List available recipes
default:
    @just --list

# ── Bootstrap ─────────────────────────────────────────────────────────────────

# Install system dependencies (Doppler CLI)
init:
    curl -Ls --tlsv1.2 --proto "=https" https://cli.doppler.com/install.sh | sudo sh

# ── Dependencies ──────────────────────────────────────────────────────────────

# Install / sync Python dependencies
install:
    uv sync

# ── Auth ──────────────────────────────────────────────────────────────────────

# Check Doppler auth status
doppler-auth:
    doppler whoami

# Verify all credentials (Doppler secrets → E2B + Telegram)
auth:
    doppler run -- uv run python scripts/check_auth.py

# ── E2B Template ──────────────────────────────────────────────────────────────

# Rebuild the E2B sandbox template (requires e2b CLI: npm i -g @e2b/cli)
template-build:
    e2b template build --dockerfile e2b.Dockerfile

# ── Bot ───────────────────────────────────────────────────────────────────────

# Run the bot in the foreground (Ctrl+C to stop); tees output to bot.log
run:
    doppler run -- uv run python -m tgrambotz 2>&1 | tee bot.log

# Tail the bot log
logs:
    tail -f bot.log

# Show last N lines of the bot log (default 50)
log-tail n="50":
    tail -{{ n }} bot.log

# ── Sandboxes ─────────────────────────────────────────────────────────────────

# List all running E2B sandboxes
sandboxes:
    doppler run -- uv run python scripts/sandboxes.py list

# Kill all running E2B sandboxes
kill-sandboxes:
    doppler run -- uv run python scripts/sandboxes.py kill

# Kill a specific sandbox by ID
kill-sandbox id:
    doppler run -- uv run python scripts/sandboxes.py kill {{ id }}

# Start a fresh sandbox and print its ID (useful for manual debugging)
new-sandbox:
    doppler run -- uv run python scripts/sandboxes.py new

# ── Sandbox-hosted bot ────────────────────────────────────────────────────────

# Start bot inside E2B sandbox — no local process needed after this
bot-start:
    doppler run -- uv run python scripts/sandbox_ctl.py start

# Pause sandbox (state preserved, billing stops)
bot-pause:
    doppler run -- uv run python scripts/sandbox_ctl.py pause

# Resume sandbox (bot continues from frozen state)
bot-resume:
    doppler run -- uv run python scripts/sandbox_ctl.py resume

# Show sandbox status
bot-status:
    doppler run -- uv run python scripts/sandbox_ctl.py status

# Tail logs from inside the sandbox (default last 50 lines)
bot-logs n="50":
    doppler run -- uv run python scripts/sandbox_ctl.py logs {{ n }}

# Kill sandbox and remove .sandbox-id
bot-stop:
    doppler run -- uv run python scripts/sandbox_ctl.py stop

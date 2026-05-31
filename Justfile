# TgramBotz — common tasks
# Usage: just <recipe>

set dotenv-load := false

# List available recipes
default:
    @just --list

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

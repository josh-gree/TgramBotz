"""Bot sandbox lifecycle: start | pause | resume | status | logs | stop"""
import asyncio
import ssl
import sys
from pathlib import Path

# This environment intercepts TLS via a proxy with a self-signed cert.
ssl._create_default_https_context = ssl._create_unverified_context

from e2b import AsyncSandbox

from tgrambotz.agent import E2B_TEMPLATE
from tgrambotz.config import settings

SANDBOX_ID_FILE = Path(".sandbox-id")
BOT_SRC_LOCAL = Path(__file__).resolve().parent.parent / "src" / "tgrambotz"
REMOTE_PKG = "/home/user/bot/src/tgrambotz"
REMOTE_PYTHONPATH = "/home/user/bot/src"
LOG_FILE = "/home/user/bot.log"


def _read_id() -> str:
    if not SANDBOX_ID_FILE.exists():
        print("No .sandbox-id found. Run 'start' first.")
        sys.exit(1)
    return SANDBOX_ID_FILE.read_text().strip()


async def _connect(sandbox_id: str) -> AsyncSandbox:
    return await AsyncSandbox.connect(sandbox_id, api_key=settings.e2b_api_key)


async def _upload_source(sandbox: AsyncSandbox) -> None:
    files = list(BOT_SRC_LOCAL.glob("*.py"))
    for py_file in files:
        await sandbox.files.write(f"{REMOTE_PKG}/{py_file.name}", py_file.read_bytes())
    print(f"  Uploaded {len(files)} source files.")


async def _start_bot_process(sandbox: AsyncSandbox) -> None:
    await sandbox.commands.run(
        f"python3 -u -m tgrambotz > {LOG_FILE} 2>&1",
        background=True,
        timeout=0,
        envs={"PYTHONPATH": REMOTE_PYTHONPATH, "SANDBOX_MODE": "1"},
    )


async def cmd_start() -> None:
    if SANDBOX_ID_FILE.exists():
        sid = SANDBOX_ID_FILE.read_text().strip()
        print(f"Sandbox {sid} already exists. Use 'resume', 'pause', or 'stop'.")
        sys.exit(1)

    print("Creating sandbox...")
    sandbox = await AsyncSandbox.create(
        template=E2B_TEMPLATE,
        api_key=settings.e2b_api_key,
        timeout=3600,
        lifecycle={"on_timeout": "pause", "auto_resume": True},
        envs={
            "TELEGRAM_TOKEN": settings.telegram_token,
            "E2B_API_KEY": settings.e2b_api_key,
            "OPENROUTER_API_KEY": settings.openrouter_api_key,
            "OPENROUTER_MODEL": settings.openrouter_model,
        },
    )
    SANDBOX_ID_FILE.write_text(sandbox.sandbox_id)
    print(f"  Sandbox: {sandbox.sandbox_id}")

    print("Uploading source...")
    await _upload_source(sandbox)

    print("Starting bot...")
    await _start_bot_process(sandbox)

    print(f"\nBot running in sandbox {sandbox.sandbox_id}")
    print("Sandbox will auto-pause when idle and auto-resume on Telegram activity.")
    print("Sandbox ID saved to .sandbox-id")


async def cmd_pause() -> None:
    sandbox_id = _read_id()
    print(f"Pausing {sandbox_id}...")
    sandbox = await _connect(sandbox_id)
    await sandbox.pause()
    print("Paused. State preserved, billing stopped.")


async def cmd_resume() -> None:
    sandbox_id = _read_id()
    print(f"Resuming {sandbox_id}...")
    sandbox = await _connect(sandbox_id)
    info = await sandbox.get_info()
    print(f"State: {info.state}")
    print("Bot should be running. Check with: just bot-logs")


async def cmd_status() -> None:
    if not SANDBOX_ID_FILE.exists():
        print("No sandbox running. (.sandbox-id not found)")
        return
    sandbox_id = _read_id()
    try:
        sandbox = await _connect(sandbox_id)
        info = await sandbox.get_info()
        print(f"Sandbox : {sandbox_id}")
        print(f"State   : {info.state}")
    except Exception as e:
        print(f"Sandbox {sandbox_id}: unreachable ({e})")


async def cmd_logs() -> None:
    sandbox_id = _read_id()
    sandbox = await _connect(sandbox_id)
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    try:
        content = await sandbox.files.read(LOG_FILE)
        text = content if isinstance(content, str) else content.decode()
        for line in text.splitlines()[-n:]:
            print(line)
    except Exception as e:
        print(f"Could not read log: {e}")


async def cmd_stop() -> None:
    sandbox_id = _read_id()
    print(f"Killing sandbox {sandbox_id}...")
    await AsyncSandbox.kill(sandbox_id, api_key=settings.e2b_api_key)
    SANDBOX_ID_FILE.unlink(missing_ok=True)
    print("Stopped and .sandbox-id removed.")


COMMANDS = {
    "start": cmd_start,
    "pause": cmd_pause,
    "resume": cmd_resume,
    "status": cmd_status,
    "logs": cmd_logs,
    "stop": cmd_stop,
}


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd not in COMMANDS:
        print(f"Usage: sandbox_ctl.py [{' | '.join(COMMANDS)}]")
        sys.exit(1)
    asyncio.run(COMMANDS[cmd]())


if __name__ == "__main__":
    main()

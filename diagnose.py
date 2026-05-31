"""Find correct model name and test a working opencode run."""
import asyncio
import logging
from e2b import AsyncSandbox
from tgrambotz.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

TEMPLATE = "owngk1zv1374s7wd8y6f"


async def run(sb, cmd: str, timeout: float = 60, env: dict | None = None) -> str:
    lines = []
    kwargs = dict(
        background=True,
        on_stdout=lambda l: lines.append(l),
        on_stderr=lambda l: lines.append("[err] " + l),
        timeout=0,
    )
    if env:
        kwargs["envs"] = env
    try:
        handle = await sb.commands.run(cmd, **kwargs)
        await asyncio.wait_for(handle.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        lines.append("[timed out]")
    except Exception as e:
        lines.append(f"[exception: {e}]")
    return "\n".join(lines).strip()


async def main():
    sb = await AsyncSandbox.create(template=TEMPLATE, api_key=settings.e2b_api_key)
    log.info("Sandbox: %s", sb.sandbox_id)

    env = {"OPENROUTER_API_KEY": settings.openrouter_api_key}

    # List available providers
    print("--- Providers ---")
    out = await run(sb, "opencode models 2>&1 | head -40", timeout=30, env=env)
    print(out)

    # List openrouter models specifically
    print("\n--- OpenRouter models (search deepseek) ---")
    out = await run(sb, "opencode models openrouter 2>&1 | grep -i deepseek | head -20", timeout=30, env=env)
    print(out)

    # Try with the suggested model name from earlier error
    for model in ["deepseek/deepseek-v4-flash", "openrouter/deepseek/deepseek-v4-flash"]:
        print(f"\n--- Test: -m {model} ---")
        out = await run(sb, f'opencode run -m {model} "say hello" 2>&1', timeout=60, env=env)
        print(out[:500])

    await sb.kill()
    log.info("Done.")

asyncio.run(main())

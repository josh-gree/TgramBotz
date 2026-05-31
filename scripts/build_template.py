"""Rebuild the E2B sandbox template and print the new template ID."""
import asyncio

from e2b import AsyncTemplate

from tgrambotz.agent import E2B_TEMPLATE
from tgrambotz.config import settings


async def main() -> None:
    print(f"Building template based on {E2B_TEMPLATE}...")
    template = AsyncTemplate(file_context_path=".")
    builder = (
        AsyncTemplate(file_context_path=".")
        .from_template(E2B_TEMPLATE)
        .run_cmd("curl -LsSf https://astral.sh/uv/install.sh | sh")
        .set_envs({"PATH": "/home/user/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"})
        .run_cmd("uv pip install --system python-telegram-bot pydantic-settings")
    )
    final = builder.set_ready_cmd("opencode --version")

    info = await AsyncTemplate.build(
        final,
        name="tgrambotz",
        cpu_count=2,
        memory_mb=1024,
        on_build_logs=lambda log: print(log.message),
        api_key=settings.e2b_api_key,
    )
    print(f"\nTemplate ID: {info.template_id}")
    print("Update E2B_TEMPLATE in src/tgrambotz/agent.py if this is a new ID.")


if __name__ == "__main__":
    asyncio.run(main())

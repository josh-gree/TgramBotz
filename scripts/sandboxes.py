"""Sandbox management helper: list / kill / new."""
import asyncio
import sys

from e2b import AsyncSandbox

from tgrambotz.config import settings
from tgrambotz.agent import E2B_TEMPLATE


async def _fetch_all() -> list:
    p = AsyncSandbox.list(api_key=settings.e2b_api_key)
    return await p.next_items()


async def cmd_list() -> None:
    items = await _fetch_all()
    if not items:
        print("No running sandboxes.")
        return
    print(f"{'ID':<26}  {'TEMPLATE':<22}  {'STARTED':<25}  STATE")
    print("─" * 85)
    for sb in items:
        alias = getattr(sb, "alias", "") or ""
        template = f"{sb.template_id}" + (f" ({alias})" if alias else "")
        print(f"{sb.sandbox_id:<26}  {template:<22}  {sb.started_at}  {sb.state}")


async def cmd_kill(target_id: str | None = None) -> None:
    items = await _fetch_all()
    if not items:
        print("No running sandboxes.")
        return
    to_kill = [s for s in items if target_id is None or s.sandbox_id == target_id]
    if not to_kill:
        print(f"Sandbox {target_id!r} not found.")
        return
    for sb in to_kill:
        print(f"Killing {sb.sandbox_id} ...", end=" ", flush=True)
        await AsyncSandbox.kill(sb.sandbox_id, api_key=settings.e2b_api_key)
        print("done")


async def cmd_new() -> None:
    print(f"Creating sandbox from template {E2B_TEMPLATE} ...")
    sb = await AsyncSandbox.create(
        template=E2B_TEMPLATE,
        api_key=settings.e2b_api_key,
        timeout=3600,
    )
    print(f"Sandbox ID : {sb.sandbox_id}")
    print(f"Template   : {E2B_TEMPLATE}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        asyncio.run(cmd_list())
    elif cmd == "kill":
        target = sys.argv[2] if len(sys.argv) > 2 else None
        asyncio.run(cmd_kill(target))
    elif cmd == "new":
        asyncio.run(cmd_new())
    else:
        print(f"Unknown command: {cmd}. Use list / kill [id] / new")
        sys.exit(1)


if __name__ == "__main__":
    main()

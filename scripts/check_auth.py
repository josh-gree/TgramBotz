"""Verify all credentials are working."""
import asyncio

import httpx
from e2b import AsyncSandbox

from tgrambotz.config import settings


async def main() -> None:
    ok = True

    # Doppler — already resolved if we got here via `doppler run`
    print("Doppler ............. OK (secrets injected)")

    # E2B
    try:
        p = AsyncSandbox.list(api_key=settings.e2b_api_key)
        items = await p.next_items()
        print(f"E2B ................. OK ({len(items)} sandbox(es) running)")
    except Exception as e:
        print(f"E2B ................. FAIL — {e}")
        ok = False

    # Telegram
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://api.telegram.org/bot{settings.telegram_token}/getMe"
            )
        data = r.json()
        if data.get("ok"):
            bot = data["result"]
            print(f"Telegram ............ OK (@{bot['username']} / {bot['first_name']})")
        else:
            print(f"Telegram ............ FAIL — {data.get('description')}")
            ok = False
    except Exception as e:
        print(f"Telegram ............ FAIL — {e}")
        ok = False

    # OpenRouter
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                timeout=10,
            )
        if r.status_code == 200:
            print(f"OpenRouter .......... OK (model: {settings.openrouter_model})")
        else:
            print(f"OpenRouter .......... FAIL — HTTP {r.status_code}")
            ok = False
    except Exception as e:
        print(f"OpenRouter .......... FAIL — {e}")
        ok = False

    print()
    print("All checks passed." if ok else "Some checks FAILED.")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())

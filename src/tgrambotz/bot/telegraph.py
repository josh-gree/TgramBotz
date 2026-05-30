"""Telegraph API client for publishing diff pages."""
import httpx

_BASE = "https://api.telegra.ph"
_access_token: str | None = None


async def _get_token() -> str:
    global _access_token
    if _access_token:
        return _access_token
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{_BASE}/createAccount", params={
            "short_name": "TgramBotz",
            "author_name": "TgramBotz",
        })
        r.raise_for_status()
        _access_token = r.json()["result"]["access_token"]
    return _access_token


def _diff_to_nodes(filename: str, additions: int, deletions: int, diff_text: str) -> list:
    """Convert a unified diff into Telegraph Node objects."""
    nodes = [
        {"tag": "h3", "children": [filename]},
        {"tag": "p", "children": [f"+{additions} additions  -{deletions} deletions"]},
        {"tag": "hr"},
    ]

    # Split diff into labelled line groups for readability
    lines = diff_text.splitlines()
    added, removed, context = [], [], []

    def flush(buf: list, prefix: str) -> None:
        if buf:
            nodes.append({"tag": "pre", "children": ["\n".join(buf)]})
            buf.clear()

    block: list[str] = []
    for line in lines:
        block.append(line)

    # Emit as one pre block — Telegraph monospace renders + / - clearly
    if block:
        nodes.append({"tag": "pre", "children": ["\n".join(block)]})

    return nodes


async def create_diff_page(
    filename: str,
    additions: int,
    deletions: int,
    diff_text: str,
) -> str:
    """Post a diff to Telegraph and return the public URL."""
    import json
    token = await _get_token()
    nodes = _diff_to_nodes(filename, additions, deletions, diff_text)

    async with httpx.AsyncClient() as client:
        r = await client.post(f"{_BASE}/createPage", data={
            "access_token": token,
            "title": f"Diff — {filename}",
            "author_name": "TgramBotz",
            "content": json.dumps(nodes),
            "return_content": "false",
        })
        r.raise_for_status()
        result = r.json()
        if not result.get("ok"):
            raise RuntimeError(f"Telegraph error: {result}")
        return result["result"]["url"]

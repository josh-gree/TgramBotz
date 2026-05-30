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


def _node(tag: str, *children, attrs: dict | None = None) -> dict:
    n = {"tag": tag, "children": list(children)}
    if attrs:
        n["attrs"] = attrs
    return n


def _diff_to_nodes(filename: str, additions: int, deletions: int, diff_text: str) -> list:
    nodes: list = []

    # Header
    nodes.append(_node("h3", filename))
    nodes.append(_node("p",
        _node("b", f"+{additions}"),
        f" additions   ",
        _node("s", f"-{deletions}"),
        " deletions",
    ))
    nodes.append(_node("hr"))

    lines = diff_text.splitlines()
    current_hunk: list = []

    def flush_hunk() -> None:
        if current_hunk:
            nodes.append(_node("pre", *current_hunk))
            current_hunk.clear()

    for line in lines:
        if line.startswith("@@"):
            # Hunk header — emit previous block, start a new section
            flush_hunk()
            nodes.append(_node("h4", line))
        elif line.startswith("---") or line.startswith("+++"):
            # File header lines — skip (already in page title)
            continue
        elif line.startswith("+"):
            # Addition — bold
            flush_hunk()
            nodes.append(_node("p", _node("b", line)))
        elif line.startswith("-"):
            # Deletion — strikethrough
            flush_hunk()
            nodes.append(_node("p", _node("s", line)))
        else:
            # Context line — plain, group into pre blocks
            current_hunk.append(line)

    flush_hunk()
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
            "title": f"{filename}  +{additions} -{deletions}",
            "author_name": "TgramBotz",
            "content": json.dumps(nodes),
            "return_content": "false",
        })
        r.raise_for_status()
        result = r.json()
        if not result.get("ok"):
            raise RuntimeError(f"Telegraph error: {result}")
        return result["result"]["url"]

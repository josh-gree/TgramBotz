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


_PAGE_CHAR_LIMIT = 40_000  # conservative — Telegraph's JSON limit is ~64KB


async def _post_page(token: str, title: str, nodes: list) -> str:
    import json
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{_BASE}/createPage", data={
            "access_token": token,
            "title": title[:256],
            "author_name": "TgramBotz",
            "content": json.dumps(nodes),
            "return_content": "false",
        })
        r.raise_for_status()
        result = r.json()
        if not result.get("ok"):
            raise RuntimeError(f"Telegraph error: {result}")
        return result["result"]["url"]


async def create_output_page(
    cmd: str,
    output: str,
    exit_code: int | None,
    elapsed: float,
) -> str:
    """Post full command output to Telegraph, splitting into linked pages if needed."""
    import logging
    log = logging.getLogger(__name__)

    token = await _get_token()
    line_count = output.count("\n") + 1
    status = "✅ 0" if exit_code == 0 else f"❌ {exit_code}"
    header = f"exit {status}  ·  {line_count} lines  ·  {elapsed:.1f}s"

    # Split output into line-boundary chunks that fit under the page limit
    lines = output.splitlines()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        if current_len + len(line) + 1 > _PAGE_CHAR_LIMIT and current:
            chunks.append("\n".join(current))
            current, current_len = [], 0
        current.append(line)
        current_len += len(line) + 1
    if current:
        chunks.append("\n".join(current))

    total = len(chunks)
    log.info("Telegraph: %d chunk(s) for %d lines", total, line_count)

    # Create pages back-to-front so each page can link to the next
    urls: list[str] = [""] * total
    for i in range(total - 1, -1, -1):
        part_label = f"Part {i+1}/{total}" if total > 1 else ""
        title = f"$ {cmd[:50]}  {part_label}".strip()
        nodes: list = []
        if i == 0:
            nodes += [
                _node("h3", f"$ {cmd}"),
                _node("p", header),
                _node("hr"),
            ]
        else:
            nodes.append(_node("p", _node("b", f"Part {i+1} of {total}")))
        nodes.append(_node("pre", chunks[i]))
        if i < total - 1:
            nodes.append(_node("p", _node("a", f"→ Part {i+2}", attrs={"href": urls[i+1]})))
        urls[i] = await _post_page(token, title, nodes)
        log.info("Telegraph page %d/%d: %s", i + 1, total, urls[i])

    return urls[0]


async def create_file_page(filename: str, content: str) -> str:
    """Post a file's content to Telegraph and return the public URL."""
    import json
    token = await _get_token()

    # Guess language from extension for the code block
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    lang_map = {
        "py": "python", "js": "javascript", "ts": "typescript",
        "jsx": "javascript", "tsx": "typescript", "go": "go",
        "rs": "rust", "rb": "ruby", "sh": "bash", "yml": "yaml",
        "yaml": "yaml", "json": "json", "md": "markdown",
        "toml": "toml", "sql": "sql", "html": "html", "css": "css",
    }
    lang = lang_map.get(ext, "")
    lines = content.count("\n") + 1

    nodes = [
        _node("h3", filename),
        _node("p", f"{lines} lines"),
        _node("hr"),
        _node("pre", _node("code", content, attrs={"class": f"language-{lang}"}) if lang else content),
    ]

    async with httpx.AsyncClient() as client:
        r = await client.post(f"{_BASE}/createPage", data={
            "access_token": token,
            "title": filename,
            "author_name": "TgramBotz",
            "content": json.dumps(nodes),
            "return_content": "false",
        })
        r.raise_for_status()
        result = r.json()
        if not result.get("ok"):
            raise RuntimeError(f"Telegraph error: {result}")
        return result["result"]["url"]


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

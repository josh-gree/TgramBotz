from tgrambotz.events.types import (
    ApprovalRequestEvent,
    BashEvent,
    ErrorEvent,
    PatchEvent,
    ReadFileEvent,
    ResultEvent,
    ThinkingEvent,
    WriteFileEvent,
)


def render_event(event: object) -> str:
    match event:
        case ThinkingEvent(text=text):
            body = f"\n{text}" if text else ""
            return f"🧠 Thinking{body}"
        case ReadFileEvent(filename=f):
            return f"📖 {f}"
        case WriteFileEvent(filename=f):
            return f"✏️ {f}"
        case PatchEvent(filename=f, additions=a, deletions=d):
            return f"✏️ {f}\n+{a} -{d}"
        case BashEvent(command=cmd, output=out):
            body = f"\n<pre>{_truncate(out)}</pre>" if out else ""
            return f"🧪 <code>{cmd}</code>{body}"
        case ResultEvent(summary=s, files_modified=fm, tests_passed=tp):
            parts = [f"✅ {s}"]
            if fm:
                parts.append(f"Files modified: {fm}")
            if tp is not None:
                parts.append(f"Tests passed: {tp}")
            return "\n".join(parts)
        case ErrorEvent(message=msg):
            return f"❌ {msg}"
        case ApprovalRequestEvent(description=desc, command=cmd):
            lines = [f"⚠️ <b>Approval Required</b>", "", desc]
            if cmd:
                lines += ["", f"Run:\n<code>{cmd}</code>"]
            return "\n".join(lines)
        case _:
            return str(event)


def _truncate(text: str, max_lines: int = 30) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    kept = lines[-max_lines:]
    return f"... {len(lines) - max_lines} lines\n" + "\n".join(kept)

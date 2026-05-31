from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class BuildContext:
    dockerfile: Path
    context: Path
    command: str = "bash"


DEFAULT = BuildContext(
    dockerfile=Path(__file__).parent / "default" / "Dockerfile",
    context=Path(__file__).parent / "default",
    command="opencode",
)

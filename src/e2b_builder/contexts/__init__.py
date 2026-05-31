from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BuildContext:
    dockerfile: Path
    context: Path


DEFAULT = BuildContext(
    dockerfile=Path(__file__).parent / "default" / "Dockerfile",
    context=Path(__file__).parent / "default",
)

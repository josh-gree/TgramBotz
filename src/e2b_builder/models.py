from dataclasses import dataclass


@dataclass(frozen=True)
class BuildResult:
    template_id: str
    name: str

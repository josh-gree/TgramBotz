from dataclasses import dataclass


@dataclass(frozen=True)
class BuildResult:
    template_id: str
    name: str


@dataclass(frozen=True)
class RunResult:
    stdout: str
    stderr: str
    exit_code: int

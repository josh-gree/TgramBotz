from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ThinkingEvent:
    text: str = ""


@dataclass
class ReadFileEvent:
    filename: str


@dataclass
class WriteFileEvent:
    filename: str


@dataclass
class PatchEvent:
    filename: str
    additions: int = 0
    deletions: int = 0
    patch_text: str = ""


@dataclass
class BashEvent:
    command: str
    output: str = ""


@dataclass
class ResultEvent:
    summary: str
    files_modified: int = 0
    tests_passed: Optional[int] = None


@dataclass
class ErrorEvent:
    message: str


@dataclass
class ApprovalRequestEvent:
    description: str
    command: str = ""


@dataclass
class ApprovalResponseEvent:
    approved: bool


Event = (
    ThinkingEvent
    | ReadFileEvent
    | WriteFileEvent
    | PatchEvent
    | BashEvent
    | ResultEvent
    | ErrorEvent
    | ApprovalRequestEvent
    | ApprovalResponseEvent
)

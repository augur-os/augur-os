from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Status = Literal["ok", "guide", "fail"]


@dataclass(frozen=True)
class StepResult:
    status: Status
    message: str
    details: dict = field(default_factory=dict)

    @property
    def is_ok(self) -> bool:
        return self.status == "ok"

    @classmethod
    def ok(cls, message: str, details: dict | None = None) -> "StepResult":
        return cls("ok", message, details or {})

    @classmethod
    def guide(cls, message: str, details: dict | None = None) -> "StepResult":
        return cls("guide", message, details or {})

    @classmethod
    def fail(cls, message: str, details: dict | None = None) -> "StepResult":
        return cls("fail", message, details or {})


@dataclass
class OnboardContext:
    repo_root: Path
    non_interactive: bool = False

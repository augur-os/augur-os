from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class SourceResult:
    text: str
    citations: list[str] = field(default_factory=list)
    truncated: bool = False


class SourceAdapter(Protocol):
    kind: str

    def resolve(self, spec: dict, budget_tokens: int) -> SourceResult:
        ...

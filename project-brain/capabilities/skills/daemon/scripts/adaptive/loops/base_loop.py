"""Abstract base class for adaptive loops."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LoopResult:
    """Result of a single loop action execution."""

    success: bool
    action: str
    category: str
    files: list[str] = field(default_factory=list)
    commit: str | None = None
    error: str | None = None
    duration_ms: int = 0


class BaseLoop(ABC):
    """Abstract base for all adaptive loops.

    Subclasses must define:
    - NAME: unique identifier for the loop
    - TRIGGER: "continuous", "nightly", or "post-execution"
    - scan(): discover actions to take
    - execute_action(): perform a single action
    """

    NAME: str = ""
    TRIGGER: str = "nightly"

    @abstractmethod
    def scan(self, difficulties: dict[str, int] | None = None) -> list[dict]:
        """Discover actionable items. Returns list of action dicts.

        Each dict should have at minimum:
        - "action": str -- what to do
        - "category": str -- trust category this falls under
        - "files": list[str] -- optional list of target files

        Args:
            difficulties: Per-category difficulty levels (0=trivial .. 4=expert).
                Loops can use this to broaden scope at higher difficulties.
        """
        ...

    @abstractmethod
    def execute_action(self, action: dict) -> LoopResult:
        """Execute a single action. Returns LoopResult."""
        ...

    def finalize(self) -> None:
        """Called by the engine after a cycle completes.

        Override to flush batched work (e.g., staged git commits)
        that would otherwise be lost if the budget ran out mid-cycle.
        """

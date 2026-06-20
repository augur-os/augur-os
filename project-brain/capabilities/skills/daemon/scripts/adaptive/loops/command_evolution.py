"""Command evolution adaptive loop — DEPRECATED (ADR-200).

The scan/fix logic has been extracted into the standalone auto-command module:

    skills/ai/scripts/ops/command_evolution.py

The daemon engine discovers and runs that module directly via the OpsCommand
protocol.  This class is retained only for backward-compatibility with any
code that imports NAME or TRIGGER, and will be removed in a future cleanup.
"""
from __future__ import annotations

from pathlib import Path

from .base_loop import BaseLoop, LoopResult

# Category -> ImprovementType mapping kept for any external consumers
CATEGORY_TYPES = {
    "timeout-hints": {"add_timeout", "add_hint"},
    "cache-keys": {"add_cache"},
    "missing-steps": {"add_step", "add_check"},
    "reorder-phases": {"reorder_phase"},
    "remove-steps": {"remove_step"},
}


class CommandEvolutionLoop(BaseLoop):
    """Deprecated shell — all logic lives in auto-command-evolution (ADR-200)."""

    NAME = "command-evolution"
    TRIGGER = "post-execution"

    def __init__(
        self,
        project_root: Path,
        runtime_dir: Path,
    ) -> None:
        self._root = project_root
        self._runtime_dir = runtime_dir

    def scan(self, difficulties: dict[str, int] | None = None) -> list[dict]:
        """Deprecated: returns empty list.

        Use skills/ai/scripts/ops/command_evolution.py instead.
        """
        return []

    def execute_action(self, action: dict) -> LoopResult:
        """Deprecated: returns an error directing callers to auto-command-evolution.

        Use skills/ai/scripts/ops/command_evolution.py instead.
        """
        return LoopResult(
            success=False,
            action=action.get("action", "unknown"),
            category=action.get("category", "unknown"),
            error=(
                "CommandEvolutionLoop is deprecated (ADR-200). "
                "Use auto-command-evolution OpsCommand module instead: "
                "skills/ai/scripts/ops/command_evolution.py"
            ),
            duration_ms=0,
        )

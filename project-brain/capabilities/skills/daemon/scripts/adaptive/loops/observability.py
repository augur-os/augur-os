"""Observability adaptive loop -- DEPRECATED (ADR-200).

All scan/fix logic lives in standalone auto-command modules:
  - auto-repo-sync     (skills/routine-platform/scripts/repo_sync.py)
  - auto-context-audit (skills/routine-vault/scripts/context_audit.py)
  - auto-perf-profile  (skills/routine-platform/scripts/perf_profile.py)

The adaptive engine discovers and runs these via SKILL.md frontmatter.
This class is retained only for backward compatibility.
"""
from __future__ import annotations

from pathlib import Path

from .base_loop import BaseLoop, LoopResult


class ObservabilityLoop(BaseLoop):
    """Deprecated stub -- see scripts/ops/ for actual implementations."""

    NAME = "observability"
    TRIGGER = "nightly"

    def __init__(self, project_root: Path) -> None:
        self._root = project_root

    def scan(self, difficulties: dict[str, int] | None = None) -> list[dict]:
        """No-op: scanning now handled by auto-command modules."""
        return []

    def execute_action(self, action: dict) -> LoopResult:
        """No-op: execution now handled by auto-command modules."""
        return LoopResult(
            success=False,
            action=action.get("action", "unknown"),
            category=action.get("category", "unknown"),
            error="Deprecated: observability categories migrated to auto-commands (ADR-200)",
        )

"""Self-heal loop wrapper — DEPRECATED (ADR-200).

The scan/fix logic has been extracted to the auto-command module:
  project-brain/capabilities/skills/daemon/scripts/ops/self_heal.py

The adaptive engine now discovers and executes it directly via the
OpsCommand protocol declared in SKILL.md frontmatter.

This class is kept as a thin backward-compatible shell so that existing
imports and `adaptive_loop_executor.py` registrations do not crash during
the ADR-200 migration window. It produces no work — scan returns [] and
execute_action returns an error directing callers to the new location.

Remove this file once adaptive_loop_executor.py is updated per ADR-200
Step 4.3.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base_loop import BaseLoop, LoopResult

# Severity -> engine category mapping (preserved for any external references)
SEVERITY_CATEGORY_MAP = {
    "critical": "import-fixes",
    "high": "config-fixes",
    "medium": "logic-fixes",
    "low": "logic-fixes",
}


class SelfHealLoop(BaseLoop):
    """Deprecated stub — see project-brain/capabilities/skills/daemon/scripts/ops/self_heal.py."""

    NAME = "self-heal"
    TRIGGER = "continuous"

    def __init__(
        self,
        project_root: Path,
        healer_module: Any = None,
    ) -> None:
        self._root = project_root
        self._healer = healer_module

    def scan(self, difficulties: dict[str, int] | None = None) -> list[dict]:
        """Deprecated: returns empty list. Scanning is now handled by auto-self-heal (ADR-200)."""
        return []

    def execute_action(self, action: dict) -> LoopResult:
        """Deprecated: returns error. Fixes are now handled by auto-self-heal (ADR-200)."""
        return LoopResult(
            success=False,
            action=action.get("action", "unknown"),
            category=action.get("category", "logic-fixes"),
            error=(
                "SelfHealLoop is deprecated (ADR-200). "
                "Use auto-self-heal via scripts/ops/self_heal.py."
            ),
        )

    def _severity_to_category(self, severity: str) -> str:
        return SEVERITY_CATEGORY_MAP.get(severity, "logic-fixes")

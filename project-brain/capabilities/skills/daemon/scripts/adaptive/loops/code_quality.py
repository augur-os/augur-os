"""Code quality adaptive loop — DEPRECATED.

All scan/fix logic has been extracted to standalone auto-* command modules
in skills/platform-admin/scripts/ops/ (ADR-200).

The engine now discovers and runs these commands via SKILL.md frontmatter.
This class is retained only for backward compatibility during transition.
"""
from __future__ import annotations

from pathlib import Path

from .base_loop import BaseLoop, LoopResult


class CodeQualityLoop(BaseLoop):
    """Deprecated: use auto-commands via engine discovery instead.

    All 7 categories have been extracted:
      - log-maintenance -> auto-logs    (skills/routine-platform/scripts/logs.py)
      - format          -> auto-format  (scripts/ops/format.py)
      - lint-autofix    -> auto-lint    (scripts/ops/lint.py)
      - todo-cleanup    -> auto-todo-cleanup (scripts/ops/todo_cleanup.py)
      - type-errors     -> auto-types   (scripts/ops/types.py)
      - todo-outdated   -> auto-todo-outdated (scripts/ops/todo_outdated.py)
    """

    NAME = "code-quality"
    TRIGGER = "mixed"

    def __init__(self, project_root: Path, cli_path: str | None = None) -> None:
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
            error="Deprecated: code-quality categories migrated to auto-commands (ADR-200)",
        )

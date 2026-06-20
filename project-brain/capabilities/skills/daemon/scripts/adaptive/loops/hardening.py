"""Hardening adaptive loop — DEPRECATED shell.

All scan and fix logic has been extracted to standalone auto-command modules
as part of ADR-200 (dev-loops / auto-commands separation).

Category → module mapping:
  build-health        -> scripts/ops/build_health.py   (auto-build-health)
  page-mount-check    -> scripts/ops/page_mounts.py    (auto-page-mounts)
  stale-action-page   -> scripts/ops/stale_actions.py  (auto-stale-actions)
  api-route-health    -> scripts/ops/api_health.py     (auto-api-health)
  dependency-audit    -> skills/routine-platform/scripts/dependency_audit.py (auto-dependency-audit)
  plugin-template-lint -> skills/routine-platform/scripts/plugin_lint.py   (auto-plugin-lint)
  stale-path-scan     -> scripts/ops/stale_paths.py    (auto-stale-paths)

This class is retained only for backward compatibility with any code that
references HardeningLoop.NAME or HardeningLoop.TRIGGER.
Do NOT add new scan or fix logic here.
"""
from __future__ import annotations

from pathlib import Path

from .base_loop import BaseLoop, LoopResult


class HardeningLoop(BaseLoop):
    """Deprecated hardening loop shell. See module docstring for ADR-200 migration."""

    NAME = "hardening"
    TRIGGER = "nightly"

    def __init__(
        self,
        project_root: Path,
        cli_path: str | None = None,
        report_dir: Path | None = None,
    ) -> None:
        self._root = project_root
        self._cli = cli_path
        self._report_dir = report_dir or (
            project_root / "docs" / "generated" / "hardening"
        )

    def scan(self, difficulties: dict[str, int] | None = None) -> list[dict]:
        """Deprecated: returns empty list. Use auto-command modules instead.

        See ADR-200 and the module-level docstring for the full category → module mapping.
        """
        return []

    def execute_action(self, action: dict) -> LoopResult:
        """Deprecated: returns error. Use auto-command modules instead.

        See ADR-200 and the module-level docstring for the full category → module mapping.
        """
        category = action.get("category", "unknown")
        return LoopResult(
            success=False,
            action=action.get("action", "unknown"),
            category=category,
            error=(
                f"HardeningLoop is deprecated (ADR-200). "
                f"Category '{category}' is now handled by the corresponding "
                f"auto-command module in scripts/ops/. "
                f"See project-brain/capabilities/skills/daemon/SKILL.md for registration."
            ),
            duration_ms=0,
        )

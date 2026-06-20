"""Git worktree root helpers for generated runtime projections."""

from __future__ import annotations

from pathlib import Path

from src.config.runtime_identity import main_checkout_for_worktree


def is_linked_worktree(project_root: Path) -> bool:
    """Return True when project_root is a linked worktree rather than the main checkout."""
    return main_checkout_for_worktree(project_root) is not None

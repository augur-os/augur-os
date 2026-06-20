"""Find staged/draft leftovers that must remain Browse-Drafts-only (ADR-734 D6)."""

from __future__ import annotations

from pathlib import Path

_DRAFT_GLOBS = ("project-brain/capabilities/skills/**/*.draft.md",)


def find_draft_leftovers(project_root: Path) -> list[Path]:
    """Return draft files that should not appear in generated client surfaces."""
    found: list[Path] = []
    for pattern in _DRAFT_GLOBS:
        found.extend(sorted(project_root.glob(pattern)))
    return sorted(set(found))

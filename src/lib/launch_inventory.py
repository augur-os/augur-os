"""Launch-scope inventory helpers for public trust surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.paths import get_project_brain_skills_dir


@dataclass(frozen=True)
class LaunchSkillInventory:
    live_top_level: int
    staged_total: int
    staged_by_release: dict[str, int]


def count_launch_skills(project_root: Path) -> LaunchSkillInventory:
    """Count live project-brain skills and staged release skills from the repo tree."""
    root = project_root.resolve()
    skills_dir = get_project_brain_skills_dir(root)
    staging_dir = root / "staging"

    live_top_level = 0
    if skills_dir.exists():
        live_top_level = sum(1 for child in skills_dir.iterdir() if child.is_dir() and (child / "SKILL.md").exists())

    staged_by_release: dict[str, int] = {}
    if staging_dir.exists():
        for release_dir in sorted(path for path in staging_dir.iterdir() if path.is_dir()):
            count = len(list((release_dir / "skills").glob("*/SKILL.md")))
            if count:
                staged_by_release[release_dir.name] = count

    return LaunchSkillInventory(
        live_top_level=live_top_level,
        staged_total=sum(staged_by_release.values()),
        staged_by_release=staged_by_release,
    )

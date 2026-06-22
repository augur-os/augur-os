"""Build generated release-planning summaries for managed live skills."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config.paths import get_vault_dir
from src.lib.skill_release import (
    GROUP_VALUES,
    RELEASE_ORDER,
    RELEASE_VALUES,
    enabled_release_tags,
    ensure_valid_group,
    ensure_valid_release,
)
from src.plugins.skill_discovery import SkillRecord


def _relative_path(path: Path, project_root: Path) -> str:
    vault_root = get_vault_dir()
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        try:
            return (Path("vault") / path.relative_to(vault_root)).as_posix()
        except ValueError:
            return str(path)


def _is_inactive_vault_root_path(path: Path) -> bool:
    vault_root = get_vault_dir()
    try:
        relative = path.relative_to(vault_root)
    except ValueError:
        return False
    if not relative.parts:
        return False
    return relative.parts[0] in {"drafts", "archive", "_drafts"}


def _required_dependencies(raw: dict[str, Any] | None) -> list[str]:
    if not raw:
        return []
    required = raw.get("required")
    if not isinstance(required, list):
        return []
    return sorted(str(dependency) for dependency in required)


def _release_target_summary(rows: list[dict[str, Any]], target_release: str) -> dict[str, Any]:
    enabled_releases = list(enabled_release_tags(target_release))
    enabled_skills = [row["name"] for row in rows if row["release"] in enabled_releases]
    return {
        "enabled_releases": enabled_releases,
        "count": len(enabled_skills),
        "skills": enabled_skills,
    }


def _row_for_record(record: SkillRecord, project_root: Path) -> dict[str, Any]:
    if not record.group:
        raise ValueError(f"Skill {record.name} is missing x-augur-group")
    if not record.release:
        raise ValueError(f"Skill {record.name} is missing x-augur-release")

    group = ensure_valid_group(record.group)
    release = ensure_valid_release(record.release)
    return {
        "name": record.name,
        "path": _relative_path(record.path, project_root),
        "hub": record.hub,
        "group": group,
        "release": release,
        "visibility": record.visibility,
        "requires_platform": record.requires_platform,
        "required_dependencies": _required_dependencies(record.dependencies),
    }


def build_skill_release_matrix(records: list[SkillRecord], project_root: Path) -> dict[str, Any]:
    """Build the committed release matrix for managed live skills."""
    rows = [
        _row_for_record(record, project_root)
        for record in sorted(
            (record for record in records if record.tier == 0 and not _is_inactive_vault_root_path(record.path)),
            key=lambda item: item.name,
        )
    ]

    release_counts = {release: sum(1 for row in rows if row["release"] == release) for release in RELEASE_VALUES}
    group_counts = {group: sum(1 for row in rows if row["group"] == group) for group in GROUP_VALUES}
    targets = {release: _release_target_summary(rows, release) for release in RELEASE_ORDER}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "release_order": list(RELEASE_VALUES),
        "group_values": list(GROUP_VALUES),
        "release_counts": release_counts,
        "group_counts": group_counts,
        "targets": targets,
        "skills": rows,
    }

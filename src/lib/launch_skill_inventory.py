"""Build the managed launch skill inventory."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config.paths import get_vault_dir
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


def _load_rank(skill_dir: Path) -> tuple[str | None, float | None]:
    rank_path = skill_dir / "evals" / "rank.json"
    if not rank_path.is_file():
        return None, None
    try:
        payload = json.loads(rank_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid rank metadata at {rank_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Invalid rank metadata at {rank_path}: expected a JSON object")

    tier = payload.get("tier")
    score = payload.get("score")

    if tier is None or score is None:
        raise ValueError(f"Invalid rank metadata at {rank_path}: expected 'tier' and 'score' fields")

    quality_tier = str(tier)
    try:
        quality_score = float(score)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid rank metadata at {rank_path}: score must be numeric") from None

    return quality_tier, quality_score


def _row_for_record(record: SkillRecord, project_root: Path) -> dict[str, Any]:
    quality_tier, quality_score = _load_rank(record.path)
    return {
        "name": record.name,
        "path": _relative_path(record.path, project_root),
        "hub": record.hub,
        "group": record.group,
        "release": record.release,
        "visibility": record.visibility,
        "category": record.category,
        "requires_platform": record.requires_platform,
        "ownership": record.ownership,
        "source": record.source,
        "quality_tier": quality_tier,
        "quality_score": quality_score,
    }


def build_launch_skill_inventory(records: list[SkillRecord], project_root: Path) -> dict[str, Any]:
    """Build the launch inventory for tier-0 skills only."""
    rows = [
        _row_for_record(record, project_root)
        for record in sorted((record for record in records if record.tier == 0), key=lambda item: item.name)
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "skills": rows,
    }

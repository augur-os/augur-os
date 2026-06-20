"""Gate and target partition for layered home-dir projection (ADR-782 C1d)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from src.lib.brain_registry_models import BrainType
from src.lib.brain_stack import BrainStack


def _pref_home_sync() -> bool | None:
    try:
        from src.config.paths import get_project_root

        prefs = get_project_root() / "config" / "preferences.yaml"
        if not prefs.is_file():
            return None
        data = yaml.safe_load(prefs.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return None
        block = data.get("home_sync") or {}
        if not isinstance(block, dict):
            return None
        value = block.get("enabled")
        return bool(value) if value is not None else None
    except Exception:
        return None


def home_sync_enabled() -> bool:
    """Return whether outward-facing client HOME writes are explicitly enabled."""
    env = os.environ.get("AUGUR_HOME_SYNC")
    if env is not None:
        return env.strip().lower() in {"1", "true", "yes", "on"}
    return bool(_pref_home_sync())


def partition_skills_by_target(
    stack: BrainStack,
    *,
    project_root: Path | None = None,
) -> tuple[set[str], set[str]]:
    """Return ``(home_skills, repo_skills)`` by each skill's winning tier."""
    from src.lib.brain_effective import compute_effective_skills
    from src.lib.brain_layered_projection import resolve_layered_projection

    effective = compute_effective_skills(resolve_layered_projection(stack, project_root=project_root))
    home: set[str] = set()
    repo: set[str] = set()
    for name, entry in effective.entries.items():
        if entry.winner_tier is BrainType.PROJECT:
            repo.add(name)
        else:
            home.add(name)
    return home, repo

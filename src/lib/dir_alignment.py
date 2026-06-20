"""Directory alignment validation — enforces first-level dirs match skill names.

Spec: docs/superpowers/specs/2026-03-23-dir-alignment-design.md
"""

from __future__ import annotations

import difflib
import functools
from dataclasses import dataclass
from pathlib import Path

from src.logging import get_entity_logger

logger = get_entity_logger("lib.dir_alignment")

FUZZY_THRESHOLD = 0.85

# Vault dirs written by Augur runtime tools, valid in every vault:
# system/pins.yaml (pin-card), integrations/*.yaml (onboard CLI scan),
# prompts/*.md (ADR-748 vault prompt cards).
AUGUR_RUNTIME_DIRS = frozenset({"system", "integrations", "prompts"})


def _get_all_client_skill_dirs() -> list[Path]:
    """Return all client skill directories. Separate function for testability."""
    from src.config.paths import get_all_client_skill_dirs

    return get_all_client_skill_dirs()


@dataclass
class ManagedLocation:
    """An external directory whose first-level subdirs must match skill names."""

    path: Path
    reserved_file: str = ".augur-reserved"


def get_managed_locations() -> list[ManagedLocation]:
    """Read vault + documents paths from project.yaml via get_project_paths()."""
    from src.config.paths import get_project_paths

    project_paths = get_project_paths()
    if not project_paths:
        logger.warning("No paths: block in project.yaml — dir alignment has nothing to scan")
        return []
    locations: list[ManagedLocation] = []
    for key in ("vault", "documents"):
        path = project_paths.get(key)
        if path and path.is_dir():
            locations.append(ManagedLocation(path=path))
    return locations


def get_reserved_names(location: ManagedLocation) -> set[str]:
    """Read .augur-reserved from location root. Return empty set if missing."""
    reserved_path = location.path / location.reserved_file
    if not reserved_path.exists():
        return set()
    names: set[str] = set()
    for line in reserved_path.read_text().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            names.add(stripped)
    return names


@functools.lru_cache(maxsize=1)
def get_skill_names() -> frozenset[str]:
    """List all known skill names. The filesystem is the source of truth.

    Cached for the lifetime of the process — skill dirs don't change mid-run.
    Call get_skill_names.cache_clear() in tests to reset.
    """
    names: set[str] = set()
    for skills_dir in _get_all_client_skill_dirs():
        if not skills_dir.is_dir():
            continue
        for d in skills_dir.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                names.add(d.name)
    return frozenset(names)


def validate_dir_name(location: ManagedLocation, dir_name: str) -> bool:
    """Return True if dir_name is a skill name, reserved name, or brain skeleton dir."""
    reserved = get_reserved_names(location)
    skills = get_skill_names()
    if dir_name in reserved or dir_name in skills:
        return True
    from src.lib.brain_manifest import brain_skeleton_top_dirs, is_brain_root
    from src.lib.brain_layout import brain_layout

    if is_brain_root(location.path):
        if dir_name in brain_skeleton_top_dirs(brain_layout(location.path)) or dir_name in AUGUR_RUNTIME_DIRS:
            return True
    try:
        from src.config.paths import find_skill_root

        return find_skill_root(dir_name) is not None
    except Exception:
        return False


def _skill_match_score(dir_name: str, skill: str) -> float:
    """Compute match score between dir_name and a skill name.

    Returns 1.0 when dir_name is a bounded prefix of skill (e.g. "consulting"
    vs "consulting-template"), otherwise falls back to SequenceMatcher ratio.
    """
    if len(dir_name) >= 4 and any(skill.startswith(f"{dir_name}{sep}") for sep in ("-", "_")):
        return 1.0
    return difflib.SequenceMatcher(None, dir_name, skill).ratio()


def find_closest_skill(dir_name: str) -> tuple[str, float] | None:
    """Return (skill_name, score) if fuzzy match score >= 0.85, else None."""
    skills = get_skill_names()
    if not skills:
        return None
    best_name = ""
    best_score = 0.0
    for skill in skills:
        score = _skill_match_score(dir_name, skill)
        if score > best_score:
            best_score = score
            best_name = skill
    if best_score >= FUZZY_THRESHOLD:
        return (best_name, best_score)
    return None


def classify_violation(location: ManagedLocation, dir_name: str) -> str:
    """Return 'trivial-rename' | 'new-skill-candidate' | 'unknown'."""
    closest = find_closest_skill(dir_name)
    if closest is not None:
        return "trivial-rename"

    dir_path = location.path / dir_name
    if dir_path.is_dir():
        children = list(dir_path.iterdir())
        file_count = sum(1 for c in children if c.is_file())
        subdir_count = sum(1 for c in children if c.is_dir())
        if file_count >= 3 or subdir_count >= 1:
            return "new-skill-candidate"

    return "unknown"

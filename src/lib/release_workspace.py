"""Helpers for pruning a release workspace to an enabled skill set."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

from src.config.paths import get_project_brain_skills_dir
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.skill_release import is_release_enabled, validate_dependency_closure
from src.plugins.skill_discovery import normalize_skill_id

MVP_RELEASE_PRUNE_DIRS = (
    "docs/superpowers",
    "project-brain/capabilities/skills/rag/assets/seeds/rag",
    # Owner-private memory layer (ADR-814): never ships; new owner starts fresh.
    "project-brain/knowledge/memory",
)

MVP_RELEASE_PRUNE_FILES = (
    "docs/generated/vault-cleanup-report.md",
    # Generated MEMORY.md index is rebuilt from knowledge/memory/entries/ —
    # prune together with the entries dir so the shipped brain starts empty.
    "project-brain/MEMORY.md",
)

MVP_RELEASE_PRUNE_GLOBS = (
    "project-brain/capabilities/skills/*/references/*additional-resources.md",
    "**/references/*additional-resources.md",
)


def _dependencies_for_frontmatter(frontmatter: dict[str, object]) -> dict[str, object]:
    raw_dependencies = frontmatter.get("x-augur-dependencies")
    if isinstance(raw_dependencies, dict):
        return raw_dependencies

    augur_config = frontmatter.get("x-augur-config")
    if isinstance(augur_config, dict):
        config_dependencies = augur_config.get("dependencies")
        if isinstance(config_dependencies, dict):
            return config_dependencies

    return {}


def _load_release_records(project_root: Path) -> list[SimpleNamespace]:
    records: list[SimpleNamespace] = []
    for skill_md in sorted(get_project_brain_skills_dir(project_root).glob("*/SKILL.md")):
        frontmatter, _body = parse_frontmatter(skill_md)
        records.append(
            SimpleNamespace(
                name=normalize_skill_id(str(frontmatter.get("name") or skill_md.parent.name)),
                path=skill_md.parent,
                release=frontmatter.get("x-augur-release"),
                dependencies=_dependencies_for_frontmatter(frontmatter),
            )
        )
    return records


def prune_release_workspace(project_root: Path, target: str) -> dict[str, list[str]]:
    """Delete skills that are not enabled for the target release."""
    records = _load_release_records(project_root)
    errors = validate_dependency_closure(records, target)
    if errors:
        raise ValueError(", ".join(errors))

    enabled: list[str] = []
    removed: list[str] = []
    for record in records:
        if is_release_enabled(record.release, target):
            enabled.append(record.name)
            continue
        shutil.rmtree(record.path)
        if record.path.exists():
            raise RuntimeError(f"Failed to remove disabled skill directory: {record.path}")
        removed.append(record.name)

    removed_artifacts = _prune_release_artifacts(project_root, target)

    return {
        "enabled": sorted(enabled),
        "removed": sorted(removed),
        "removed_artifacts": sorted(removed_artifacts),
    }


def _prune_release_artifacts(project_root: Path, target: str) -> list[str]:
    """Remove private planning residue and generated local reports from public MVP trees."""
    if target != "mvp":
        return []

    removed: list[str] = []
    for rel_dir in MVP_RELEASE_PRUNE_DIRS:
        path = project_root / rel_dir
        if path.exists():
            shutil.rmtree(path)
            removed.append(rel_dir)

    for rel_file in MVP_RELEASE_PRUNE_FILES:
        path = project_root / rel_file
        if path.exists():
            path.unlink()
            removed.append(rel_file)

    for pattern in MVP_RELEASE_PRUNE_GLOBS:
        for path in project_root.glob(pattern):
            if path.is_file():
                path.unlink()
                removed.append(path.relative_to(project_root).as_posix())

    return removed

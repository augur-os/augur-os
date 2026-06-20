"""Helpers for moving non-MVP skills into vault drafts/staging release payloads."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from src.config.paths import get_project_brain_skills_dir, get_vault_staging_dir
from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter
from src.lib.porting_payload import STAGED_RELEASES, ensure_valid_staged_release
from src.lib.staged_skill_catalog import iter_live_skill_dirs

MVP_RELEASE = "mvp"
RELEASE_MOTIVES = {
    "r1": "personal operating system",
    "r2": "creation and ingestion expansion",
    "r3": "admin / builder / advanced operational",
    "r4": "ambient life + business expansion",
    "later": "unscheduled backlog",
}


def _skill_release(skill_dir: Path) -> str:
    metadata, _body = parse_frontmatter(skill_dir / "SKILL.md", include_sidecar_config=False)
    release = str(metadata.get("x-augur-release") or "").strip()
    if not release:
        raise ValueError(f"{skill_dir.name} is missing x-augur-release")
    return release


def _release_root(project_root: Path, release: str) -> Path:
    return get_vault_staging_dir() / release


def _release_skill_names(release_root: Path) -> list[str]:
    skills_root = release_root / "skills"
    if not skills_root.exists():
        return []
    return sorted(
        skill_dir.name
        for skill_dir in skills_root.iterdir()
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists()
    )


def _release_page_paths(release_root: Path) -> list[str]:
    pages_root = release_root / "pages"
    if not pages_root.exists():
        return []
    return sorted(
        path.relative_to(release_root).as_posix()
        for path in pages_root.rglob("*")
        if path.is_file() and not path.name.startswith(".")
    )


def _write_release_manifest(release_root: Path, release: str) -> None:
    release_root.mkdir(parents=True, exist_ok=True)
    pages_root = release_root / "pages"
    pages_root.mkdir(parents=True, exist_ok=True)
    keep_path = pages_root / ".gitkeep"
    if not keep_path.exists():
        keep_path.write_text("", encoding="utf-8")
    manifest = {
        "release": release,
        "motive": RELEASE_MOTIVES[release],
        "skills": _release_skill_names(release_root),
        "pages": _release_page_paths(release_root),
        "prerequisites": [],
    }
    write_frontmatter(
        release_root / "manifest.md",
        manifest,
        f"Generated staged release manifest for {release}.",
    )


def _prune_residual_skill_dirs(project_root: Path) -> list[str]:
    skills_root = get_project_brain_skills_dir(project_root)
    if not skills_root.exists():
        return []

    removed: list[str] = []
    for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        if (skill_dir / "SKILL.md").exists():
            continue
        shutil.rmtree(skill_dir)
        removed.append(skill_dir.name)
    return removed


def migrate_non_mvp_skills(project_root: Path) -> dict[str, Any]:
    """Move all non-MVP live skills into the matching drafts/staging release tree."""

    project_root = Path(project_root)
    kept: list[str] = []
    moved: list[str] = []

    for skill_dir in iter_live_skill_dirs(project_root):
        release = _skill_release(skill_dir)
        if release == MVP_RELEASE:
            kept.append(skill_dir.name)
            continue

        ensure_valid_staged_release(release)
        target_dir = _release_root(project_root, release) / "skills" / skill_dir.name
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.move(str(skill_dir), str(target_dir))
        moved.append(skill_dir.name)

    staged_releases: list[str] = []
    for release in STAGED_RELEASES:
        release_root = _release_root(project_root, release)
        if not (release_root / "skills").exists():
            continue
        _write_release_manifest(release_root, release)
        staged_releases.append(release)

    removed_residual_dirs = _prune_residual_skill_dirs(project_root)

    return {
        "kept": sorted(kept),
        "moved": sorted(moved),
        "removed_residual_dirs": removed_residual_dirs,
        "staged_releases": staged_releases,
    }

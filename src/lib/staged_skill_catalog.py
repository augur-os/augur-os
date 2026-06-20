from __future__ import annotations

from pathlib import Path

from src.config.paths import (
    get_project_brain_skills_dir,
    get_vault_skills_dir,
    get_vault_staging_dir,
)
from src.lib.porting_payload import STAGED_RELEASES


def is_staging_payload_path(path: Path) -> bool:
    rel = path.as_posix().strip("/")
    return rel == "staging" or rel.startswith("staging/")


def _skill_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir() and (path / "SKILL.md").exists())


def _repo_live_skill_roots(project_root: Path) -> list[Path]:
    """Return repo-owned live skill roots in current authority order."""
    project_root_skills = get_project_brain_skills_dir(project_root)
    return _dedupe_roots([project_root_skills])


def _lookup_skill_roots(project_root: Path) -> list[Path]:
    """Return roots for direct skill lookup, including private-vault fallback."""
    return _dedupe_roots([*_repo_live_skill_roots(project_root), get_vault_skills_dir()])


def _dedupe_roots(roots: list[Path]) -> list[Path]:
    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(root)
    return deduped


def iter_live_skill_dirs(project_root: Path) -> list[Path]:
    dirs: list[Path] = []
    seen_names: set[str] = set()
    for root in _repo_live_skill_roots(project_root):
        for skill_dir in _skill_dirs(root):
            if skill_dir.name in seen_names:
                continue
            seen_names.add(skill_dir.name)
            dirs.append(skill_dir)
    return dirs


def iter_staged_skill_dirs(project_root: Path, release: str | None = None) -> list[Path]:
    """Return skill directories from the vault drafts/staging release payloads."""

    drafts_root = get_vault_staging_dir()
    releases = (release,) if release is not None else STAGED_RELEASES
    dirs: list[Path] = []
    for release_tag in releases:
        dirs.extend(_skill_dirs(drafts_root / release_tag / "skills"))
    return sorted(dirs)


def iter_all_release_skill_dirs(project_root: Path) -> list[Path]:
    return sorted(iter_live_skill_dirs(project_root) + iter_staged_skill_dirs(project_root))


def find_skill_dir(project_root: Path, skill_name: str) -> Path | None:
    # 1. Live skills (project-brain + private vault).
    for root in _lookup_skill_roots(project_root):
        live_dir = root / skill_name
        if (live_dir / "SKILL.md").exists():
            return live_dir

    # 2. Staged skills (drafts/staging/<release>/skills/) — restored after the
    # live-skill refactor regression. Mirrors iter_staged_skill_dirs so a
    # caller looking up a staged-only skill by name (e.g. _resolve_notes_lib_path
    # → apple, file-manager, books) gets a hit instead of None.
    #
    # Lazy import so tests can monkeypatch paths.get_vault_staging_dir to
    # redirect at a tmp staging tree without import-time binding interfering.
    from src.config import paths as _paths

    drafts_root = _paths.get_vault_staging_dir()
    for release_tag in STAGED_RELEASES:
        staged_dir = drafts_root / release_tag / "skills" / skill_name
        if (staged_dir / "SKILL.md").exists():
            return staged_dir

    return None


def find_skill_file(project_root: Path, skill_name: str, *parts: str) -> Path | None:
    skill_dir = find_skill_dir(project_root, skill_name)
    if skill_dir is None:
        return None

    target = skill_dir.joinpath(*parts)
    if target.exists():
        return target
    return None

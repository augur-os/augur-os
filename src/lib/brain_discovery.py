"""Assemble the brain discovery snapshot for the dashboard (ADR-772).

This is the data engine behind the ``brain-discovery`` MCP tool and the
``/brain/settings`` dashboard surface. It answers, against the real registry and
filesystem:

- Which brains are registered (type, root, git arrangement, sync state)?
- What does each brain actually contain (memory entries, notes, sources, wiki)?
- Is the current project a registered brain, an unregistered project brain found
  in a cloned repo, or an uninitialized project that ``augur init`` can adopt?

The engine stays in core ``src/lib`` and is pure with respect to AI clients: the
per-client *projection* status is computed by the existing sync-status surface
and injected by the MCP layer, so this module never imports skill-owned
projection code. Git status is best-effort and can be disabled for deterministic
tests.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.lib.brain_manifest import (
    BRAIN_MANIFEST_NAME,
    find_project_brain_root,
    project_brain_root_for,
    read_brain_manifest,
)
from src.lib.brain_registry import get_registry
from src.lib.brain_registry_models import Brain, BrainRegistry, GitArrangement

_GIT_TIMEOUT_SECONDS = 5


def build_discovery_snapshot(
    *,
    cwd: Path,
    registry_path: Optional[Path] = None,
    project_root: Optional[Path] = None,
    projections: Optional[dict[str, Any]] = None,
    include_git_status: bool = True,
) -> dict[str, Any]:
    """Build the full brain discovery snapshot.

    Args:
        cwd: Working directory used to resolve the active brain and detect a
            nearby project brain.
        registry_path: Optional explicit registry path (tests). None uses the
            real registry.
        project_root: The repository root treated as "the current project".
            None falls back to the configured project root.
        projections: Pre-computed per-client projection status (from the
            sync-status surface). Embedded as-is; None yields an empty map.
        include_git_status: When False, skip the per-brain git subprocess calls
            (deterministic tests). Defaults to True for real dashboard use.
    """
    registry = get_registry(registry_path=registry_path, project_root=project_root)
    resolved_project_root = _resolve_project_root(project_root)
    active = _resolve_active(cwd=cwd, registry_path=registry_path)
    active_brain_id = active["brain_id"] if active else None

    brains = [
        _brain_entry(
            brain,
            is_active=brain.id == active_brain_id,
            include_git_status=include_git_status,
        )
        for brain in _sorted_brains(registry)
    ]

    return {
        "success": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active": active,
        "current_project": _current_project_status(resolved_project_root, registry),
        "brains": brains,
        "detected_project_brains": _detected_project_brains(cwd, registry),
        "projections": projections or {},
    }


def _sorted_brains(registry: BrainRegistry) -> list[Brain]:
    # Stable, human-meaningful order: personal first, then team, then project,
    # alphabetical within a type.
    type_rank = {"personal": 0, "team": 1, "project": 2}
    return sorted(
        registry.brains.values(),
        key=lambda b: (type_rank.get(b.type.value, 9), b.id),
    )


def _brain_entry(
    brain: Brain,
    *,
    is_active: bool,
    include_git_status: bool,
) -> dict[str, Any]:
    root = Path(str(brain.data_root)).expanduser()
    exists = root.is_dir()
    return {
        "id": brain.id,
        "type": brain.type.value,
        "root": str(brain.data_root),
        "description": brain.description,
        "is_active": is_active,
        "exists": exists,
        "write_policy": brain.write_policy,
        "git": _git_info(brain, include_git_status=include_git_status),
        "index": _index_info(root) if exists else _empty_index(),
    }


def _git_info(brain: Brain, *, include_git_status: bool) -> dict[str, Any]:
    git = brain.git
    info: dict[str, Any] = {
        "arrangement": git.arrangement.value,
        "branch": git.branch,
        "remote": git.remote,
        "host_repo": str(git.host_repo) if git.host_repo is not None else None,
        "auto_commit": git.auto_commit,
        "auto_push": git.auto_push,
        "tracked": git.arrangement is not GitArrangement.UNTRACKED,
        "dirty": None,
        "uncommitted": None,
    }
    if not include_git_status:
        return info

    repo_dir = _git_repo_dir(brain)
    if repo_dir is None or not repo_dir.is_dir():
        return info

    porcelain = _git_porcelain(repo_dir)
    if porcelain is None:
        return info
    changed = [line for line in porcelain.splitlines() if line.strip()]
    info["uncommitted"] = len(changed)
    info["dirty"] = len(changed) > 0
    return info


def _git_repo_dir(brain: Brain) -> Optional[Path]:
    git = brain.git
    if git.arrangement is GitArrangement.BUNDLED and git.host_repo is not None:
        return Path(str(git.host_repo)).expanduser()
    if git.arrangement is GitArrangement.STANDALONE:
        return Path(str(brain.data_root)).expanduser()
    return None


def _git_porcelain(repo_dir: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _index_info(root: Path) -> dict[str, Any]:
    from src.lib.brain_layout import (
        MACHINE_DIR,
        brain_layout,
        brain_sources_dir,
        brain_wiki_dir,
        vault_machine_dir,
    )

    if brain_layout(root) == "domains":
        # Domains layout: notes are the per-domain markdown files at the vault
        # root. Count per top-level dir, excluding the machine subtree and the
        # dedicated wiki/sources dirs (inbox/ counts as notes). Root-level
        # brain-contract files (MEMORY.md, ...) are not notes and fall out
        # naturally because only directories are counted.
        excluded = {MACHINE_DIR, "wiki", "sources"}
        notes = 0
        for child in sorted(root.iterdir()):
            if child.is_symlink() or not child.is_dir():
                continue
            if child.name in excluded:
                continue
            notes += _count_markdown(child)
        # Live memory moves to _augur/memory in the migration; count the
        # machine knowledge location too (distinct dirs — no double count).
        memory_entries = _count_markdown_any(
            vault_machine_dir(root, "memory") / "entries",
            vault_machine_dir(root, "knowledge") / "memory" / "entries",
        )
        sources = _count_markdown(brain_sources_dir(root))
        wiki_pages = _count_markdown(brain_wiki_dir(root))
    else:
        # Legacy: ADR-770 moves brain content under ``knowledge/`` but that
        # migration has not landed yet, so the live personal brain still stores
        # content at the legacy top-level dirs. Count both layouts so stats are
        # honest today and remain correct once content physically migrates.
        memory_entries = _count_markdown_any(
            root / "knowledge" / "memory" / "entries",
            root / "memory" / "entries",
        )
        notes = _count_markdown_any(root / "knowledge" / "notes", root / "notes")
        sources = _count_markdown_any(root / "knowledge" / "sources", root / "sources")
        wiki_pages = _count_markdown_any(root / "knowledge" / "wiki", root / "wiki")
    total = memory_entries + notes + sources + wiki_pages
    return {
        "exists": True,
        "memory_entries": memory_entries,
        "notes": notes,
        "sources": sources,
        "wiki_pages": wiki_pages,
        "total_records": total,
        "populated": total > 0,
    }


def _empty_index() -> dict[str, Any]:
    return {
        "exists": False,
        "memory_entries": 0,
        "notes": 0,
        "sources": 0,
        "wiki_pages": 0,
        "total_records": 0,
        "populated": False,
    }


def _count_markdown_any(*directories: Path) -> int:
    """Total markdown files across the given directories (canonical + legacy)."""
    return sum(_count_markdown(directory) for directory in directories)


def _count_markdown(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    try:
        return sum(1 for path in directory.rglob("*.md") if path.is_file())
    except OSError:
        return 0


def _current_project_status(project_root: Path, registry: BrainRegistry) -> dict[str, Any]:
    brain_root = project_brain_root_for(project_root)
    manifest_path = brain_root / BRAIN_MANIFEST_NAME
    has_project_brain = manifest_path.is_file()

    registered_brain_id: Optional[str] = None
    if has_project_brain:
        try:
            manifest = read_brain_manifest(manifest_path)
        except (OSError, ValueError):
            manifest = None
        if manifest is not None:
            registered = registry.get(manifest.id)
            if registered is not None and _same_path(registered.data_root, brain_root):
                registered_brain_id = manifest.id

    return {
        "root": str(project_root),
        "name": project_root.name,
        "project_brain_root": str(brain_root),
        "has_project_brain": has_project_brain,
        "registered_brain_id": registered_brain_id,
        "registered": registered_brain_id is not None,
        "can_init": not has_project_brain or registered_brain_id is None,
    }


def _detected_project_brains(cwd: Path, registry: BrainRegistry) -> list[dict[str, Any]]:
    """Project brains discovered by walking up from ``cwd`` (cloned-repo case)."""
    brain_root = find_project_brain_root(cwd)
    if brain_root is None:
        return []
    try:
        manifest = read_brain_manifest(brain_root / BRAIN_MANIFEST_NAME)
    except (OSError, ValueError):
        return []

    registered = registry.get(manifest.id)
    is_registered = registered is not None and _same_path(registered.data_root, brain_root)
    return [
        {
            "id": manifest.id,
            "type": manifest.type.value,
            "root": str(brain_root),
            "attached_project": manifest.attached_project,
            "description": manifest.description,
            "registered": is_registered,
        }
    ]


def _resolve_active(
    *,
    cwd: Path,
    registry_path: Optional[Path],
) -> Optional[dict[str, Any]]:
    try:
        from src.lib.brain_context import resolve_active_context

        ctx = resolve_active_context(
            cwd=cwd,
            registry_path=registry_path or _real_registry_path(),
        )
    except Exception:
        return None
    return {
        "brain_id": ctx.active_brain.id,
        "type": ctx.active_brain.type.value,
        "root": str(ctx.active_brain.data_root),
        "source": ctx.source,
        "attached_project": str(ctx.attached_project) if ctx.attached_project else None,
    }


def _resolve_project_root(project_root: Optional[Path]) -> Path:
    if project_root is not None:
        return project_root.resolve()
    from src.config.paths import get_project_root

    return get_project_root().resolve()


def _real_registry_path() -> Path:
    from src.config.paths import get_brain_registry_path

    return get_brain_registry_path()


def _same_path(left: object, right: Path) -> bool:
    try:
        return Path(str(left)).expanduser().resolve(strict=False) == right.resolve(strict=False)
    except OSError:
        return Path(str(left)).expanduser() == right

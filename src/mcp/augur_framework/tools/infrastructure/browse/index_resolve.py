"""Source-path / brain-id resolution helpers for Browse entries."""

from pathlib import Path

from src.config.paths import get_project_root

from .index_common import _FILESYSTEM_BACKED_CATEGORIES


def _resolve_entry_brain_id(entry: dict) -> str | None:
    """Owning brain for a browse entry's source file (ADR-772), best-effort.

    Resolves the entry's ``source_path`` to an absolute path and maps it to the
    project brain manifest or registered brain that contains it. Repo artifacts
    outside a brain resolve to no brain and stay unbadged, which is correct —
    they belong to the codebase, not a brain.
    """
    resolved = _resolve_local_source_path(entry.get("source_path"))
    if resolved is None:
        return None
    project_brain_id = _resolve_project_brain_id_for_path(resolved)
    if project_brain_id:
        return project_brain_id
    try:
        from src.lib.brain_path import resolve_brain_id_for_path

        return resolve_brain_id_for_path(resolved)
    except Exception:
        return None


def _resolve_project_brain_id_for_path(path: Path) -> str | None:
    try:
        from src.lib.brain_manifest import (
            BRAIN_MANIFEST_NAME,
            find_project_brain_root,
            read_brain_manifest,
        )
        from src.lib.brain_registry_models import BrainType

        brain_root = find_project_brain_root(path)
        if brain_root is None:
            return None
        try:
            path.resolve(strict=False).relative_to(brain_root.resolve(strict=False))
        except ValueError:
            return None
        manifest = read_brain_manifest(brain_root / BRAIN_MANIFEST_NAME)
        if manifest.type is BrainType.PROJECT:
            return manifest.id
    except Exception:
        return None
    return None


def _resolve_local_source_path(source_path: object) -> Path | None:
    raw = str(source_path or "").strip()
    if not raw:
        return None
    lowered = raw.lower()
    if "://" in lowered or lowered.startswith(("urn:", "mailto:")):
        return None
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return get_project_root() / path


def _resolve_safe_project_relative_source_path(source_path: object) -> Path | None:
    raw = str(source_path or "").strip()
    if not raw:
        return None
    lowered = raw.lower()
    if "://" in lowered or lowered.startswith(("urn:", "mailto:")):
        return None
    path = Path(raw).expanduser()
    if path.is_absolute() or raw.startswith("~") or any(part == ".." for part in path.parts):
        return None

    project_root = get_project_root().resolve()
    resolved = (project_root / path).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError:
        return None
    if not resolved.exists():
        return None
    return resolved


def _source_path_for_output(category: str, entry: dict) -> object:
    """Resolve a project-relative ``source_path`` to an absolute path under the
    ACTIVE project root, for any filesystem-backed category.

    The RAG index is machine-shared across checkouts/worktrees (ADR-270/759), so
    in-repo entries are stored project-root-relative (POSIX). Resolving here — the
    single point where an index entry becomes the dashboard's path / action target
    — repairs Open File, Reveal, Copy Path, content read, and brain-id resolution
    on every checkout at once. Absolute/external paths (private vault, logs) and
    non-file values (route hrefs, URLs) pass through unchanged because
    ``_resolve_safe_project_relative_source_path`` returns None for them.
    """
    source_path = entry.get("source_path", "")
    resolved = _resolve_safe_project_relative_source_path(source_path)
    if resolved is None:
        return source_path
    return str(resolved)


def _entry_has_existing_source_path(entry: dict) -> bool:
    source_path = _resolve_local_source_path(entry.get("source_path"))
    if source_path is None:
        return True
    return source_path.exists()


def _filter_missing_source_path_entries(category: str, entries: list[dict]) -> list[dict]:
    if category not in _FILESYSTEM_BACKED_CATEGORIES:
        return entries
    return [entry for entry in entries if _entry_has_existing_source_path(entry)]

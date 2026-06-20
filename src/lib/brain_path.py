"""Map filesystem paths to their owning brain (ADR-772).

Federated read surfaces (search, Browse, wiki, vault-note lists) attribute every
record to a brain so the dashboard can render a brain badge and offer brain
filters. The single source of truth for "which brain owns this path" is the
registered brain whose ``data_root`` contains the path. Longest match wins so a
project brain nested under a personal brain root still resolves to the project.

This module is intentionally dependency-light and pure: it never writes, and it
degrades to ``None`` for paths outside every registered brain (repo artifacts,
caches, runtime state) rather than guessing. Callers attach ``brain_id`` only
when this returns a value, so non-brain records stay honestly unbadged.
"""

from __future__ import annotations

from pathlib import Path, PurePath
from typing import Optional

from src.lib.brain_registry_models import BrainRegistry


def _normalize(path: PurePath | str) -> Optional[Path]:
    """Return an absolute, symlink-resolved Path, or None if unusable."""
    try:
        candidate = Path(str(path)).expanduser()
    except (TypeError, ValueError):
        return None
    try:
        return candidate.resolve(strict=False)
    except (OSError, RuntimeError):
        return candidate


def _contains(root: Path, target: Path) -> bool:
    """True when ``target`` is ``root`` or lives beneath it."""
    if target == root:
        return True
    try:
        target.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_brain_id_for_path(
    path: PurePath | str,
    *,
    registry: Optional[BrainRegistry] = None,
) -> Optional[str]:
    """Return the id of the registered brain that owns ``path``.

    The owning brain is the one whose ``data_root`` contains ``path``. When
    multiple brains' roots contain the path (e.g. a project brain nested under a
    personal root), the deepest root wins. Returns ``None`` when no registered
    brain owns the path, so callers can omit ``brain_id`` for non-brain records.

    Args:
        path: An absolute or user-relative filesystem path. Relative paths are
            expanded but not resolved against any project root — callers that
            hold relative paths should resolve them to absolute first.
        registry: Optional pre-loaded registry. When omitted, the active
            registry is loaded (and bootstrapped on first read) lazily.
    """
    target = _normalize(path)
    if target is None:
        return None

    resolved_registry = registry if registry is not None else _load_registry()
    if resolved_registry is None:
        return None

    best_id: Optional[str] = None
    best_depth = -1
    for brain_id, brain in resolved_registry.brains.items():
        root = _normalize(brain.data_root)
        if root is None:
            continue
        if not _contains(root, target):
            continue
        depth = len(root.parts)
        if depth > best_depth:
            best_depth = depth
            best_id = brain_id
    return best_id


def annotate_brain_id(
    record: dict,
    *path_keys: str,
    registry: Optional[BrainRegistry] = None,
) -> dict:
    """Attach ``record['brain_id']`` from the first present path-bearing key.

    Federated read surfaces call this on each record they emit. The first key in
    ``path_keys`` that holds a value is treated as the record's filesystem
    location; ``brain_id`` is set only when that path resolves to a registered
    brain (so records outside every brain stay unbadged). Mutates and returns
    ``record`` for call-site convenience. Defaults to the common path keys when
    none are supplied.
    """
    for key in path_keys or ("file", "source_path", "path"):
        value = record.get(key)
        if not value:
            continue
        brain_id = resolve_brain_id_for_path(value, registry=registry)
        if brain_id:
            record["brain_id"] = brain_id
        return record
    return record


def _load_registry() -> Optional[BrainRegistry]:
    # Late import keeps this module importable in contexts where the registry
    # stack (and its path-helper dependencies) is not wired up.
    try:
        from src.lib.brain_registry import get_registry

        return get_registry()
    except Exception:
        return None

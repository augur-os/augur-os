from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.lib.brain_registry_bootstrap import build_default_registry, migrate_loaded_registry
from src.lib.brain_registry_io import load_registry, save_registry
from src.lib.brain_registry_models import BrainRegistry


@dataclass(frozen=True)
class _CacheEntry:
    registry: BrainRegistry
    signature: tuple[int, int] | None


_cache: dict[Path, _CacheEntry] = {}


def get_registry(
    *,
    registry_path: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> BrainRegistry:
    """Return the active brain registry, bootstrapping it on first read."""
    resolved_path = _resolve_registry_path(registry_path)
    signature = _registry_signature(resolved_path)
    cached = _cache.get(resolved_path)
    if cached is not None and cached.signature == signature:
        return cached.registry
    resolved_project_root = _resolve_project_root(project_root)
    if resolved_path.is_file():
        registry = load_registry(resolved_path)
        registry, changed = migrate_loaded_registry(
            registry,
            project_root=resolved_project_root,
        )
        if changed:
            save_registry(registry, resolved_path)
    else:
        registry = build_default_registry(project_root=resolved_project_root)
        save_registry(registry, resolved_path)
    _cache[resolved_path] = _CacheEntry(
        registry=registry,
        signature=_registry_signature(resolved_path),
    )
    return registry


def clear_cache() -> None:
    """Reset the per-process cache. Test-only; do not use in production code."""
    _cache.clear()


def _resolve_registry_path(explicit: Optional[Path]) -> Path:
    if explicit is not None:
        return explicit
    # Late import to avoid a cycle with src.config.paths during paths' own initialization.
    from src.config.paths import get_brain_registry_path

    return get_brain_registry_path()


def _resolve_project_root(explicit: Optional[Path]) -> Path:
    if explicit is not None:
        return explicit
    from src.config.paths import get_project_root

    return get_project_root()


def _registry_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return (stat.st_mtime_ns, stat.st_size)

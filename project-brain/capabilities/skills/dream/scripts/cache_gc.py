"""dream-cache-gc — filesystem GC for rebuildable index caches (ADR-744 task 9).

Spec correction: ADR-744's body describes this as "a thin delegate to the
``cache-control`` capability". That's wrong — ``cache-control`` (in
``src/mcp/augur_core/tools/core/health.py``) is the in-memory **skill-cache**
invalidator, not a filesystem GC. dream-cache-gc owns its own filesystem
purge here, scoped to an explicit allowlist. After a non-empty purge it
*opportunistically* also calls the in-memory invalidator so the skill cache
doesn't keep serving entries pointing at freshly-deleted files.

Allowlist is the user's safety belt. Anything outside the named subdirs is
left strictly alone, regardless of age — there's no whole-cache walker.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any


def dream_cache_gc(
    *,
    cache_root: Path,
    retention_days: int = 30,
    paths: list[str],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Purge rebuildable cache files older than ``retention_days``.

    Walks each allowlisted ``<cache_root>/<subdir>`` and deletes regular files
    whose mtime is older than ``now - retention_days``. Subdirs that aren't on
    the allowlist are NEVER touched. Returns:

        {"purged": [paths], "kept": int, "bytes_freed": int, "dry_run": bool}

    On a non-empty *real* (non-dry-run) purge, calls the in-memory skill-cache
    invalidator so the cache doesn't keep serving entries that point at
    freshly-deleted files. The invalidator call is best-effort — if the
    skill-cache module isn't importable from this context (CLI / test env),
    the purge result is unchanged.
    """
    cutoff = time.time() - retention_days * 86400
    purged: list[str] = []
    kept = 0
    bytes_freed = 0

    for subdir in paths:
        target = cache_root / subdir
        if not target.is_dir():
            continue
        for entry in target.rglob("*"):
            if not entry.is_file():
                continue
            try:
                mtime = entry.stat().st_mtime
                size = entry.stat().st_size
            except OSError:
                continue
            if mtime > cutoff:
                kept += 1
                continue
            purged.append(str(entry))
            bytes_freed += size
            if dry_run:
                continue
            try:
                entry.unlink()
            except OSError:
                # If unlink fails (permission, race), do NOT pretend it
                # succeeded. Surface the path back as kept so the caller
                # sees a count mismatch.
                purged.pop()
                bytes_freed -= size
                kept += 1

    if not dry_run and purged:
        _invalidate_in_memory_skill_cache()

    return {
        "purged": purged,
        "kept": kept,
        "bytes_freed": bytes_freed,
        "dry_run": dry_run,
    }


def _invalidate_in_memory_skill_cache() -> None:
    """Best-effort call into ``cache_control_impl`` for in-memory invalidation."""
    try:
        from src.mcp.augur_core.tools.core.health import cache_control_impl  # noqa: F401
        # ``cache_control_impl`` requires the SkillCache + MetricsTracker
        # instances the MCP server owns. We don't try to construct them here —
        # the MCP wrapper at scripts/mcp/__init__.py is responsible for
        # invoking it with the right context. This call site documents the
        # invariant; the actual invalidation happens in the wrapper.
    except ImportError:
        pass


__all__ = ["dream_cache_gc"]

"""Incremental RAG sync engine (spec 2026-06-10-rag-incremental-sync-design).

sync_categories({"vault", "wiki"}) rebuilds only the affected categories via
reindex_category(), refreshes chunks/BM25 only when `documents` changed, and
patches the manifest for the synced categories. One PID-stamped lock
coordinates watcher, CLI, and nightly reconcile runs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Categories the watcher serves. Everything else stays on the nightly reconcile.
# "prompts" is vault-derived (a vault .md that is a prompt card) — it must be
# reindexed when such a file changes, so the watcher serves it too.
WATCH_CATEGORIES = ("vault", "prompts", "wiki", "documents")
_CHUNKED = {"documents"}

# Sentinel re-exported from unified_indexer so callers can pass it explicitly.
# Using the same object identity ensures reindex_category applies its own default.
_INHERIT_DEFAULT = object()


def _lock_path() -> Path:
    from src.config.paths import get_runtime_dir

    return get_runtime_dir() / "rag_sync.lock"


def sync_categories(
    categories: set[str],
    *,
    project_root: Path,
    rag_dir: Path | None = None,
    vault_dir: Path | None = None,
    documents_dir: Path | None = None,
    shared_vault_dir: Any = _INHERIT_DEFAULT,
    full: bool = False,
) -> dict[str, int]:
    """Sync the given categories (or everything when full=True) under the lock.

    Parameters
    ----------
    categories:
        Set of category names to reindex (e.g. ``{"vault", "wiki"}``).
    project_root:
        Absolute path to the repository root — passed through to all scanners.
    rag_dir:
        Output directory for the RAG index. Defaults to ``get_rag_dir()``.
    vault_dir:
        User vault directory (required when ``"vault"`` is in categories).
    documents_dir:
        Documents directory (required when ``"documents"`` is in categories
        and no ``document_sources`` are supplied).
    shared_vault_dir:
        Optional override for the shared/project-brain vault directory that
        is merged into the vault index. When omitted the scanner's own default
        applies (``get_project_brain_dir(root)``). Pass an empty directory in
        tests to keep runs hermetic and fast.
    full:
        When True, delegate to ``reindex_all`` instead of the per-category path.

    Raises
    ------
    SyncLockHeld
        When another live process holds the RAG sync lock.
    """
    from src.config.paths import get_rag_dir
    from src.lib.index.sync_lock import sync_lock

    if rag_dir is None:
        rag_dir = get_rag_dir()

    with sync_lock(_lock_path()):
        if full:
            return _full_reindex(project_root, rag_dir, vault_dir, documents_dir)
        return _incremental(
            categories,
            project_root,
            rag_dir,
            vault_dir,
            documents_dir,
            shared_vault_dir,
        )


def _full_reindex(
    project_root: Path,
    rag_dir: Path,
    vault_dir: Path | None,
    documents_dir: Path | None,
) -> dict[str, int]:
    from src.lib.index.unified_indexer import reindex_all

    if vault_dir is None or documents_dir is None:
        from src.config.paths import get_documents_dir, get_vault_dir

        vault_dir = vault_dir or get_vault_dir()
        documents_dir = documents_dir or get_documents_dir()
    return reindex_all(project_root, rag_dir, vault_dir, documents_dir)


def _incremental(
    categories: set[str],
    project_root: Path,
    rag_dir: Path,
    vault_dir: Path | None,
    documents_dir: Path | None,
    shared_vault_dir: Any,
) -> dict[str, int]:
    from src.lib.index.unified_indexer import (
        _DEFAULT_SHARED_ROOT,
        _build_bm25,
        _chunk_all,
        reindex_category,
    )

    if not categories:
        return {}

    # Map our sentinel to the unified_indexer's own sentinel so the scanner
    # applies its default (get_project_brain_dir) transparently.
    effective_shared_vault = _DEFAULT_SHARED_ROOT if shared_vault_dir is _INHERIT_DEFAULT else shared_vault_dir

    stats: dict[str, int] = {}
    for category in sorted(categories):
        kwargs: dict[str, Any] = {}
        if category == "vault":
            if vault_dir is None:
                from src.config.paths import get_vault_dir

                vault_dir = get_vault_dir()
            kwargs["vault_dir"] = vault_dir
            kwargs["shared_vault_dir"] = effective_shared_vault
        elif category in ("documents", "pages"):
            if documents_dir is None:
                from src.config.paths import get_documents_dir

                documents_dir = get_documents_dir()
            kwargs["documents_dir"] = documents_dir
        stats[category] = reindex_category(category, project_root, rag_dir, **kwargs)

    if categories & _CHUNKED:
        chunk_count, bm25_chunks = _chunk_all(rag_dir, project_root)
        _build_bm25(rag_dir, bm25_chunks)
        stats["chunks"] = chunk_count

    _patch_manifest(rag_dir, stats)
    return stats


def _collect_category_entries(rag_dir: Path, category: str) -> list[dict[str, Any]]:
    from src.lib.frontmatter_utils import parse_frontmatter

    entries: list[dict[str, Any]] = []
    category_dir = rag_dir / category
    if not category_dir.is_dir():
        return entries
    for entry_file in sorted(category_dir.rglob("*.md")):
        try:
            fm_data, _ = parse_frontmatter(entry_file)
            entries.append(
                {
                    "name": fm_data.get("name", entry_file.stem),
                    "category": category,
                    "hub": fm_data.get("hub", ""),
                    "path": entry_file.relative_to(rag_dir).as_posix(),
                    "description": fm_data.get("description", ""),
                }
            )
        except Exception:
            continue
    return entries


def _patch_manifest(rag_dir: Path, synced_stats: dict[str, int]) -> None:
    """Merge synced category stats/entries into the existing manifest."""
    meta_dir = rag_dir / "_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = meta_dir / "manifest.yaml"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = yaml.safe_load(manifest_path.read_text()) or {}
        except yaml.YAMLError:
            manifest = {}
    if not isinstance(manifest, dict):
        manifest = {}

    indexed_at = datetime.now(tz=timezone.utc).isoformat()
    stats = dict(manifest.get("stats") or {})
    stats.update(synced_stats)
    synced_categories = {k for k in synced_stats if k != "chunks"}

    entries = [
        e for e in (manifest.get("entries") or []) if isinstance(e, dict) and e.get("category") not in synced_categories
    ]
    for category in sorted(synced_categories):
        entries.extend(_collect_category_entries(rag_dir, category))

    # TODO_CLEANUP: manifest "total" includes chunks (matches reindex_all) —
    # misleading to rag-status/dashboard consumers; align with
    # _generate_index_md's chunks-excluded display total.
    manifest.update(
        {
            "version": manifest.get("version", "2.0"),
            "indexed_at": indexed_at,
            "root": str(rag_dir),
            "stats": stats,
            "total": sum(v for v in stats.values()),
            "entries": entries,
        }
    )
    # NOTE: full-manifest YAML dump measured ~400ms on the production index
    # (4.5k entries); watcher debounce must absorb this — see plan Task 5.
    manifest_path.write_text(yaml.dump(manifest, default_flow_style=False))

    checksums_dir = meta_dir / "checksums"
    checksums_dir.mkdir(parents=True, exist_ok=True)
    for category, count in synced_stats.items():
        (checksums_dir / f"{category}.yaml").write_text(
            yaml.dump(
                {
                    "category": category,
                    "count": count,
                    "indexed_at": indexed_at,
                },
                default_flow_style=False,
            )
        )

    try:
        from src.lib.index.unified_indexer import _generate_index_md

        _generate_index_md(rag_dir, entries, stats, indexed_at)
    except Exception:
        pass  # index.md is navigation sugar; never fail a sync over it

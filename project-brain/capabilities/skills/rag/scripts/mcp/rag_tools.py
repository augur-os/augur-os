from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
import shutil

import yaml

from src.config.paths import (
    get_compiled_wiki_dir,
    get_documents_dir,
    get_project_root,
    get_rag_dir,
    get_vault_dir,
)
from src.lib.index.unified_search import (
    iterative_search,
    resolve_scope_paths,
    unified_rag_search,
)

__all__ = ["unified_rag_search", "register_tools"]


def _count_status(rag_dirs: list) -> dict:
    chunks = 0
    symbols = 0
    indices = 0
    bm25_size = 0
    existing_dirs: list[str] = []

    for rag_dir in rag_dirs:
        if not rag_dir.exists():
            continue
        existing_dirs.append(str(rag_dir))
        chunks_dir = rag_dir / "chunks"
        if chunks_dir.is_dir():
            chunks += sum(1 for _ in chunks_dir.rglob("*.md"))
        indices += sum(1 for _ in rag_dir.rglob("*_index.md"))
        if (rag_dir / "index.md").is_file():
            indices += 1
        symbols += sum(1 for _ in rag_dir.rglob("symbols.yaml"))
        bm25_path = rag_dir / "_meta" / "bm25_index.json"
        if bm25_path.exists():
            bm25_size = bm25_path.stat().st_size

    return {
        "chunks": chunks,
        "symbols": symbols,
        "indices": indices,
        "bm25_index_bytes": bm25_size,
        "rag_paths": existing_dirs,
    }


def _cleanup_rag_scope(skill: str) -> dict[str, str]:
    try:
        _, _, rag_dirs, label = resolve_scope_paths(skill)
    except ValueError as exc:
        return {"error": str(exc)}

    count = 0
    if skill == "all":
        rag_root = get_rag_dir()
        if rag_root.exists():
            for child in rag_root.iterdir():
                if child.name == "project-index.yaml":
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                    count += 1
                elif child.is_file():
                    child.unlink()
                    count += 1
            project_index = rag_root / "project-index.yaml"
            if project_index.exists():
                project_index.unlink()
                count += 1
    else:
        for rag_dir in rag_dirs:
            if rag_dir.exists():
                shutil.rmtree(rag_dir)
                count += 1

    return {"status": "success", "target": label, "message": f"Cleaned up {count} index locations"}


def register_tools(mcp, mcp_tool_interceptor, metrics):
    @mcp.tool(name="search-skill-knowledge")
    @mcp_tool_interceptor
    async def search_skill_knowledge(skill: str, query: str, budget: str | None = None) -> str:
        """Search a specific skill's centralized RAG knowledge base using iterative mode."""
        try:
            source_dirs, priority_dirs, rag_dirs, label = resolve_scope_paths(skill)
        except ValueError as exc:
            return json.dumps({"error": str(exc)})

        results = iterative_search(query, source_dirs, priority_dirs, rag_dirs, budget=budget)
        return json.dumps({"target": label, "results": results})

    @mcp.tool(name="rag-status")
    @mcp_tool_interceptor
    async def rag_status(skill: str = "all") -> str:
        """Get RAG indexing status for a specific skill or 'all' for global stats."""
        try:
            source_dirs, _, rag_dirs, label = resolve_scope_paths(skill)
        except ValueError as exc:
            return json.dumps({"error": str(exc)})

        status = _count_status(rag_dirs)
        status["target"] = label
        status["source_paths"] = [str(path) for path in source_dirs]

        from src.config.paths import get_runtime_dir

        watcher_state_file = get_runtime_dir() / "rag_watcher_state.json"
        watcher = None
        if watcher_state_file.exists():
            try:
                watcher = json.loads(watcher_state_file.read_text())
            except (OSError, json.JSONDecodeError):
                watcher = {"error": "unreadable state file"}
        status["watcher"] = watcher

        # StatData projection for the dashboard stat-card (spec 2026-06-10
        # success criterion 4: card shows true freshness): total indexed
        # entries as the value, watcher freshness age as the label.
        try:
            from datetime import datetime, timezone

            from src.config.paths import get_rag_dir

            manifest_path = get_rag_dir() / "_meta" / "manifest.yaml"
            manifest = yaml.safe_load(manifest_path.read_text()) or {}
            stats_map = manifest.get("stats") or {}
            if isinstance(stats_map, dict):
                status["value"] = sum(
                    v for k, v in stats_map.items()
                    if k != "chunks" and isinstance(v, int)
                )
            freshness = "watcher offline"
            heartbeat = (watcher or {}).get("heartbeat_at") if isinstance(watcher, dict) else None
            if heartbeat:
                age = (
                    datetime.now(tz=timezone.utc)
                    - datetime.fromisoformat(heartbeat)
                ).total_seconds()
                freshness = (
                    f"entries — watcher live, synced {int(age)}s ago"
                    if age < 120
                    else f"entries — watcher heartbeat {int(age // 60)}m ago"
                )
            status["label"] = freshness
        except Exception:  # noqa: BLE001 — summary is additive; never break status
            pass

        return json.dumps(status)

    @mcp.tool(name="rag-sync")
    @mcp_tool_interceptor
    async def rag_sync(full: bool = False, category: str = "") -> str:
        """Headlessly sync the RAG index. Incremental over watch categories by
        default; full=True runs a complete reindex_all rebuild. Returns stats."""
        import asyncio

        from src.lib.index.incremental import WATCH_CATEGORIES, sync_categories
        from src.lib.index.sync_lock import SyncLockHeld

        categories = {category} if category else set(WATCH_CATEGORIES)
        try:
            stats = await asyncio.to_thread(
                sync_categories, categories,
                project_root=get_project_root(), full=full,
            )
        except (SyncLockHeld, ValueError) as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        return json.dumps({"ok": True, "full": full, "stats": stats})

    @mcp.tool(name="rag-reindex")
    @mcp_tool_interceptor
    async def rag_reindex(skill: str | None = None, category: str | None = None) -> str:
        """Rebuild RAG index for a skill, category, or all."""
        from src.lib.index.unified_indexer import index_documents, reindex_all, reindex_category

        root = get_project_root()
        rag_dir = get_rag_dir()

        if category:
            if category == "documents":
                try:
                    documents_dir = get_documents_dir()
                except Exception:
                    return json.dumps({"error": "documents_dir not configured"})
                count = index_documents(documents_dir, rag_dir)
            elif category == "vault":
                try:
                    vault_dir = get_vault_dir()
                except Exception:
                    return json.dumps({"error": "vault_dir not configured"})
                count = reindex_category(category, root, rag_dir, vault_dir=vault_dir)
            elif category == "wiki":
                count = reindex_category(category, root, rag_dir, wiki_dir=get_compiled_wiki_dir())
                return json.dumps({"status": "ok", "category": category, "count": count, "mode": "index-only"})
            else:
                try:
                    count = reindex_category(category, root, rag_dir)
                except ValueError:
                    return json.dumps({"error": f"Unknown category: {category}"})
            return json.dumps({"status": "ok", "category": category, "count": count})

        vault_dir = None
        documents_dir = None
        try:
            vault_dir = get_vault_dir()
            documents_dir = get_documents_dir()
        except Exception:
            pass

        stats = reindex_all(root, rag_dir, vault_dir=vault_dir, documents_dir=documents_dir)
        return json.dumps({"status": "ok", "stats": stats, "total": sum(stats.values())})

    @mcp.tool(name="wiki-reindex")
    @mcp_tool_interceptor
    async def wiki_reindex() -> str:
        """Refresh the compiled wiki RAG browse index without rebuilding wiki content."""
        from src.lib.index.unified_indexer import reindex_category

        wiki_dir = get_compiled_wiki_dir()
        count = reindex_category("wiki", get_project_root(), get_rag_dir(), wiki_dir=wiki_dir)
        return json.dumps({"status": "ok", "indexed": count, "mode": "index-only", "wiki_dir": str(wiki_dir)})

    @mcp.tool(name="rag-cleanup")
    @mcp_tool_interceptor
    async def rag_cleanup(skill: str) -> str:
        """Cleanup centralized RAG indices and caches for a specific skill or for all skills."""
        metrics.track_tool("rag_cleanup", skill="rag")
        return json.dumps(_cleanup_rag_scope(skill))

    @mcp.tool(name="rag-purge")
    @mcp_tool_interceptor
    async def rag_purge(skill: str = "all") -> str:
        """Purge centralized RAG indices and caches for a specific skill or for all skills."""
        metrics.track_tool("rag_purge", skill="rag")
        return json.dumps(_cleanup_rag_scope(skill))

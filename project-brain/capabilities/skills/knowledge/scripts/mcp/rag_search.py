"""RAG search, stats, graph, documents, and OCR queue tools.

Handles unified search, project index search/stats, knowledge graph,
search status, document listing, and OCR queue.
"""

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
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import yaml

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.logging import get_entity_logger
    from src.mcp.augur_shared.annotations import tool_annotations
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        return logging.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

logger = get_entity_logger("mcp.knowledge.rag.search")


def _attach_brain_ids(records: list[dict]) -> None:
    """Annotate each search result with its owning brain (ADR-772).

    Best-effort and non-fatal: results whose path lies outside every registered
    brain (RAG cache chunks, repo files) are left unbadged.
    """
    if not records:
        return
    try:
        from src.lib.brain_path import annotate_brain_id
        from src.lib.brain_registry import get_registry

        registry = get_registry()
    except Exception:
        return
    for record in records:
        if not isinstance(record, dict):
            continue
        metadata = record.get("metadata")
        if isinstance(metadata, dict) and "attached_brain_ids" in metadata:
            continue
        if "attached_brain_ids" in record:
            continue
        annotate_brain_id(record, "file", "source_path", "path", registry=registry)


def _enrich_hit_display_fields(records: list[dict]) -> None:
    """Surface clean display fields on each hit for the dashboard card mapper.

    Raw search hits carry only file/content/score, so a Browse search-result card
    falls back to the filename slug for its title and the scope word ("knowledge")
    for hub/type. The indexed entry frontmatter already holds a real title, tags,
    note type, and journey category (see _scanners_structural.index_vault), so lift
    those onto the hit. Best-effort and non-fatal.
    """
    if not records:
        return
    try:
        from src.lib.knowledge.unified_search import _read_frontmatter
    except Exception:
        return
    for hit in records:
        if not isinstance(hit, dict):
            continue
        file_path = hit.get("file")
        if not file_path:
            continue
        fm = _read_frontmatter(file_path)
        if not fm:
            continue
        # Hits may point at the indexed entry (scanner-written `title`) or the
        # source vault note (which uses `label`/`document_title` instead).
        display_title = fm.get("title") or fm.get("label") or fm.get("document_title")
        if display_title and not hit.get("title"):
            hit["title"] = display_title
        if fm.get("name") and not hit.get("name"):
            hit["name"] = fm["name"]
        md = hit.setdefault("metadata", {})
        if not isinstance(md, dict):
            continue
        for key in ("x-augur-note-type", "document_title", "name"):
            if fm.get(key) is not None and key not in md:
                md[key] = fm[key]
        # Prefer the note's journey category as the hub chip over the scope word.
        if "hub" not in md and fm.get("journey_category"):
            md["hub"] = fm["journey_category"]
        if "tags" not in md and fm.get("tags"):
            md["tags"] = fm["tags"]

try:
    from src.config.paths import get_rag_dir
except ImportError:
    if sys.platform == "darwin":
        def get_rag_dir() -> Path:
            return Path.home() / "Library" / "Application Support" / "Augur" / "rag"
    else:
        def get_rag_dir() -> Path:
            return Path.home() / ".local" / "share" / "augur" / "rag"


def search_stats() -> dict[str, Any]:
    """Return BM25 index freshness and configured ADR-739 search budgets."""
    from src.lib.index.search_config import load_search_config
    from src.config.paths import get_config_dir

    cfg = load_search_config()
    cost_class = "remote"
    try:
        llm_cfg = yaml.safe_load((get_config_dir() / "system" / "llm.yaml").read_text(encoding="utf-8")) or {}
        active_profile = llm_cfg.get("active_profile")
        profile = (llm_cfg.get("profiles") or {}).get(active_profile, {})
        base_url = str(profile.get("base_url", ""))
        provider = str(profile.get("provider", ""))
        if base_url.startswith(("http://localhost", "http://127.0.0.1", "local://")) or provider == "command":
            cost_class = "local"
    except Exception:
        cost_class = "remote"

    budgets = {
        name: {
            **spec,
            "cost_label": f"~{int(spec.get('token_estimate', 0)) // 1000}K tokens - {cost_class}",
        }
        for name, spec in cfg["search_budgets"].items()
    }
    meta_dir = get_rag_dir() / "_meta"
    index_path = meta_dir / "bm25_index.json"
    chunk_map_path = meta_dir / "bm25_chunk_map.json"
    doc_count = 0
    if chunk_map_path.exists():
        try:
            data = json.loads(chunk_map_path.read_text(encoding="utf-8"))
            doc_count = len(data) if isinstance(data, list) else 0
        except Exception:
            doc_count = 0

    last_rebuild = None
    if index_path.exists():
        last_rebuild = datetime.fromtimestamp(
            index_path.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat()

    return {
        "bm25_index": {
            "path": str(index_path),
            "exists": index_path.exists(),
            "last_rebuild": last_rebuild,
            "doc_count": doc_count,
        },
        "rrf": cfg["rrf"],
        "budgets": budgets,
        "default_budget": cfg["default_budget"],
    }


def search_tune(query: str = "") -> dict[str, Any]:
    """Recommend a search budget without applying it automatically."""
    from src.lib.index.search_config import load_search_config

    cfg = load_search_config()
    tokens = [token for token in query.split() if token.strip()]
    lower = query.lower()
    if len(tokens) <= 2:
        budget = "conservative"
        reason = "short query"
    elif len(tokens) >= 8 or any(marker in lower for marker in (" and ", " or ", "multi-part", "?")):
        budget = "tokenmax"
        reason = "long or multi-part query"
    else:
        budget = "balanced"
        reason = "default depth for medium query"

    return {
        "recommended_budget": budget,
        "reason": reason,
        "applied": False,
        "token_estimate": cfg["search_budgets"][budget]["token_estimate"],
        "cost_label": search_stats()["budgets"][budget]["cost_label"],
    }


def knowledge_graph_deprecation_payload(stats: dict[str, Any]) -> dict[str, Any]:
    """Deprecation pointer for the legacy knowledge-graph tool (ADR-738).

    knowledge-graph is superseded by the graph skill's graph-stats tool. This
    one-release pointer still carries the legacy RAG-manifest counts so existing
    callers do not break before they migrate. Per Rule #14 it is a deprecation
    pointer, not a permanent alias.
    """
    return {
        "success": True,
        "deprecated": True,
        "superseded_by": "graph-stats",
        "message": (
            "knowledge-graph is superseded by the graph skill's graph-stats "
            "tool (ADR-738). Call graph-stats for typed edge/entity/tier "
            "statistics."
        ),
        "stats": stats,  # legacy RAG-manifest counts, kept for one release
    }


def _manifest_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def score_manifest_entry(entry: dict[str, Any], query: str) -> float:
    """Score a manifest row with word matching that treats hyphens as separators."""
    query_words = _manifest_tokens(query)
    if not query_words:
        return 0.0
    text = " ".join(
        str(entry.get(key, ""))
        for key in ("name", "description", "hub", "path", "category", "type")
    )
    entry_words = _manifest_tokens(text)
    overlap = query_words & entry_words
    return len(overlap) / len(query_words)


def register_rag_search_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register search, stats, graph, documents, and OCR tools."""
    from src.lib.knowledge import UnifiedSearcher

    # =========================================================================
    # Project Index Search
    # =========================================================================

    @mcp.tool(
        name="knowledge-project-index-search",
        annotations=tool_annotations(
            {
                "title": "Search Project Index",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_project_index_search_tool(
        query: str = "",
        q: str = "",
        type: str | None = None,
    ) -> str:
        """Search the RAG project index.

        Args:
            query: Search query (dashboard alias: q)
            q: Dashboard alias for query
            type: Optional filter by entry type/category (skill, page, action, etc.)

        Returns:
            str: JSON with search results
        """
        # Accept dashboard param name
        query = query or q
        metrics.track_tool("knowledge_project_index_search", skill="knowledge")

        def _search_index(q: str, entry_type: str | None) -> list[dict[str, Any]]:
            rag_dir = get_rag_dir()
            manifest_path = rag_dir / "_meta" / "manifest.yaml"
            if not manifest_path.exists():
                return []

            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            entries = manifest.get("entries", [])
            if not isinstance(entries, list):
                return []

            scored: list[tuple[float, dict[str, Any]]] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                # Filter by category (entries use "category", API param is "type")
                category = entry.get("category", entry.get("type", ""))
                if entry_type and category != entry_type:
                    continue
                score = score_manifest_entry(entry, q)
                if score > 0:
                    scored.append((score, {
                        "category": category or "unknown",
                        "name": entry.get("name", ""),
                        "description": entry.get("description", ""),
                        "hub": entry.get("hub", ""),
                        "path": entry.get("path", ""),
                        "score": round(score, 3),
                    }))
            # Sort by score descending, return top 50
            scored.sort(key=lambda x: x[0], reverse=True)
            return [item for _, item in scored[:50]]

        try:
            results = await asyncio.to_thread(_search_index, query, type)
            return json.dumps({"results": results}, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to search project index: {e}", exc_info=True)
            return json.dumps({"results": []})

    # =========================================================================
    # Knowledge Graph
    # =========================================================================

    @mcp.tool(
        name="knowledge-graph",
        annotations=tool_annotations(
            {
                "title": "Knowledge Graph Stats",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_graph_tool(
        query: str | None = None,
        full: bool = False,
    ) -> str:
        """Return knowledge graph statistics.

        Args:
            query: Optional search query (reserved for future use)
            full: Whether to return full graph data (reserved for future use)
        """
        metrics.track_tool("knowledge_graph", skill="knowledge")

        def _get_graph_stats() -> dict[str, Any]:
            rag_dir = get_rag_dir()
            manifest_path = rag_dir / "_meta" / "manifest.yaml"

            stats = {
                "skills": 0,
                "collections": 0,
                "chains": 0,
                "relationships": 0,
                "documents": 0,
            }

            if manifest_path.exists():
                try:
                    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                    manifest_stats = manifest.get("stats", {})
                    stats["skills"] = manifest_stats.get("skills", 0)
                    stats["documents"] = manifest.get("total", 0)
                    entries = manifest.get("entries", [])
                    if isinstance(entries, list):
                        type_counts: dict[str, int] = {}
                        for entry in entries:
                            if isinstance(entry, dict):
                                t = entry.get("category", entry.get("type", "unknown"))
                                type_counts[t] = type_counts.get(t, 0) + 1
                        stats["collections"] = len(type_counts)
                except Exception:
                    pass

            try:
                from src.config.paths import get_documents_dir
                docs_dir = get_documents_dir()
                if docs_dir.exists():
                    doc_count = sum(1 for f in docs_dir.rglob("*") if f.is_file())
                    stats["documents"] = max(stats["documents"], doc_count)
            except Exception:
                pass

            return knowledge_graph_deprecation_payload(stats)

        try:
            result = await asyncio.to_thread(_get_graph_stats)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to get knowledge graph stats: {e}", exc_info=True)
            return json.dumps({
                "success": False,
                "stats": {"skills": 0, "collections": 0, "chains": 0, "relationships": 0, "documents": 0},
                "error": str(e),
            })

    # =========================================================================
    # Project Index Stats
    # =========================================================================

    @mcp.tool(
        name="knowledge-project-index-stats",
        annotations=tool_annotations(
            {
                "title": "Project Index Statistics",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_project_index_stats_tool() -> str:
        """Return project index statistics from the RAG manifest."""
        metrics.track_tool("knowledge_project_index_stats", skill="knowledge")

        try:
            manifest_path = get_rag_dir() / "_meta" / "manifest.yaml"
            if not manifest_path.exists():
                return json.dumps({
                    "skills": 0, "pages": 0, "mcp-tools": 0, "actions": 0,
                    "commands": 0, "adrs": 0, "chains": 0, "agents": 0,
                    "total": 0, "lastIndexed": None,
                })

            manifest = yaml.safe_load(manifest_path.read_text())
            stats = manifest.get("stats", {})

            return json.dumps({
                "skills": stats.get("skills", 0),
                "pages": stats.get("pages", 0),
                "mcp-tools": stats.get("mcp-tools", 0),
                "mcp_tools": stats.get("mcp-tools", 0),
                "actions": stats.get("actions", 0),
                "commands": stats.get("cli-commands", 0),
                "adrs": stats.get("adrs", 0),
                "chains": 0,
                "agents": stats.get("agents", 0),
                "total": manifest.get("total", 0),
                "lastIndexed": manifest.get("indexed_at"),
                "last_indexed": manifest.get("indexed_at"),
            }, indent=2)
        except Exception as e:
            logger.error(f"Failed to read project index stats: {e}")
            return json.dumps({"error": str(e)})

    # =========================================================================
    # Unified Search
    # =========================================================================

    @mcp.tool(
        name="search-stats",
        annotations=tool_annotations(
            {
                "title": "Search Stats",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def search_stats_tool() -> str:
        """Return BM25 index freshness and ADR-739 budget settings."""
        metrics.track_tool("search_stats", skill="knowledge")
        return json.dumps(await asyncio.to_thread(search_stats), indent=2, default=str)

    @mcp.tool(
        name="search-tune",
        annotations=tool_annotations(
            {
                "title": "Search Budget Recommendation",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def search_tune_tool(query: str = "") -> str:
        """Recommend a search budget; never applies the switch automatically."""
        metrics.track_tool("search_tune", skill="knowledge")
        return json.dumps(search_tune(query=query), indent=2, default=str)

    @mcp.tool(
        name="unified-search",
        annotations=tool_annotations(
            {
                "title": "Search All Knowledge Sources",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def unified_search_tool(
        query: str = "",
        q: str = "",
        scopes: list[str] | None = None,
        mode: str = "hybrid",
        top_k: int = 10,
        max_results: int | None = None,
        project: str | None = None,
        budget: str | None = None,
        category: str | None = None,
        include_stale_documents: bool = False,
    ) -> str:
        """Search across all Augur knowledge sources.

        Args:
            query: Search query (supports regex, dashboard alias: q)
            q: Dashboard alias for query
            scopes: Sources to search (memory, knowledge, skills, rag, decisions). Default: all.
            mode: Search mode (keyword, metadata, hybrid, iterative)
            top_k: Maximum results to return (default 10, dashboard alias: max_results)
            max_results: Dashboard alias for top_k
            project: Optional project filter
            budget: Optional retrieval budget (conservative, balanced, tokenmax)
            category: Optional Browse-category scope (documents, vault, wiki,
                skills, adrs, ...). When set, results are restricted to that
                category so a per-tab search stays scoped to the active tab.
            include_stale_documents: Include out-of-sync document bodies for
                diagnostics. Defaults false.

        Returns:
            str: JSON with search results including scope labels
        """
        # Accept dashboard param names
        query = query or q
        if max_results is not None:
            top_k = max_results
        metrics.track_tool("unified_search", skill="knowledge")

        try:
            unified = UnifiedSearcher(scopes=scopes)
            results = unified.search(
                query=query,
                scopes=scopes,
                top_k=top_k,
                budget=budget,
                category=category,
                include_stale_documents=include_stale_documents,
            )

            result_list = [r if isinstance(r, dict) else r.to_dict() for r in results]
            _attach_brain_ids(result_list)
            _enrich_hit_display_fields(result_list)
            budget_name = result_list[0].get("budget") if result_list else budget
            limit = top_k
            if budget_name:
                from src.lib.index.search_config import budget_top_k, load_search_config

                limit = budget_top_k(load_search_config(), budget_name)
            return json.dumps(
                {
                    "success": True,
                    "query": query,
                    "scopes": scopes or ["memory", "knowledge", "skills", "rag"],
                    "mode": mode,
                    "budget": budget_name,
                    "result_count": len(result_list),
                    "count": len(result_list),
                    "limit": limit,
                    "results": result_list,
                },
                indent=2,
            )
        except ValueError as e:
            return json.dumps({"success": False, "error": str(e)})
        except Exception as e:
            logger.error(f"Unified search failed: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    # =========================================================================
    # Search Status
    # =========================================================================

    @mcp.tool(
        name="knowledge-search-status",
        annotations=tool_annotations(
            {
                "title": "Knowledge Search Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def knowledge_search_status_tool() -> str:
        """Return search index status for the knowledge search block."""
        metrics.track_tool("knowledge_search_status", skill="knowledge")

        def _get_status() -> dict:
            rag_dir = get_rag_dir()
            manifest_path = rag_dir / "_meta" / "manifest.yaml"

            indexed_count = 0
            last_indexed = None
            sources: list[str] = []

            if manifest_path.exists():
                try:
                    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
                    indexed_count = manifest.get("total", 0)
                    last_indexed = manifest.get("indexed_at")
                    entries = manifest.get("entries", [])
                    if isinstance(entries, list):
                        seen: set[str] = set()
                        for entry in entries:
                            if isinstance(entry, dict):
                                src = entry.get("category") or entry.get("type") or entry.get("source", "")
                                if src and src not in seen:
                                    sources.append(src)
                                    seen.add(src)
                except Exception:
                    pass

            try:
                from src.config.paths import get_documents_dir
                docs_dir = get_documents_dir()
                if docs_dir.exists():
                    doc_count = sum(1 for f in docs_dir.rglob("*") if f.is_file())
                    if not indexed_count:
                        indexed_count = doc_count
            except Exception:
                pass

            return {
                "status": "ready" if indexed_count > 0 else "empty",
                "indexed_count": indexed_count,
                "last_indexed": last_indexed,
                "sources": sources,
            }

        try:
            result = await asyncio.to_thread(_get_status)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error(f"knowledge-search-status failed: {e}", exc_info=True)
            return json.dumps({"status": "error", "error": str(e)})

    # =========================================================================
    # List Knowledge Documents
    # =========================================================================

    @mcp.tool(
        name="list-knowledge-documents",
        annotations=tool_annotations(
            {
                "title": "List Knowledge Documents",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_knowledge_documents_tool() -> str:
        """List document files from ~/Documents/Augur/."""
        metrics.track_tool("list_knowledge_documents", skill="knowledge")

        def _list_docs() -> list[dict]:
            try:
                from src.config.paths import get_documents_dir
                docs_dir = get_documents_dir()
            except ImportError:
                docs_dir = Path.home() / "Documents" / "Augur"

            if not docs_dir.exists():
                return []

            TEXT_EXTS = {".md", ".txt", ".pdf", ".docx", ".doc", ".csv", ".json", ".yaml", ".yml"}

            docs: list[dict] = []
            for f in sorted(docs_dir.rglob("*")):
                if not f.is_file():
                    continue
                if f.name.startswith(".") or f.name.startswith("_"):
                    continue
                if f.suffix.lower() not in TEXT_EXTS:
                    continue
                try:
                    rel = f.relative_to(docs_dir)
                    parts = rel.parts
                    # Flat layout: parts[0] is the skill name (no bundle prefix).
                    skill = parts[0] if len(parts) > 1 else "general"
                    size = f.stat().st_size
                    docs.append({
                        "title": f.stem.replace("-", " ").replace("_", " ").title(),
                        "path": str(f),
                        "type": f.suffix.lstrip(".").lower() or "unknown",
                        "size": size,
                        "skill": skill,
                    })
                except Exception:
                    continue
            return docs

        try:
            docs = await asyncio.to_thread(_list_docs)
            return json.dumps({"documents": docs, "total": len(docs)}, indent=2, default=str)
        except Exception as e:
            logger.error(f"list-knowledge-documents failed: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    # =========================================================================
    # OCR Queue
    # =========================================================================

    @mcp.tool(
        name="list-knowledge-ocr-queue",
        annotations=tool_annotations(
            {
                "title": "List OCR Queue",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_knowledge_ocr_queue_tool() -> str:
        """List PDF and image files in ~/Documents/Augur/ that can be OCR-processed."""
        metrics.track_tool("list_knowledge_ocr_queue", skill="knowledge")

        def _list_ocr() -> list[dict]:
            try:
                from src.config.paths import get_documents_dir
                docs_dir = get_documents_dir()
            except ImportError:
                docs_dir = Path.home() / "Documents" / "Augur"

            if not docs_dir.exists():
                return []

            OCR_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".tiff", ".tif", ".bmp"}

            items: list[dict] = []
            for f in sorted(docs_dir.rglob("*")):
                if not f.is_file():
                    continue
                if f.name.startswith("."):
                    continue
                if f.suffix.lower() not in OCR_EXTS:
                    continue
                try:
                    sidecar = f.with_suffix(".txt")
                    status = "done" if sidecar.exists() else "pending"
                    items.append({
                        "title": f.stem.replace("-", " ").replace("_", " ").title(),
                        "path": str(f),
                        "type": f.suffix.lstrip(".").lower(),
                        "status": status,
                    })
                except Exception:
                    continue
            return items

        try:
            items = await asyncio.to_thread(_list_ocr)
            return json.dumps({"queue": items, "total": len(items)}, indent=2, default=str)
        except Exception as e:
            logger.error(f"list-knowledge-ocr-queue failed: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

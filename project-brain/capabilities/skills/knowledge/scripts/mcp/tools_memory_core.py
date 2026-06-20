"""Core memory MCP tools: search, stats, index, decision/preference logging, curation.

Split from tools_memory.py for module size management.
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
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.annotations import tool_annotations
except ImportError:

    def tool_annotations(annotations: dict) -> dict:
        return annotations

from src.lib.knowledge import DailyLogger, MemoryStore, MemoryCurator
from src.lib.knowledge.search import MemorySearcher
from src.lib.knowledge._types import SearchMode
from src.lib.index.rrf import RankedHit, fuse
from src.lib.index.search_config import (
    budget_top_k,
    load_search_config,
    resolve_budget_name,
)
from skills.wiki.scripts.wiki_query_runner import run_query

try:
    from src.mcp.augur_shared.logging import get_entity_logger
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        return logging.getLogger(name)


logger = get_entity_logger("mcp.knowledge.memory.core")
_SEARCH_STOPWORDS = {
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "how",
    "did",
    "does",
    "do",
    "our",
    "we",
    "recently",
    "change",
    "changed",
    "made",
    "captured",
    "about",
    "have",
    "has",
    "the",
    "this",
    "that",
}


def _normalize_search_mode(mode: str) -> SearchMode:
    try:
        return SearchMode(mode)
    except ValueError:
        return SearchMode.HYBRID


def _prepare_search_query(query: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\s_-]+", " ", query).lower()
    tokens = [token for token in cleaned.split() if len(token) > 2 and token not in _SEARCH_STOPWORDS]
    return " ".join(tokens[:8]) or query.strip()


def _search_memory_results(
    *,
    query: str,
    mode: str = "hybrid",
    category: str | None = None,
    source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    top_k: int = 5,
    budget: str | None = None,
) -> list[dict[str, Any]]:
    cfg = load_search_config()
    budget_name = resolve_budget_name(cfg, budget)
    effective_top_k = budget_top_k(cfg, budget_name) if budget is not None else top_k
    searcher = MemorySearcher()
    prepared_query = _prepare_search_query(query)
    results = searcher.search(
        query=prepared_query,
        mode=_normalize_search_mode(mode),
        category=category,
        source=source,
        date_from=date_from,
        date_to=date_to,
        top_k=effective_top_k,
    )
    if not results and prepared_query != query.strip():
        results = searcher.search(
            query=query.strip(),
            mode=_normalize_search_mode(mode),
            category=category,
            source=source,
            date_from=date_from,
            date_to=date_to,
            top_k=effective_top_k,
        )
    payloads = [result.to_dict() if hasattr(result, "to_dict") else dict(result) for result in results]
    ranked_hits: list[RankedHit] = []
    for index, payload in enumerate(payloads):
        file_path = payload.get("file_path") or payload.get("path") or ""
        line_number = payload.get("line_number")
        doc_id = f"{file_path}:{line_number}" if file_path and line_number is not None else str(file_path or index)
        ranked_hits.append(
            RankedHit(
                doc_id=doc_id,
                rank=index + 1,
                raw_score=float(payload.get("relevance", payload.get("score", 0.0)) or 0.0),
                snippet=str(payload.get("content", "")),
                payload=payload,
            )
        )

    fused = fuse(
        {"memory": ranked_hits},
        k=int(cfg["rrf"].get("k", 60)),
        top_k=effective_top_k,
    )
    return [
        {
            **(row.get("payload") or {}),
            "doc_id": row["doc_id"],
            "score": row["score"],
            "budget": budget_name,
            "provenance": row["provenance"],
        }
        for row in fused
    ]


def _memory_profile_regenerate_impl() -> dict[str, Any]:
    result = run_query("profile-human-api")
    details = result.to_dict() if hasattr(result, "to_dict") else {
        "success": getattr(result, "success", False),
        "query_id": getattr(result, "query_id", "profile-human-api"),
        "error": getattr(result, "error", None),
        "output_path": getattr(result, "output_path", None),
    }
    if not getattr(result, "success", False):
        return {
            "success": False,
            "error": "Failed to regenerate wiki profile",
            "details": details,
        }
    return {
        "success": True,
        "message": "Profile regenerated successfully",
        "output": f"Wrote profile-human-api to {getattr(result, 'output_path', None)}",
        "details": details,
    }


def register_memory_core_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
    daily_logger: DailyLogger,
    memory_store: MemoryStore,
    curator: MemoryCurator,
) -> None:
    """Register core memory tools (search, stats, index, logging, curation, profile)."""

    @mcp.tool(
        name="memory-search",
        annotations=tool_annotations(
            {
                "title": "Search Augur Memory",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def memory_search_tool(
        query: str,
        mode: str = "hybrid",
        category: str | None = None,
        source: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        top_k: int = 5,
        budget: str | None = None,
    ) -> str:
        """Search Augur memory for decisions, patterns, and preferences.

        IMPORTANT: Use this tool BEFORE answering questions like:
        - "What did we decide about X?"
        - "What's my preference for Y?"
        - "Have we discussed Z before?"

        This enables deterministic lookup of past decisions and context.

        Args:
            query: Search query (supports regex)
            mode: Search mode (ignored, mapped to RAG iterative_search)
            category: Filter by category (decision, pattern, preference, event)
            source: Filter by source (daily logs or curated MEMORY.md)
            date_from: Start date filter (YYYY-MM-DD)
            date_to: End date filter (YYYY-MM-DD)
            top_k: Maximum results to return (default 5)
            budget: Optional retrieval budget (conservative, balanced, tokenmax)

        Returns:
            str: JSON with search results and metadata
        """
        metrics.track_tool("memory_search", skill="knowledge")

        results = _search_memory_results(
            query=query,
            mode=mode,
            category=category,
            source=source,
            date_from=date_from,
            date_to=date_to,
            top_k=top_k,
            budget=budget,
        )
        budget_name = results[0]["budget"] if results else resolve_budget_name(load_search_config(), budget)

        return json.dumps(
            {
                "success": True,
                "query": query,
                "normalized_query": _prepare_search_query(query),
                "mode": _normalize_search_mode(mode).value,
                "budget": budget_name,
                "result_count": len(results),
                "results": results,
            },
            indent=2,
        )

    @mcp.tool(
        name="memory-stats",
        annotations=tool_annotations(
            {
                "title": "Memory Stats",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def memory_stats_tool() -> str:
        """Get memory system statistics and index health."""
        metrics.track_tool("memory_stats", skill="knowledge")

        try:
            from src.lib.knowledge.search import MemorySearcher

            searcher = MemorySearcher()
            stats = searcher.get_stats()
            return json.dumps({"success": True, **stats}, indent=2)
        except Exception as e:
            logger.error(f"Failed to load memory stats: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="memory-rebuild-index",
        annotations=tool_annotations(
            {
                "title": "Rebuild Memory Index",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def memory_rebuild_index_tool(force: bool = True) -> str:
        """Rebuild the memory YAML index used by search."""
        metrics.track_tool("memory_rebuild_index", skill="knowledge")

        try:
            from src.lib.knowledge.search import MemorySearcher

            searcher = MemorySearcher()
            indexed_entries = searcher.build_index(force=force)
            return json.dumps(
                {
                    "success": True,
                    "indexed_entries": indexed_entries,
                    "message": f"Rebuilt memory index with {indexed_entries} entries",
                },
                indent=2,
            )
        except Exception as e:
            logger.error(f"Failed to rebuild memory index: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="memory-log-decision",
        annotations=tool_annotations(
            {
                "title": "Log a Decision",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def memory_log_decision_tool(
        topic: str,
        decision: str,
        reasoning: str | None = None,
        confidence: str = "medium",
        category: str | None = None,
    ) -> str:
        """Log a decision made during the session.

        Records decisions to daily log for later curation into MEMORY.md.
        Use this when:
        - User makes an explicit choice between options
        - A workflow decision is established
        - An important preference is determined

        Args:
            topic: Decision topic/key (e.g., "Vitamin D timing")
            decision: The actual decision (e.g., "Take in morning with breakfast")
            reasoning: Why this decision was made
            confidence: Confidence level (low, medium, high)
            category: Category (Health, Career, Workflow, General)

        Returns:
            str: JSON confirmation of logged decision
        """
        metrics.track_tool("memory_log_decision", skill="knowledge")

        daily_logger.log_decision(
            topic=topic,
            decision=decision,
            reasoning=reasoning,
            confidence=confidence,
            category=category,
        )

        return json.dumps(
            {
                "success": True,
                "logged": {
                    "type": "decision",
                    "topic": topic,
                    "decision": decision,
                    "confidence": confidence,
                    "category": category,
                },
                "message": f"Decision logged: {topic}",
            },
            indent=2,
        )

    @mcp.tool(
        name="memory-log-preference",
        annotations=tool_annotations(
            {
                "title": "Log a User Preference",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def memory_log_preference_tool(
        preference: str,
        value: str,
        source: str | None = None,
    ) -> str:
        """Log a user preference discovered during the session.

        Records preferences to daily log for later curation.
        Use this when:
        - User states a preference explicitly
        - A pattern suggests a preference
        - Settings or configurations are chosen

        Args:
            preference: Preference name (e.g., "Response format")
            value: Preference value (e.g., "Concise, no emojis")
            source: How the preference was discovered

        Returns:
            str: JSON confirmation of logged preference
        """
        metrics.track_tool("memory_log_preference", skill="knowledge")

        daily_logger.log_user_preference(
            preference=preference,
            value=value,
            source=source,
        )

        return json.dumps(
            {
                "success": True,
                "logged": {
                    "type": "preference",
                    "preference": preference,
                    "value": value,
                    "source": source,
                },
                "message": f"Preference logged: {preference}",
            },
            indent=2,
        )

    @mcp.tool(
        name="memory-curate",
        annotations=tool_annotations(
            {
                "title": "Curate Memory",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def memory_curate_tool(
        days_back: int = 7,
        archive_processed: bool = False,
    ) -> str:
        """Curate daily logs into persistent MEMORY.md.

        Extracts decisions, patterns, and preferences from daily logs
        and distills them into the curated MEMORY.md file.

        Should be run periodically (e.g., weekly) to maintain memory.

        Args:
            days_back: Number of days to look back (default 7)
            archive_processed: Move processed logs to archive (default False)

        Returns:
            str: JSON summary of curation results
        """
        metrics.track_tool("memory_curate", skill="knowledge")

        result = curator.curate(
            days_back=days_back,
            archive_processed=archive_processed,
        )
        indexed_entries = await asyncio.to_thread(MemorySearcher().build_index, True)

        return json.dumps(
            {
                "success": True,
                "curation_summary": result,
                "indexed_entries": indexed_entries,
                "message": f"Curated {result['entries_added']} entries from {result['logs_processed']} daily logs",
            },
            indent=2,
        )

    @mcp.tool(
        name="memory-profile-regenerate",
        annotations=tool_annotations(
            {
                "title": "Regenerate Memory Profile",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def memory_profile_regenerate_tool() -> str:
        """Regenerate the memory profile wiki query from memory logs and curated memory."""
        metrics.track_tool("memory_profile_regenerate", skill="knowledge")
        try:
            result = await asyncio.to_thread(_memory_profile_regenerate_impl)
        except Exception as exc:
            return json.dumps(
                {
                    "success": False,
                    "error": "Failed to regenerate wiki profile",
                    "details": str(exc),
                }
            )

        return json.dumps(result)

    @mcp.tool(
        name="memory-add-decision",
        annotations=tool_annotations(
            {
                "title": "Add Decision to MEMORY.md",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def memory_add_decision_tool(
        topic: str,
        decision: str,
        category: str = "General",
        source: str | None = None,
        confidence: str = "medium",
    ) -> str:
        """Add a decision directly to curated MEMORY.md.

        Unlike memory-log-decision (which logs to daily file), this
        adds directly to the persistent MEMORY.md. Use for:
        - Important decisions that should be immediately persistent
        - Retroactive decisions discovered from past conversations
        - System-level configuration decisions

        Args:
            topic: Decision topic/key
            decision: The actual decision
            category: Category (Health, Career, Workflow, General)
            source: Source of the decision
            confidence: Confidence level (low, medium, high)

        Returns:
            str: JSON confirmation
        """
        metrics.track_tool("memory_add_decision", skill="knowledge")

        memory_store.add_decision(
            topic=topic,
            decision=decision,
            category=category,
            source=source,
            confidence=confidence,
        )

        return json.dumps(
            {
                "success": True,
                "added": {
                    "type": "decision",
                    "topic": topic,
                    "decision": decision,
                    "category": category,
                },
                "message": f"Decision added to MEMORY.md: {topic}",
            },
            indent=2,
        )

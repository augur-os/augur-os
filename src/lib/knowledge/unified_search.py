"""
Unified Search — Single entry point for searching across all Augur knowledge sources.

ADR-033 Component 5: Extends search across multiple scopes
using the centralized RAG SearchEngine (ADR-127).

Scopes:
- memory: vault-backed memory logs and profile state
- knowledge: vault-backed knowledge data
- skills: managed shared/private skill roots (skill documentation)
- rag: centralized RAG indexes under get_rag_dir()
- decisions: get_adr_dir() (Architecture Decision Records) — ADR-166
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config.paths import (
    get_managed_skill_source_dirs,
    get_memory_dir,
    get_project_root,
    get_rag_dir,
)
from src.lib.index.unified_search import iterative_search as rag_iterative_search
from src.lib.brain_stack import BrainStack, resolve_active_stack
from src.lib.skill_paths import get_own_data_dir
from src.logging import get_entity_logger

# Import all helpers from sibling module (behavior-preserving split)
from src.lib.knowledge._search_helpers import (  # noqa: F401
    DEFAULT_SCOPES,
    VALID_SCOPES,
    _SearchSource,
    _brain_knowledge_dirs,
    _browse_index_lookup_intent,
    _current_work_intent,
    _dedup_key,
    _document_query_intent,
    _exact_rag_index_hits,
    _hit_browse_category,
    _hit_metadata,
    _hit_mtime,
    _hit_source_path,
    _normalize_filename_query,
    _normalize_path,
    _path_key,
    _query_terms,
    _rag_index_match_score,
    _rag_relative_category,
    _RAG_FAMILY_TO_CATEGORY,
    _rank_and_dedup_hits,
    _ranking_score,
    _read_frontmatter,
    _read_frontmatter_cached,
    _recent_rag_document_hits,
    _recency_score,
    _tier_knowledge_sources,
    _tokenize_search_text,
)

logger = get_entity_logger(__name__)


class UnifiedSearcher:
    """
    Single entry point for searching across all Augur knowledge sources
    using the global RAG SearchEngine.
    """

    def __init__(
        self,
        scopes: list[str] | None = None,
        *,
        stack: BrainStack | None = None,
    ):
        """
        Args:
            scopes: List of scopes to search. Default: all.
                    Options: "memory", "knowledge", "skills", "rag", "decisions"
            stack: Optional explicit Global/User/Project brain stack. When omitted,
                    the active stack is resolved lazily for tier-federated scopes.
        """
        self._project_root = get_project_root()
        self._memory_dir = get_memory_dir()
        self._stack = stack
        self._stack_checked = stack is not None

        if scopes is not None:
            invalid = set(scopes) - VALID_SCOPES
            if invalid:
                raise ValueError(f"Invalid scope(s): {invalid}. Valid scopes: {VALID_SCOPES}")
            self._default_scopes = list(scopes)
        else:
            self._default_scopes = list(DEFAULT_SCOPES)

    def _active_stack(self) -> BrainStack | None:
        if self._stack is not None:
            return self._stack
        if self._stack_checked:
            return None
        self._stack_checked = True
        try:
            self._stack = resolve_active_stack(cwd=self._project_root)
        except Exception:  # noqa: BLE001 - legacy non-tier search stays available
            return None
        return self._stack

    def _get_scope_sources(self, scope: str) -> list[_SearchSource]:
        if scope == "knowledge":
            stack = self._active_stack()
            tier_sources = _tier_knowledge_sources(stack) if stack is not None else []
            fallback_sources = [
                _SearchSource(path=path)
                for path in self._get_legacy_knowledge_paths()
                if _path_key(path) not in {_path_key(source.path) for source in tier_sources}
            ]
            return [*tier_sources, *fallback_sources]
        if scope in {"rag", "rag_index"}:
            return [_SearchSource(path=path, search_kind="rag") for path in self._get_scope_paths(scope)]
        return [_SearchSource(path=path) for path in self._get_scope_paths(scope)]

    def _get_legacy_knowledge_paths(self) -> list[Path]:
        try:
            p = get_own_data_dir(__file__)
            return [p] if p.exists() else []
        except ValueError:
            return []

    def _get_scope_paths(self, scope: str) -> list[Path]:
        """Get search directories for a given scope."""
        if scope == "memory":
            p = self._memory_dir
            return [p] if p.exists() else []
        elif scope == "knowledge":
            return [source.path for source in self._get_scope_sources(scope)]
        elif scope == "skills":
            paths: list[Path] = []
            for skills_dir in get_managed_skill_source_dirs(self._project_root):
                if not skills_dir.exists():
                    continue
                for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
                    paths.append(skill_md.parent)
            return paths
        elif scope == "rag":
            rag_dir = get_rag_dir()
            return [rag_dir] if rag_dir.exists() else []
        elif scope == "rag_index":
            rag_dir = get_rag_dir()
            if rag_dir.exists():
                return [rag_dir]
            return []
        elif scope == "decisions":
            from src.lib.adr_utils import get_adr_dir

            p = get_adr_dir()
            return [p] if p.exists() else []
        return []

    def _tag_source_brain(self, hit: dict[str, Any], source: _SearchSource) -> None:
        if not source.brain_id:
            return
        hit["source_brain"] = source.brain_id
        hit["source_brain_tier"] = source.brain_tier
        hit["source_brain_root"] = str(source.path)
        hit.setdefault("brain_id", source.brain_id)

    def search(
        self,
        query: str,
        scopes: list[str] | None = None,
        top_k: int = 10,
        budget: str | None = None,
        *,
        category: str | None = None,
        include_stale_documents: bool = False,
    ) -> list[dict[str, Any]]:
        """Search across configured scopes using RAG iterative_search.

        Args:
            query: Search query
            scopes: Sources to search. Default: all configured scopes.
            top_k: Maximum results per scope.
            budget: Optional search budget name (conservative/balanced/tokenmax).
            category: Optional Browse-category scope (documents, vault, wiki,
                skills, adrs, ...). When set, results are filtered to hits that
                belong to that category so a per-tab search stays scoped to the
                tab instead of returning whole-knowledge-base results.
            include_stale_documents: Include document hits whose source changed
                after indexing. Defaults to false so search results do not
                surface out-of-sync document bodies.

        Returns:
            List of dictionaries containing search hits, tagged with scope.
        """
        active_scopes = scopes if scopes is not None else self._default_scopes

        invalid = set(active_scopes) - VALID_SCOPES
        if invalid:
            raise ValueError(f"Invalid scope(s): {invalid}. Valid scopes: {VALID_SCOPES}")

        budget_requested = budget is not None
        if budget is not None:
            from src.lib.index.search_config import (
                budget_top_k,
                load_search_config,
                resolve_budget_name,
            )

            cfg = load_search_config()
            budget = resolve_budget_name(cfg, budget)
            top_k = budget_top_k(cfg, budget)

        all_results: list[dict[str, Any]] = []

        candidate_k = max(top_k, 200) if category else max(top_k, 50)

        for scope in active_scopes:
            scope_sources = self._get_scope_sources(scope)

            for source in scope_sources:
                search_path = source.path
                try:
                    if source.search_kind == "rag":
                        scope_results = rag_iterative_search(
                            query,
                            [],
                            [],
                            [search_path],
                            top_k=candidate_k,
                            budget=None,
                            include_stale_documents=include_stale_documents,
                        )
                    else:
                        scope_results = rag_iterative_search(
                            query,
                            [search_path],
                            [],
                            [],
                            top_k=candidate_k,
                            budget=None,
                            include_stale_documents=include_stale_documents,
                        )

                    for group in scope_results:
                        if isinstance(group, dict) and "hits" in group:
                            for hit in group["hits"]:
                                hit_dict = dict(hit)
                                hit_dict["scope"] = scope
                                self._tag_source_brain(hit_dict, source)
                                all_results.append(hit_dict)
                        elif isinstance(group, dict) and "file" in group:
                            hit_dict = dict(group)
                            hit_dict["scope"] = scope
                            self._tag_source_brain(hit_dict, source)
                            all_results.append(hit_dict)

                    if source.search_kind == "rag":
                        for hit in _recent_rag_document_hits(
                            query,
                            search_path,
                            include_stale_documents=include_stale_documents,
                        ):
                            hit_dict = dict(hit)
                            hit_dict["scope"] = scope
                            self._tag_source_brain(hit_dict, source)
                            all_results.append(hit_dict)
                        for hit in _exact_rag_index_hits(query, search_path):
                            hit_dict = dict(hit)
                            hit_dict["scope"] = scope
                            self._tag_source_brain(hit_dict, source)
                            all_results.append(hit_dict)

                except Exception as e:
                    logger.warning(f"Search failed for scope={scope}, path={search_path}: {e}")
                    continue

        if category:
            from src.lib.index.watch_roots import resolve_watch_roots

            try:
                roots = resolve_watch_roots()
            except Exception as exc:  # pragma: no cover - registry/fs failure
                logger.warning("category scope unavailable (%s); skipping filter", exc)
                roots = []
            if roots:
                scoped: list[dict[str, Any]] = []
                for hit in all_results:
                    hit_category = _hit_browse_category(hit, roots)
                    if hit_category != category:
                        continue
                    hit["browse_category"] = hit_category
                    scoped.append(hit)
                all_results = scoped

        result_limit = top_k if budget_requested else top_k * len(active_scopes)
        return _rank_and_dedup_hits(all_results, query, result_limit)

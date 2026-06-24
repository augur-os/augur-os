"""
Memory Search - Ripgrep-based Search for Two-Layer Memory Architecture

Implements keyword search using ripgrep (consistent with ADR-004 Markdown RAG)
and a YAML index for metadata queries. No binary dependencies required.

ADR-033 hardening: secure JSON parsing, incremental indexing with checksums,
path-normalized deduplication, iterative LLM search via AI bridge.

Index: {memory_dir}/index.yaml
"""

import re
from pathlib import Path
from typing import Optional

import yaml

from src.config.paths import (
    get_daily_logs_dir,
    get_memory_dir,
    get_project_brain_skills_dir,
    get_project_root,
)
from src.lib.frontmatter_utils import load_skill_contract
from src.logging import get_entity_logger

# ---------------------------------------------------------------------------
# Re-exports: all public symbols remain importable from this module.
# ---------------------------------------------------------------------------
from ._types import (  # noqa: F401
    MemoryEntry,
    SearchEvaluation,
    SearchMode,
    SearchResult,
    _normalize_path,
)
from ._index import INDEX_VERSION, IndexMixin  # noqa: F401
from ._ripgrep import RipgrepMixin  # noqa: F401
from ._iterative import IterativeMixin  # noqa: F401

logger = get_entity_logger(__name__)


class MemorySearcher(IndexMixin, RipgrepMixin, IterativeMixin):
    """
    Ripgrep-based search across memory layers.

    Follows ADR-004 pattern:
    - Primary: ripgrep for full-text search (fast, regex-capable)
    - Secondary: YAML index for structured queries
    - No binary dependencies (SQLite, vector DBs)

    ADR-033 enhancements:
    - Secure JSON parsing (json.loads, not eval)
    - Incremental index with file checksums
    - Path-normalized deduplication
    - Iterative LLM search via AI bridge
    - Circuit breaker: skip LLM calls during sustained API outages
    """

    def __init__(self, search_root: Optional[Path] = None):
        """Initialize memory searcher.

        Args:
            search_root: Override search root directory. Defaults to the
                configured vault-backed memory directory.
        """
        self._memory_dir = get_memory_dir()
        self._search_root = search_root or self._memory_dir
        self._index_path = self._memory_dir / "index.yaml"
        self._daily_dir = get_daily_logs_dir()
        self._memory_file = self._memory_dir / "MEMORY.md"
        self._config = self._load_config()
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create memory directories if needed."""
        self._memory_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> dict:
        """Load knowledge config from test override or canonical skill metadata."""
        candidates = [
            # Test fixture / local override layout
            self._memory_dir.parent
            / "knowledge"
            / "config.yaml",
        ]
        for config_path in candidates:
            if not config_path.exists():
                continue
            try:
                raw = yaml.safe_load(config_path.read_text()) or {}
                if isinstance(raw, dict):
                    return raw
            except Exception:
                continue

        contract = load_skill_contract(get_project_brain_skills_dir(get_project_root()) / "knowledge")
        config = contract.get("config")
        return config if isinstance(config, dict) else {}

    # ------------------------------------------------------------------
    # Core search (Component 3: path-normalized dedup)
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        mode: SearchMode = SearchMode.HYBRID,
        category: Optional[str] = None,
        source: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """
        Search memory using ripgrep + YAML index.

        Args:
            query: Search query (supports regex)
            mode: Search mode (keyword, metadata, hybrid, iterative)
            category: Filter by category (decision, pattern, preference, event)
            source: Filter by source (daily, curated)
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            top_k: Maximum results to return

        Returns:
            List of SearchResult objects
        """
        # Dispatch iterative mode
        if mode == SearchMode.ITERATIVE:
            return self._iterative_search(query, top_k=top_k)

        results: list[SearchResult] = []

        if mode in (SearchMode.KEYWORD, SearchMode.HYBRID):
            rg_results = self._ripgrep_search(query, self._search_root)

            for match in rg_results:
                match_source = "daily" if "/daily/" in match["path"] else "curated"
                match_category = self._infer_category(match["content"])
                match_date = self._extract_date(match["path"], match["content"])

                if category and match_category != category:
                    continue
                if source and match_source != source:
                    continue
                if date_from and match_date < date_from:
                    continue
                if date_to and match_date > date_to:
                    continue

                relevance = self._calculate_relevance(query, match["content"])

                results.append(
                    SearchResult(
                        content=match["content"],
                        source=match_source,
                        category=match_category,
                        date=match_date,
                        relevance=relevance,
                        file_path=match["path"],
                        line_number=match["line_number"],
                    )
                )

        if mode in (SearchMode.METADATA, SearchMode.HYBRID):
            # Auto-rebuild stale index before metadata search
            if self._is_index_stale():
                self.build_index()
            index_results = self._search_index(query, category, source, date_from, date_to)
            results.extend(index_results)

        # Deduplicate using normalized paths (Component 3)
        seen: dict[tuple, SearchResult] = {}
        for r in results:
            key = (_normalize_path(r.file_path), r.line_number)
            existing = seen.get(key)
            if existing is None or r.relevance > existing.relevance:
                seen[key] = r

        unique_results = list(seen.values())
        unique_results.sort(key=lambda x: x.relevance, reverse=True)
        return unique_results[:top_k]

    def _search_index(
        self,
        query: str,
        category: Optional[str],
        source: Optional[str],
        date_from: Optional[str],
        date_to: Optional[str],
    ) -> list[SearchResult]:
        """Search YAML index for matching entries."""
        if not self._index_path.exists():
            self.build_index()

        if not self._index_path.exists():
            return []

        index_data = yaml.safe_load(self._index_path.read_text())
        results = []
        query_lower = query.lower()

        for entry in index_data.get("entries", []):
            content_lower = entry.get("content", "").lower()
            tags = entry.get("tags", [])

            match_score = 0
            if query_lower in content_lower:
                match_score = 0.8
            elif any(query_lower in tag for tag in tags):
                match_score = 0.6
            elif any(word in content_lower for word in query_lower.split()):
                match_score = 0.4
            else:
                continue

            if category and entry.get("category") != category:
                continue
            if source and entry.get("source") != source:
                continue
            if date_from and entry.get("date", "") < date_from:
                continue
            if date_to and entry.get("date", "") > date_to:
                continue

            raw_fp = entry.get("file_path")
            results.append(
                SearchResult(
                    content=entry.get("content", ""),
                    source=entry.get("source", "unknown"),
                    category=entry.get("category", "unknown"),
                    date=entry.get("date", ""),
                    relevance=match_score,
                    file_path=_normalize_path(raw_fp),
                    line_number=entry.get("line_number"),
                )
            )

        return results

    def _infer_category(self, content: str) -> str:
        """Infer category from content."""
        content_lower = content.lower()
        if "decision" in content_lower or "**topic**" in content_lower:
            return "decision"
        if "preference" in content_lower:
            return "preference"
        if "pattern" in content_lower:
            return "pattern"
        if "tool:" in content_lower:
            return "tool_execution"
        if "error" in content_lower:
            return "error"
        return "event"

    def _extract_date(self, path: str, content: str) -> str:
        """Extract date from path or content."""
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", path)
        if date_match:
            return date_match.group(1)

        date_match = re.search(r"\((\d{4}-\d{2}-\d{2})\)", content)
        if date_match:
            return date_match.group(1)

        return ""

    def _calculate_relevance(self, query: str, content: str) -> float:
        """Calculate relevance score (0.0 to 1.0)."""
        query_lower = query.lower()
        content_lower = content.lower()

        if query_lower in content_lower:
            ratio = len(query) / max(len(content), 1)
            return min(0.5 + ratio * 0.5, 1.0)

        query_words = set(query_lower.split())
        content_words = set(content_lower.split())
        overlap = len(query_words & content_words)
        if overlap > 0:
            return overlap / len(query_words) * 0.5

        return 0.0

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def search_decisions(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Convenience method to search only decisions."""
        return self.search(query, category="decision", top_k=top_k)

    def search_patterns(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Convenience method to search only patterns."""
        return self.search(query, category="pattern", top_k=top_k)

    def search_preferences(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Convenience method to search only preferences."""
        return self.search(query, category="preference", top_k=top_k)

    def get_stats(self) -> dict:
        """Get memory statistics."""
        stats = {
            "memory_dir": str(self._memory_dir),
            "index_exists": self._index_path.exists(),
            "index_stale": self._is_index_stale() if self._index_path.exists() else True,
            "daily_logs": 0,
            "memory_md_exists": self._memory_file.exists(),
        }

        if self._daily_dir.exists():
            stats["daily_logs"] = len(list(self._daily_dir.glob("*.md")))

        if self._index_path.exists():
            index_data = yaml.safe_load(self._index_path.read_text())
            stats["indexed_entries"] = index_data.get("entry_count", 0)
            stats["index_updated"] = index_data.get("updated", "never")
            stats["index_version"] = index_data.get("version", "unknown")

        return stats

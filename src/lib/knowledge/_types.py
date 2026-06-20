"""Types and data classes for the memory search module.

SearchMode, SearchResult, MemoryEntry, SearchEvaluation, and path normalization.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class SearchMode(Enum):
    """Search mode for memory queries."""

    KEYWORD = "keyword"  # Ripgrep full-text search
    METADATA = "metadata"  # YAML index queries
    HYBRID = "hybrid"  # Combined approach
    ITERATIVE = "iterative"  # LLM-in-the-loop via AI bridge


@dataclass
class SearchResult:
    """A single search result from memory."""

    content: str
    source: str  # 'daily' or 'curated'
    category: str  # 'decision', 'pattern', 'preference', 'event'
    date: str
    relevance: float  # 0.0 to 1.0 based on match quality
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    context: Optional[str] = None  # Surrounding lines
    scope: Optional[str] = None  # Scope label for unified search

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        result = {
            "content": self.content,
            "source": self.source,
            "category": self.category,
            "date": self.date,
            "relevance": self.relevance,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "context": self.context,
        }
        if self.scope is not None:
            result["scope"] = self.scope
        return result


@dataclass
class MemoryEntry:
    """Indexed memory entry for YAML index."""

    key: str
    content: str
    category: str
    source: str
    date: str
    file_path: str
    line_number: int
    tags: list[str]

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "content": self.content,
            "category": self.category,
            "source": self.source,
            "date": self.date,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "tags": self.tags,
        }


@dataclass
class SearchEvaluation:
    """Result of LLM evaluation of search results."""

    sufficient: bool
    refined_query: str
    reasoning: str


def _normalize_path(file_path: Optional[str]) -> Optional[str]:
    """Normalize a file path to absolute resolved form for consistent dedup."""
    if file_path is None:
        return None
    try:
        return str(Path(file_path).resolve())
    except (OSError, ValueError):
        return file_path

"""
knowledge._search_helpers — Module-level helpers for UnifiedSearcher.

Category mapping, scoring, ranking, RAG-specific lookup, brain source helpers.
All helpers are self-contained and do not import from unified_search.py.

Internal use by the knowledge package; do not import directly from outside.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import re
from typing import Any

from src.lib.index.sources import (
    document_index_status,
    document_status_is_searchable,
    document_status_warning,
)
from src.lib.brain_registry_models import Brain
from src.lib.brain_stack import BrainStack

# ---------------------------------------------------------------------------
# Hit source path helper
# ---------------------------------------------------------------------------


def _hit_source_path(hit: dict[str, Any]) -> str:
    """Best-effort original on-disk source path for a search hit."""
    metadata = hit.get("metadata") if isinstance(hit.get("metadata"), dict) else {}
    return str(
        hit.get("source_path") or (metadata or {}).get("source_path") or hit.get("file") or hit.get("path") or ""
    )


# ---------------------------------------------------------------------------
# Category mapping
# ---------------------------------------------------------------------------

# rag-index family directory -> Browse category.
_RAG_FAMILY_TO_CATEGORY = {
    "documents": "documents",
    "vault": "vault",
    "wiki": "wiki",
    "adrs": "adrs",
    "decisions": "adrs",
    "skills": "skills",
    "prompts": "prompts",
    "scripts": "scripts",
    "tests": "tests",
    "mcp-tools": "mcp-tools",
    "pages": "pages",
    "agents": "agents",
    "commands": "commands",
    "logs": "logs",
    "integrations": "integrations",
    "api-routes": "api-routes",
    "blocks": "blocks",
}


def _rag_relative_category(path_str: str) -> str | None:
    """Categorize a rag-index/chunk path by its family directory."""
    norm = path_str.replace("\\", "/")
    try:
        from src.config.paths import get_rag_dir as _get_rag_dir

        rag = str(_get_rag_dir()).replace("\\", "/").rstrip("/")
        if rag and norm.startswith(rag + "/"):
            norm = norm[len(rag) + 1 :]
    except Exception:
        pass
    parts = [p for p in norm.split("/") if p and p != "."]
    if not parts:
        return None
    head = parts[0]
    if head == "chunks" and len(parts) > 1:
        head = parts[1]
    return _RAG_FAMILY_TO_CATEGORY.get(head)


def _hit_browse_category(hit: dict[str, Any], roots: list[Any]) -> str | None:
    """Map a search hit to its Browse category."""
    from pathlib import Path as _Path

    from src.lib.index.watch_roots import categorize_path

    path_str = _hit_source_path(hit)
    if path_str:
        p = _Path(path_str)
        if p.is_absolute():
            try:
                category = categorize_path(p, roots)
            except Exception:
                category = None
            if category:
                return category
        category = _rag_relative_category(path_str)
        if category:
            return category
    scope = hit.get("scope")
    if scope == "skills":
        return "skills"
    if scope == "decisions":
        return "adrs"
    return None


# ---------------------------------------------------------------------------
# Scope constants
# ---------------------------------------------------------------------------

VALID_SCOPES = {"memory", "knowledge", "skills", "rag", "rag_index", "decisions"}
DEFAULT_SCOPES = ["rag", "rag_index", "memory", "knowledge", "skills", "decisions"]
_CURRENT_WORK_TERMS = {"current", "latest", "recent", "today", "now", "working", "editing"}
_DOCUMENT_QUERY_TERMS = {
    "deck",
    "doc",
    "docs",
    "docx",
    "document",
    "file",
    "pdf",
    "pitch",
    "ppt",
    "pptx",
    "presentation",
    "slide",
    "slides",
}
_QUERY_STOPWORDS = {
    "a",
    "an",
    "am",
    "and",
    "are",
    "find",
    "for",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "search",
    "that",
    "the",
    "to",
}


# ---------------------------------------------------------------------------
# Search source descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _SearchSource:
    path: Path
    brain_id: str | None = None
    brain_tier: str | None = None
    search_kind: str = "source"


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _normalize_path(path: str) -> str:
    """Normalize a file path."""
    return str(Path(path).resolve())


def _tokenize_search_text(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _query_terms(query: str) -> list[str]:
    return [token for token in _tokenize_search_text(query) if token not in _QUERY_STOPWORDS]


def _current_work_intent(query: str) -> bool:
    return bool(_CURRENT_WORK_TERMS & set(_tokenize_search_text(query)))


def _document_query_intent(query: str) -> bool:
    return bool(_DOCUMENT_QUERY_TERMS & set(_query_terms(query)))


# ---------------------------------------------------------------------------
# Frontmatter reading (cached)
# ---------------------------------------------------------------------------


def _read_frontmatter(path: str) -> dict[str, Any]:
    file_path = Path(path)
    if file_path.suffix.lower() != ".md" or not file_path.is_file():
        return {}
    try:
        stat = file_path.stat()
    except OSError:
        return {}
    return _read_frontmatter_cached(path, stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=512)
def _read_frontmatter_cached(path: str, mtime_ns: int, size: int) -> dict[str, Any]:
    del mtime_ns, size
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    try:
        import yaml

        data = yaml.safe_load(text[4:end]) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Scoring and ranking helpers
# ---------------------------------------------------------------------------


def _parse_timestamp(value: Any) -> float | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().strip("'\"")
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _hit_metadata(hit: dict[str, Any]) -> dict[str, Any]:
    file_path = str(hit.get("file") or "")
    metadata: dict[str, Any] = {}
    if file_path:
        metadata.update(_read_frontmatter(file_path))
    for key in (
        "source_path",
        "modified",
        "indexed_at",
        "created",
        "name",
        "document_title",
        "source",
    ):
        if key in hit and hit[key] not in (None, ""):
            metadata[key] = hit[key]
    return metadata


def _hit_mtime(hit: dict[str, Any], metadata: dict[str, Any]) -> tuple[float | None, bool]:
    source_path = metadata.get("source_path")
    if source_path:
        try:
            source = Path(str(source_path))
            if source.exists():
                return source.stat().st_mtime, True
        except OSError:
            pass
    for key in ("modified", "indexed_at", "created"):
        parsed = _parse_timestamp(metadata.get(key))
        if parsed is not None:
            return parsed, True
    file_path = str(hit.get("file") or "")
    if file_path:
        try:
            return Path(file_path).stat().st_mtime, False
        except OSError:
            return None, False
    return None, False


def _recency_score(mtime: float | None, authoritative: bool) -> float:
    if mtime is None:
        return 0.0
    age_days = max(0.0, (datetime.now(timezone.utc).timestamp() - mtime) / 86_400)
    if age_days <= 1:
        score = 100.0
    elif age_days <= 7:
        score = 70.0
    elif age_days <= 30:
        score = 40.0
    elif age_days <= 90:
        score = 15.0
    else:
        score = 0.0
    if not authoritative:
        return min(score, 10.0)
    return score


def _ranking_score(hit: dict[str, Any], query: str) -> float:
    metadata = _hit_metadata(hit)
    file_path = str(hit.get("file") or "")
    basename = Path(file_path).name if file_path else ""
    source_path = str(metadata.get("source_path") or "")
    haystack = " ".join(
        str(value)
        for value in (
            file_path,
            basename,
            source_path,
            hit.get("doc_id", ""),
            hit.get("content", ""),
            hit.get("snippet", ""),
            metadata.get("name", ""),
            metadata.get("document_title", ""),
            metadata.get("source", ""),
        )
    )
    terms = _query_terms(query)
    text_tokens = set(_tokenize_search_text(haystack))
    path_tokens = set(_tokenize_search_text(f"{file_path} {source_path}"))
    basename_tokens = set(_tokenize_search_text(basename))

    score = float(hit.get("score") or 0.0)
    score += 4.0 * sum(1 for term in terms if term in text_tokens)
    score += 8.0 * sum(1 for term in terms if term in path_tokens)
    score += 12.0 * sum(1 for term in terms if term in basename_tokens)

    normalized_query = " ".join(terms)
    normalized_text = " ".join(_tokenize_search_text(haystack))
    if normalized_query and normalized_query in normalized_text:
        score += 30.0

    if hit.get("scope") in {"rag", "rag_index"}:
        score += 3.0
    if "/_meta/" in file_path or file_path.endswith("/_meta"):
        score -= 100.0
    if _current_work_intent(query):
        mtime, authoritative = _hit_mtime(hit, metadata)
        score += _recency_score(mtime, authoritative)
    return score


# ---------------------------------------------------------------------------
# RAG document and index lookup helpers
# ---------------------------------------------------------------------------


def _recent_rag_document_hits(
    query: str,
    rag_dir: Path,
    limit: int = 25,
    *,
    include_stale_documents: bool = False,
) -> list[dict[str, Any]]:
    if not (_current_work_intent(query) and _document_query_intent(query)):
        return []

    documents_dir = rag_dir / "documents"
    if not documents_dir.is_dir():
        return []

    terms = set(_query_terms(query)) - _CURRENT_WORK_TERMS
    candidates: list[tuple[float, dict[str, Any]]] = []
    for document_path in documents_dir.rglob("*.md"):
        metadata = _read_frontmatter(str(document_path))
        index_status = document_index_status(metadata)
        if not document_status_is_searchable(
            index_status,
            include_stale_documents=include_stale_documents,
        ):
            continue
        mtime, authoritative = _hit_mtime({"file": str(document_path)}, metadata)
        recency = _recency_score(mtime, authoritative)
        if recency <= 0:
            continue
        try:
            body = document_path.read_text(encoding="utf-8", errors="replace")[:6000]
        except OSError:
            body = ""
        text = " ".join(
            str(value)
            for value in (
                document_path,
                metadata.get("name", ""),
                metadata.get("document_title", ""),
                metadata.get("source_path", ""),
                body,
            )
        )
        tokens = set(_tokenize_search_text(text))
        term_hits = sum(1 for term in terms if term in tokens)
        if terms and term_hits == 0:
            continue
        hit = {
            "file": str(document_path),
            "content": f"Recent document: {metadata.get('document_title') or metadata.get('name') or document_path.stem}",
            "score": recency + (term_hits * 10.0),
            "source_path": metadata.get("source_path"),
            "name": metadata.get("name", document_path.stem),
            "document_title": metadata.get("document_title", metadata.get("name", document_path.stem)),
        }
        if index_status:
            hit["index_status"] = index_status
        warning = document_status_warning(index_status)
        if warning:
            hit["stale_source_warning"] = warning
        candidates.append((float(hit["score"]), hit))

    candidates.sort(key=lambda item: (-item[0], str(item[1]["file"])))
    return [hit for _, hit in candidates[:limit]]


def _normalize_filename_query(value: str) -> str:
    return value.strip().strip("'\"").replace("\\", "/").lower()


def _browse_index_lookup_intent(query: str) -> bool:
    normalized_query = _normalize_filename_query(query)
    if len(normalized_query) < 8:
        return False
    if "/" in normalized_query or "\\" in query:
        return True
    if re.search(r"\.[a-z0-9]{1,8}$", normalized_query):
        return True
    if re.search(r"\d{4}[-_]\d{2}[-_]\d{2}", normalized_query):
        return True
    if " " not in normalized_query and (normalized_query.count("-") + normalized_query.count("_")) >= 2:
        return True
    return False


def _rag_index_match_score(query: str, metadata: dict[str, Any], index_path: Path) -> float:
    normalized_query = _normalize_filename_query(query)
    if not normalized_query:
        return 0.0
    query_stem = Path(normalized_query).stem
    values = [
        str(index_path),
        index_path.name,
        index_path.stem,
        metadata.get("source_path", ""),
        Path(str(metadata.get("source_path") or "")).name,
        Path(str(metadata.get("source_path") or "")).stem,
        metadata.get("id", ""),
        metadata.get("name", ""),
        metadata.get("title", ""),
        metadata.get("document_title", ""),
    ]
    score = 0.0
    for raw_value in values:
        value = _normalize_filename_query(str(raw_value))
        if not value:
            continue
        value_stem = Path(value).stem
        if value == normalized_query:
            score = max(score, 500.0)
        elif query_stem and value_stem == query_stem:
            score = max(score, 450.0)
        elif normalized_query in value:
            score = max(score, 300.0)
        elif query_stem and query_stem in value:
            score = max(score, 250.0)
    return score


def _exact_rag_index_hits(
    query: str,
    rag_dir: Path,
    limit: int = 25,
) -> list[dict[str, Any]]:
    if not _browse_index_lookup_intent(query) or not rag_dir.is_dir():
        return []

    candidates: list[tuple[float, dict[str, Any]]] = []
    for index_path in rag_dir.rglob("*.md"):
        if "/_meta/" in str(index_path).replace("\\", "/"):
            continue
        metadata = _read_frontmatter(str(index_path))
        score = _rag_index_match_score(query, metadata, index_path)
        if score <= 0:
            continue
        title = metadata.get("document_title") or metadata.get("title") or metadata.get("name") or index_path.stem
        hit = {
            "file": str(index_path),
            "content": metadata.get("description") or f"Indexed file: {title}",
            "score": score,
            "source_path": metadata.get("source_path"),
            "name": metadata.get("name", index_path.stem),
            "title": title,
            "document_title": title,
            "modified": metadata.get("modified"),
            "indexed_at": metadata.get("indexed_at"),
            "format": metadata.get("format"),
            "category": metadata.get("type") or metadata.get("category"),
            "type": metadata.get("type"),
            "hub": metadata.get("hub"),
            "provenance": ["browse-index"],
        }
        candidates.append((score, hit))

    candidates.sort(key=lambda item: (-item[0], str(item[1]["file"])))
    return [hit for _, hit in candidates[:limit]]


# ---------------------------------------------------------------------------
# Dedup and ranking
# ---------------------------------------------------------------------------


def _dedup_key(hit: dict[str, Any]) -> str:
    metadata = _hit_metadata(hit)
    source_path = str(metadata.get("source_path") or "")
    if source_path:
        return source_path
    return str(hit.get("file") or hit.get("doc_id") or "")


def _rank_and_dedup_hits(
    hits: list[dict[str, Any]],
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    ranked = sorted(
        hits,
        key=lambda hit: (-_ranking_score(hit, query), str(hit.get("file") or "")),
    )
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in ranked:
        key = _dedup_key(hit)
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(hit)
        if len(deduped) >= limit:
            break
    return deduped


# ---------------------------------------------------------------------------
# Brain source helpers
# ---------------------------------------------------------------------------


def _path_key(path: Path) -> str:
    try:
        return str(path.resolve(strict=False))
    except OSError:
        return str(path.absolute())


def _brain_knowledge_dirs(brain: Brain) -> tuple[Path, ...]:
    root = Path(brain.data_root)
    candidates = (
        root / "knowledge",
        root / "notes",
        root / "wiki",
        root / "sources",
    )
    existing = tuple(path for path in candidates if path.is_dir())
    return existing or ((root,) if root.is_dir() else ())


def _tier_knowledge_sources(stack: BrainStack) -> list[_SearchSource]:
    by_path: dict[str, _SearchSource] = {}
    for brain in stack.ordered():
        for path in _brain_knowledge_dirs(brain):
            by_path[_path_key(path)] = _SearchSource(
                path=path,
                brain_id=brain.id,
                brain_tier=brain.type.value,
            )
    return list(by_path.values())

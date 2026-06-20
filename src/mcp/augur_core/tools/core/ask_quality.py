"""Deterministic context-support checks for /ask."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

CLIENT_MEMORY_FAMILIES = {"codex_memory", "agent_global_memories"}
GENERIC_QUERY_TERMS = {
    "what",
    "about",
    "this",
    "that",
    "these",
    "those",
    "thing",
    "things",
    "it",
    "its",
    "the",
    "and",
    "for",
    "with",
    "from",
    "into",
    "onto",
    "over",
    "under",
    "why",
    "how",
    "when",
    "where",
    "who",
    "which",
    "should",
    "could",
    "would",
    "does",
    "did",
    "not",
    "working",
    "work",
    "current",
    "currently",
    "latest",
    "today",
    "focus",
    "focused",
    "now",
    "are",
    "was",
    "were",
    "been",
    "being",
    "has",
    "have",
    "had",
    "can",
    "will",
    "might",
    "must",
    "shall",
    "know",
    "want",
    "need",
    "tell",
    "give",
    "show",
    "list",
}


@dataclass(frozen=True)
class AskContextAssessment:
    supported: bool
    answer_mode: str
    flags: list[str]
    source_count: int
    total_chars: int

    def to_dict(self) -> dict[str, object]:
        flags = list(self.flags)
        return {
            "supported": self.supported,
            "answer_mode": self.answer_mode,
            "flags": flags,
            "quality_flags": list(flags),
            "source_count": self.source_count,
            "total_chars": self.total_chars,
        }


def _source_text(source: dict[str, Any]) -> str:
    for key in ("text", "body", "content", "summary"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def _source_dates(source: dict[str, Any]) -> list[date]:
    dates: list[date] = []
    for key in ("updated_at", "modified_at"):
        parsed = _parse_date(source.get(key))
        if parsed is not None:
            dates.append(parsed)
    return dates


def _source_effective_date(source: dict[str, Any]) -> date | None:
    dates = _source_dates(source)
    if not dates:
        return None
    return max(dates)


def _is_current_focus_question(question: str) -> bool:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in question)
    compact = f" {' '.join(normalized.split())} "
    if " not working " in compact:
        return False
    if any(phrase in compact for phrase in (" working on ", " current focus ", " focused on ")):
        return True
    return any(f" {term} " in compact for term in ("now", "currently", "latest", "today"))


def _query_terms(question: str) -> list[str]:
    return [
        token
        for token in ("".join(char.lower() if char.isalnum() else " " for char in question)).split()
        if len(token) > 1
    ]


def _content_query_terms(question: str) -> list[str]:
    return [term for term in _query_terms(question) if term not in GENERIC_QUERY_TERMS]


def _source_family(source: dict[str, Any]) -> str:
    value = source.get("source_family") or source.get("source_type")
    return value if isinstance(value, str) else ""


def _has_client_memory_source(sources: list[dict[str, Any]]) -> bool:
    return any(_source_family(source) in CLIENT_MEMORY_FAMILIES for source in sources)


def _has_source_family_metadata(sources: list[dict[str, Any]]) -> bool:
    return any(bool(_source_family(source)) for source in sources)


def _source_match_terms(source: dict[str, Any]) -> tuple[str, ...] | None:
    value = source.get("match_terms")
    if not isinstance(value, (list, tuple)):
        return None
    return tuple(term for term in value if isinstance(term, str))


def _generic_query_low_signal(
    question: str,
    sources: list[dict[str, Any]],
    current_focus: bool,
) -> bool:
    if current_focus or _content_query_terms(question):
        return False
    metadata_match_terms = [
        match_terms for match_terms in (_source_match_terms(source) for source in sources) if match_terms is not None
    ]
    if not metadata_match_terms:
        return False
    return not any(term not in GENERIC_QUERY_TERMS for match_terms in metadata_match_terms for term in match_terms)


def _low_relevance_context(question: str, sources: list[dict[str, Any]]) -> bool:
    """True when the question has several content terms but no source matches more than one.

    Catches confident-looking packs assembled from marginal single-term matches
    (e.g. a competitor-research note surfacing for a health-goals question).
    Single- and zero-content-term questions are excluded — coverage is not
    meaningful there and the generic-query flag already covers the latter.
    """
    content_terms = _content_query_terms(question)
    if len(content_terms) < 2:
        return False
    match_lists = [
        match_terms for match_terms in (_source_match_terms(source) for source in sources) if match_terms is not None
    ]
    if not match_lists:
        return False
    best = max(len([term for term in match_terms if term not in GENERIC_QUERY_TERMS]) for match_terms in match_lists)
    return best <= 1


def _source_is_fresh(source: dict[str, Any], today: date, stale_after_days: int) -> bool:
    stale = source.get("stale")
    if stale is False:
        return True
    if stale is True:
        return False
    source_date = _source_effective_date(source)
    return source_date is not None and (today - source_date).days <= stale_after_days


def _dedupe_flags(flags: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for flag in flags:
        if flag in seen:
            continue
        seen.add(flag)
        deduped.append(flag)
    return deduped


def assess_context_support(
    question: str,
    sources: list[dict[str, Any]],
    *,
    current_date: str | None = None,
    min_sources: int = 2,
    min_total_chars: int = 400,
    stale_after_days: int = 365,
) -> AskContextAssessment:
    # Guard against malformed source lists (None / non-dict entries) so a bad
    # retrieval payload degrades to weak-context instead of crashing the gate.
    sources = [source for source in sources if isinstance(source, dict)]
    current_focus = _is_current_focus_question(question)
    flags: list[str] = []
    usable_sources = [source for source in sources if _source_text(source)]
    usable_texts = [_source_text(source) for source in usable_sources]
    total_chars = sum(len(text) for text in usable_texts)

    if not usable_texts:
        flags.append("no-sources")
    if len(usable_texts) < min_sources:
        flags.append("too-few-sources")
    if total_chars < min_total_chars:
        flags.append("low-context-volume")

    if current_date is None:
        today = datetime.now(timezone.utc).date()
    else:
        today = date.fromisoformat(current_date)

    # Freshness is only evaluated when source date metadata exists.
    date_sources = [source for source in sources if not (current_focus and source.get("stale") is False)]
    dated_sources = [
        source_date
        for source_date in (_source_effective_date(source) for source in date_sources)
        if source_date is not None
    ]
    if dated_sources and any((today - item).days > stale_after_days for item in dated_sources):
        flags.append("stale-sources")

    if current_focus:
        if not any(_source_is_fresh(source, today, stale_after_days) for source in usable_sources):
            flags.append("no-fresh-sources")
        if usable_sources and usable_sources[0].get("stale") is True:
            flags.append("stale-primary-source")
        if _has_source_family_metadata(usable_sources) and not _has_client_memory_source(usable_sources):
            flags.append("client-memory-unavailable")
    if _generic_query_low_signal(question, usable_sources, current_focus):
        flags.append("generic-query-low-signal")
    if _low_relevance_context(question, usable_sources):
        flags.append("low-relevance-context")

    flags = _dedupe_flags(flags)
    supported = not flags
    return AskContextAssessment(
        supported=supported,
        answer_mode="supported" if supported else "weak-context",
        flags=flags,
        source_count=len(usable_texts),
        total_chars=total_chars,
    )

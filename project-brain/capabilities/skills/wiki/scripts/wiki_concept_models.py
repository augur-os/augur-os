from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _require_text(data: dict[str, Any], key: str) -> str:
    if key not in data:
        raise ValueError(f"Missing required field: {key}")
    value = data[key]
    if not isinstance(value, str):
        raise ValueError(f"Field {key} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"Field {key} must be a non-empty string")
    return text


def _require_list(data: dict[str, Any], key: str) -> list[Any]:
    if key not in data:
        raise ValueError(f"Missing required field: {key}")
    value = data[key]
    if not isinstance(value, list):
        raise ValueError(f"Field {key} must be a list")
    return value


def _optional_list_of_text(data: dict[str, Any], key: str) -> list[str]:
    if key not in data or data[key] is None:
        return []
    value = data[key]
    if not isinstance(value, list):
        raise ValueError(f"Field {key} must be a list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"Field {key} items must be strings")
        result.append(item)
    return result


def _optional_text(data: dict[str, Any], key: str) -> str:
    if key not in data or data[key] is None:
        return ""
    value = data[key]
    if not isinstance(value, str):
        raise ValueError(f"Field {key} must be a string")
    return value.strip()


@dataclass(frozen=True)
class SourceDescriptor:
    source_id: str
    kind: str
    title: str
    source_path: str
    checksum: str
    modified_at: str | None = None
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "kind": self.kind,
            "title": self.title,
            "source_path": self.source_path,
            "checksum": self.checksum,
            "modified_at": self.modified_at,
            "priority": self.priority,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceDescriptor:
        return cls(
            source_id=_require_text(data, "source_id"),
            kind=_require_text(data, "kind"),
            title=_require_text(data, "title"),
            source_path=_require_text(data, "source_path"),
            checksum=_require_text(data, "checksum"),
            modified_at=data.get("modified_at"),
            priority=int(data["priority"]) if "priority" in data and data["priority"] is not None else 0,
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class ConceptEvidence:
    source_id: str
    quote: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "quote": self.quote,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConceptEvidence:
        return cls(
            source_id=_require_text(data, "source_id"),
            quote=_require_text(data, "quote"),
            note=data.get("note", ""),
        )


@dataclass(frozen=True)
class ExtractedQuery:
    title: str
    slug: str
    summary: str
    answer: str
    evidence: list[ConceptEvidence] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "slug": self.slug,
            "summary": self.summary,
            "answer": self.answer,
            "evidence": [item.to_dict() for item in self.evidence],
            "source_ids": list(self.source_ids),
            "related": list(self.related),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedQuery:
        raw_evidence = data.get("evidence", [])
        if raw_evidence is None:
            raw_evidence = []
        if not isinstance(raw_evidence, list):
            raise ValueError("Field evidence must be a list")
        return cls(
            title=_require_text(data, "title"),
            slug=_require_text(data, "slug"),
            summary=_require_text(data, "summary"),
            answer=_require_text(data, "answer"),
            evidence=[
                item if isinstance(item, ConceptEvidence) else ConceptEvidence.from_dict(item)
                for item in raw_evidence
            ],
            source_ids=_optional_list_of_text(data, "source_ids"),
            related=_optional_list_of_text(data, "related"),
        )


@dataclass(frozen=True)
class ConceptArticle:
    core_thesis: str = ""
    source_synthesis: str = ""
    key_dimensions: list[str] = field(default_factory=list)
    recent_shifts: list[str] = field(default_factory=list)
    open_tensions: list[str] = field(default_factory=list)
    how_to_use: str = ""
    boundaries: str = ""
    open_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "core_thesis": self.core_thesis,
            "source_synthesis": self.source_synthesis,
            "key_dimensions": list(self.key_dimensions),
            "recent_shifts": list(self.recent_shifts),
            "open_tensions": list(self.open_tensions),
            "how_to_use": self.how_to_use,
            "boundaries": self.boundaries,
            "open_questions": list(self.open_questions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConceptArticle:
        return cls(
            core_thesis=_optional_text(data, "core_thesis"),
            source_synthesis=_optional_text(data, "source_synthesis"),
            key_dimensions=_optional_list_of_text(data, "key_dimensions"),
            recent_shifts=_optional_list_of_text(data, "recent_shifts"),
            open_tensions=_optional_list_of_text(data, "open_tensions"),
            how_to_use=_optional_text(data, "how_to_use"),
            boundaries=_optional_text(data, "boundaries"),
            open_questions=_optional_list_of_text(data, "open_questions"),
        )

    def is_empty(self) -> bool:
        return not (
            self.core_thesis
            or self.source_synthesis
            or self.key_dimensions
            or self.recent_shifts
            or self.open_tensions
            or self.how_to_use
            or self.boundaries
            or self.open_questions
        )


@dataclass(frozen=True)
class ExtractedConcept:
    title: str
    slug: str
    summary: str
    evidence: list[ConceptEvidence] = field(default_factory=list)
    confidence: float = 0.0
    aliases: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    queries: list[ExtractedQuery] = field(default_factory=list)
    article: ConceptArticle | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "slug": self.slug,
            "summary": self.summary,
            "evidence": [item.to_dict() for item in self.evidence],
            "confidence": self.confidence,
            "aliases": list(self.aliases),
            "related": list(self.related),
            "queries": [item.to_dict() for item in self.queries],
            "article": self.article.to_dict() if self.article is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedConcept:
        evidence_items = _optional_list_of_text(data, "aliases")  # type: ignore[assignment]
        related_items = _optional_list_of_text(data, "related")
        raw_evidence = data.get("evidence", [])
        if raw_evidence is None:
            raw_evidence = []
        if not isinstance(raw_evidence, list):
            raise ValueError("Field evidence must be a list")
        raw_queries = data.get("queries", [])
        if raw_queries is None:
            raw_queries = []
        if not isinstance(raw_queries, list):
            raise ValueError("Field queries must be a list")
        raw_article = data.get("article")
        if raw_article is not None and not isinstance(raw_article, dict):
            raise ValueError("Field article must be an object")
        return cls(
            title=_require_text(data, "title"),
            slug=_require_text(data, "slug"),
            summary=_require_text(data, "summary"),
            evidence=[
                item if isinstance(item, ConceptEvidence) else ConceptEvidence.from_dict(item)
                for item in raw_evidence
            ],
            confidence=float(data["confidence"]) if "confidence" in data and data["confidence"] is not None else 0.0,
            aliases=evidence_items,
            related=related_items,
            queries=[
                item if isinstance(item, ExtractedQuery) else ExtractedQuery.from_dict(item)
                for item in raw_queries
            ],
            article=ConceptArticle.from_dict(raw_article)
            if isinstance(raw_article, dict)
            else None,
        )

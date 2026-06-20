from __future__ import annotations

from dataclasses import dataclass, field
import re

from skills.wiki.scripts.wiki_concept_models import (
    ConceptArticle,
    ConceptEvidence,
    ExtractedConcept,
    ExtractedQuery,
)


@dataclass(frozen=True)
class MergedConcept:
    slug: str
    title: str
    summary: str
    source_ids: list[str] = field(default_factory=list)
    evidence: list[ConceptEvidence] = field(default_factory=list)
    confidence: float = 0.0
    aliases: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    queries: list[ExtractedQuery] = field(default_factory=list)
    article: ConceptArticle | None = None


def merge_extracted_concepts(concepts: list[ExtractedConcept]) -> list[MergedConcept]:
    if not concepts:
        return []

    parent = list(range(len(concepts)))
    identity_owner: dict[str, int] = {}

    for index, concept in enumerate(concepts):
        for key in _identity_keys(concept):
            owner = identity_owner.get(key)
            if owner is None:
                identity_owner[key] = index
                continue
            _union(parent, owner, index)

    for left_index, left in enumerate(concepts):
        for right_index in range(left_index + 1, len(concepts)):
            if _are_near_duplicate_concepts(left, concepts[right_index]):
                _union(parent, left_index, right_index)

    groups: dict[int, list[ExtractedConcept]] = {}
    for index, concept in enumerate(concepts):
        root = _find(parent, index)
        groups.setdefault(root, []).append(concept)

    merged = [_merge_group(group) for group in groups.values()]
    return sorted(merged, key=lambda concept: concept.slug)


def _merge_group(concepts: list[ExtractedConcept]) -> MergedConcept:
    canonical = min(
        concepts,
        key=lambda concept: (
            -concept.confidence,
            _normalize_identity(concept.slug),
            _normalize_identity(concept.title),
            concept.slug,
            concept.title,
        ),
    )

    evidence = _merged_evidence(concepts)
    source_ids = sorted({item.source_id for item in evidence})
    excluded_aliases = {
        _normalize_identity(canonical.title),
        _normalize_identity(canonical.slug),
    }

    return MergedConcept(
        slug=_safe_slug(canonical.slug, canonical.title),
        title=canonical.title,
        summary=canonical.summary,
        source_ids=source_ids,
        evidence=evidence,
        confidence=max(concept.confidence for concept in concepts),
        aliases=_sorted_unique_text(
            [
                value
                for concept in concepts
                for value in [concept.title, *concept.aliases]
                if _normalize_identity(value) not in excluded_aliases
            ]
        ),
        related=_sorted_unique_text([value for concept in concepts for value in concept.related]),
        queries=_merged_queries(concepts, canonical_slug=_safe_slug(canonical.slug, canonical.title)),
        article=_merged_article(concepts, canonical=canonical),
    )


def _identity_keys(concept: ExtractedConcept) -> set[str]:
    return {
        key
        for key in [
            _normalize_identity(concept.slug),
            _normalize_identity(concept.title),
            *[_normalize_identity(alias) for alias in concept.aliases],
        ]
        if key
    }


def _are_near_duplicate_concepts(left: ExtractedConcept, right: ExtractedConcept) -> bool:
    left_tokens = _concept_identity_tokens(left)
    right_tokens = _concept_identity_tokens(right)
    if len(left_tokens) < 3 or len(right_tokens) < 3:
        return False
    overlap = left_tokens & right_tokens
    if len(overlap) < 3:
        return False
    return len(overlap) / len(left_tokens | right_tokens) >= 0.67


def _concept_identity_tokens(concept: ExtractedConcept) -> set[str]:
    text = " ".join([concept.title, concept.slug, *concept.aliases])
    stopwords = {
        "and",
        "for",
        "from",
        "how",
        "into",
        "the",
        "this",
        "that",
        "with",
    }
    return {
        token
        for token in re.split(r"[^a-z0-9]+", text.lower())
        if len(token) >= 3 and token not in stopwords
    }


def _normalize_identity(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", value.strip().lower())
    return " ".join(text.split())


def _safe_slug(slug: str, title: str) -> str:
    for value in (slug, title):
        normalized = _normalize_identity(value)
        if normalized:
            return normalized.replace(" ", "-")
    return "concept"


def _merged_evidence(concepts: list[ExtractedConcept]) -> list[ConceptEvidence]:
    by_key: dict[tuple[str, str, str], ConceptEvidence] = {}
    for concept in concepts:
        for item in concept.evidence:
            by_key.setdefault((item.source_id, item.quote, item.note), item)
    return [by_key[key] for key in sorted(by_key)]


def _merged_queries(concepts: list[ExtractedConcept], *, canonical_slug: str) -> list[ExtractedQuery]:
    by_slug: dict[str, ExtractedQuery] = {}
    for concept in concepts:
        for query in concept.queries:
            slug = _safe_slug(query.slug, query.title)
            evidence = query.evidence or concept.evidence
            source_ids = query.source_ids or sorted({item.source_id for item in evidence})
            related = _sorted_unique_text([canonical_slug, *query.related])
            normalized_query = ExtractedQuery(
                title=query.title,
                slug=slug,
                summary=query.summary,
                answer=query.answer,
                evidence=evidence,
                source_ids=source_ids,
                related=related,
            )
            existing = by_slug.get(slug)
            if existing is None or query.title < existing.title:
                by_slug[slug] = normalized_query
    return [by_slug[key] for key in sorted(by_slug)]


def _merged_article(concepts: list[ExtractedConcept], *, canonical: ExtractedConcept) -> ConceptArticle | None:
    ordered = sorted(
        concepts,
        key=lambda concept: (
            0 if concept is canonical else 1,
            -concept.confidence,
            _normalize_identity(concept.slug),
            _normalize_identity(concept.title),
        ),
    )
    articles = [
        concept.article
        for concept in ordered
        if concept.article is not None and not concept.article.is_empty()
    ]
    if not articles:
        return None

    article = ConceptArticle(
        core_thesis=_first_article_value(articles, "core_thesis"),
        source_synthesis=_compound_article_value(articles, "source_synthesis"),
        key_dimensions=_merged_article_list(articles, "key_dimensions"),
        recent_shifts=_merged_article_list(articles, "recent_shifts"),
        open_tensions=_merged_article_list(articles, "open_tensions"),
        how_to_use=_first_article_value(articles, "how_to_use"),
        boundaries=_merged_boundaries(concepts=concepts, articles=articles),
        open_questions=_sorted_unique_text(
            [question for item in articles for question in item.open_questions]
        ),
    )
    return None if article.is_empty() else article


def _first_article_value(articles: list[ConceptArticle], field_name: str) -> str:
    for article in articles:
        value = getattr(article, field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _compound_article_value(articles: list[ConceptArticle], field_name: str) -> str:
    values = _sorted_unique_text(
        [
            getattr(article, field_name)
            for article in articles
            if isinstance(getattr(article, field_name), str)
        ]
    )
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return " ".join(_as_sentence(value) for value in values[:4])


def _merged_article_list(articles: list[ConceptArticle], field_name: str) -> list[str]:
    values: list[str] = []
    for article in articles:
        raw_values = getattr(article, field_name)
        if not isinstance(raw_values, list):
            continue
        values.extend(str(value) for value in raw_values)
    return _sorted_unique_text(values)


def _merged_boundaries(*, concepts: list[ExtractedConcept], articles: list[ConceptArticle]) -> str:
    values = _sorted_unique_text(
        [article.boundaries for article in articles if article.boundaries.strip()]
    )
    if not values:
        return ""
    if len(values) == 1:
        return values[0]

    generated_values = [
        value
        for value in values
        if "This synthesis is bounded by" in value
        and "not a replacement for reviewing the underlying source" in value
    ]
    if len(generated_values) == len(values):
        source_ids = sorted(
            {
                item.source_id
                for concept in concepts
                for item in concept.evidence
                if item.source_id.strip()
            }
        )
        kinds = sorted({source_id.split(":", 1)[0] for source_id in source_ids if ":" in source_id})
        source_text = f"{len(source_ids)} source-specific extraction"
        if len(source_ids) != 1:
            source_text += "s"
        if kinds:
            source_text += f" across {', '.join(kinds)} material"
        return (
            f"This synthesis draws on {source_text}. "
            "Treat it as the current source-backed reading, not a replacement for reviewing the underlying sources "
            "when precision, dates, or source nuance matter."
        )

    return " ".join(_as_sentence(value) for value in values[:4])


def _as_sentence(value: str) -> str:
    text = " ".join(value.split())
    if not text:
        return ""
    return text if text[-1] in ".?!" else f"{text}."


def _sorted_unique_text(values: list[str]) -> list[str]:
    by_key: dict[str, str] = {}
    for value in values:
        text = value.strip()
        if not text:
            continue
        key = _normalize_identity(text)
        if not key:
            continue
        existing = by_key.get(key)
        if existing is None or text < existing:
            by_key[key] = text
    return [by_key[key] for key in sorted(by_key)]


def _find(parent: list[int], index: int) -> int:
    while parent[index] != index:
        parent[index] = parent[parent[index]]
        index = parent[index]
    return index


def _union(parent: list[int], left: int, right: int) -> None:
    left_root = _find(parent, left)
    right_root = _find(parent, right)
    if left_root == right_root:
        return
    if right_root < left_root:
        left_root, right_root = right_root, left_root
    parent[right_root] = left_root

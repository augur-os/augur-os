from __future__ import annotations

import math
from numbers import Real
import re
from typing import Any

from skills.wiki.scripts.wiki_concept_models import (
    ConceptArticle,
    ConceptEvidence,
    ExtractedConcept,
    ExtractedQuery,
    SourceDescriptor,
)
from skills.wiki.scripts.wiki_compound_policy import (
    MIN_COMPOUND_SOURCE_COUNT,
    TARGET_COMPOUND_SOURCE_MAX,
    target_source_count_label,
)


class ExtractionPayloadError(ValueError):
    """Raised when concept extraction output does not match the required schema."""


def build_extraction_prompt(source: SourceDescriptor, body: str, *, cluster_context: str = "") -> str:
    cluster_lines = [
        "",
        "Related source cluster:",
        cluster_context,
    ] if cluster_context.strip() else []
    grounding_lines = _grounding_guidance(source, body)

    return "\n".join(
        [
            "Extract 1-3 durable concepts from narrow sources, or 3-8 from meaningfully dense sources; use 0 when the source has no durable wiki value.",
            "Do not summarize the source as a page.",
            "Perform a deep editorial review before writing JSON: identify durable claims, internal dimensions, recent shifts, tensions, and adjacent concepts.",
            "The goal is a compiled wiki article whose future questions can use the page as an answer source without re-reading the raw document.",
            f"Target source density: {target_source_count_label()} sources per published concept page.",
            f"Treat concepts backed by fewer than {MIN_COMPOUND_SOURCE_COUNT} sources as draft or pending cluster material.",
            f"Split concepts backed by more than {TARGET_COMPOUND_SOURCE_MAX} sources into narrower 8-15 source concepts before publication.",
            "Prefer strengthening an existing/cluster-backed concept over proposing a new thin page.",
            "Each summary must be 2-4 sentences explaining what the concept means, when to use it, and why it matters.",
            "Each concept must include an article object for human-readable wiki prose.",
            "The article object should include core_thesis, source_synthesis, key_dimensions, recent_shifts, open_tensions, how_to_use, boundaries, and open_questions.",
            "Use key_dimensions for named subtopics, workflow parts, operating constraints, or conceptual axes found in the source.",
            "Use recent_shifts for what changed, what the source newly clarifies, or why this source should deepen the existing wiki.",
            "Use open_tensions for tradeoffs, contradictions, unresolved decisions, or competing framings.",
            "Write article fields as synthesized prose from the source, not a source inventory or bullet summary.",
            "Return only a JSON array. Each item must include title, slug, summary, confidence, and evidence.",
            "A concept may include a queries array for reusable question pages; each query needs title, slug, summary, and answer.",
            "Confidence must be a number from 0 to 1.",
            "Evidence must be a non-empty array of objects with quote, optional note, and optional source_id.",
            "Reject evidence that is only frontmatter, labels, descriptions, ADR titles, YAML keys, or large metadata blobs.",
            "Evidence quotes must be concise body claims, not copied metadata.",
            *grounding_lines,
            "",
            f"Source ID: {source.source_id}",
            f"Kind: {source.kind}",
            f"Title: {source.title}",
            f"Path: {source.source_path}",
            *cluster_lines,
            "",
            "Source body:",
            body,
        ]
    )


def _grounding_guidance(source: SourceDescriptor, body: str) -> list[str]:
    lines = [
        "Stay grounded in the literal domain of the source.",
        "Prefer titles, summaries, and article prose that use concrete nouns a user would recognize from the source path, title, and body.",
        "Do not inflate practical notes into strategy language, management metaphors, or grand abstractions unless the source cluster explicitly supports that level.",
    ]
    if _looks_like_recipe_source(source, body):
        lines.extend(
            [
                "For recipe, meal-planning, and cooking notes: keep concepts concrete and food-oriented.",
                "Prefer recipe collection, meal ideas, cooking notes, meal rotation, named dishes, or appliance-specific cooking over abstract household-systems language.",
                "If a tool or appliance is central, name it directly, such as Ninja Grill.",
                'Do not turn recipes, ingredients, or instructions into an "operating system", "playbook", "framework", or generic home-operations concept unless the source explicitly says that.',
            ]
        )
    return lines


def _looks_like_recipe_source(source: SourceDescriptor, body: str) -> bool:
    metadata_values = " ".join(str(value) for value in source.metadata.values())
    haystack = " ".join(
        [
            source.source_id,
            source.title,
            source.source_path,
            metadata_values,
            body[:2000],
        ]
    ).lower()
    recipe_markers = (
        "/recipes/",
        "recipe-manager",
        "## ingredients",
        "## instructions",
        "ninja grill",
        "type: ninja",
        "type: breakfast",
    )
    return any(marker in haystack for marker in recipe_markers)


def parse_extraction_payload(source_id: str, payload: list[dict[str, Any]]) -> list[ExtractedConcept]:
    if not isinstance(payload, list):
        raise ExtractionPayloadError("Extraction payload must be a list of concept objects")

    concepts: list[ExtractedConcept] = []
    for concept_index, raw_concept in enumerate(payload):
        if not isinstance(raw_concept, dict):
            raise ExtractionPayloadError(f"Concept at index {concept_index} must be an object")

        concepts.append(_parse_concept(source_id, raw_concept, concept_index))

    return concepts


def _parse_concept(source_id: str, raw_concept: dict[str, Any], concept_index: int) -> ExtractedConcept:
    confidence = _require_confidence(raw_concept, concept_index)
    evidence = _require_evidence(source_id, raw_concept, concept_index)

    return ExtractedConcept(
        title=_require_text(raw_concept, "title", f"concept[{concept_index}]"),
        slug=_require_text(raw_concept, "slug", f"concept[{concept_index}]"),
        summary=_require_text(raw_concept, "summary", f"concept[{concept_index}]"),
        evidence=evidence,
        confidence=confidence,
        aliases=_optional_text_list(raw_concept, "aliases", f"concept[{concept_index}]"),
        related=_optional_text_list(raw_concept, "related", f"concept[{concept_index}]"),
        queries=_optional_queries(source_id, raw_concept, evidence, concept_index),
        article=_optional_article(raw_concept, concept_index),
    )


def _require_confidence(raw_concept: dict[str, Any], concept_index: int) -> float:
    if "confidence" not in raw_concept:
        raise ExtractionPayloadError(f"concept[{concept_index}].confidence is required")

    value = raw_concept["confidence"]
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ExtractionPayloadError(f"concept[{concept_index}].confidence must be numeric")

    confidence = float(value)
    if not math.isfinite(confidence):
        raise ExtractionPayloadError(f"concept[{concept_index}].confidence must be finite")
    if confidence < 0.0 or confidence > 1.0:
        raise ExtractionPayloadError(f"concept[{concept_index}].confidence must be between 0 and 1")
    return confidence


def _require_evidence(
    default_source_id: str,
    raw_concept: dict[str, Any],
    concept_index: int,
) -> list[ConceptEvidence]:
    if "evidence" not in raw_concept:
        raise ExtractionPayloadError(f"concept[{concept_index}].evidence is required")

    raw_evidence = raw_concept["evidence"]
    if not isinstance(raw_evidence, list) or not raw_evidence:
        raise ExtractionPayloadError(f"concept[{concept_index}].evidence must be a non-empty list")

    evidence: list[ConceptEvidence] = []
    for evidence_index, item in enumerate(raw_evidence):
        location = f"concept[{concept_index}].evidence[{evidence_index}]"
        if not isinstance(item, dict):
            raise ExtractionPayloadError(f"{location} must be an object")

        item_source_id = item.get("source_id", default_source_id)
        if not isinstance(item_source_id, str) or not item_source_id.strip():
            raise ExtractionPayloadError(f"{location}.source_id must be a non-empty string")

        quote = _require_text(item, "quote", location)
        if _is_rejected_evidence_quote(quote):
            raise ExtractionPayloadError(f"{location}.evidence quote is metadata or title-only text")

        evidence.append(
            ConceptEvidence(
                source_id=item_source_id.strip(),
                quote=quote,
                note=_optional_text(item, "note", location),
            )
        )

    return evidence


def _is_rejected_evidence_quote(quote: str) -> bool:
    text = " ".join(quote.strip().split())
    lowered = text.lower()
    if text in {"---", "..."}:
        return True
    if len(text) > 320:
        return True
    if re_match := re.match(
        r"^(label|description|title|tags|type|name|status|dispatch|action|x-augur-[a-z0-9_-]+):\s+",
        lowered,
    ):
        return bool(re_match)
    if re.match(r"^adr-\d{3,}:\s+[^.?!]{1,120}$", text, flags=re.IGNORECASE):
        return True
    if " extracted from " in lowered:
        return True
    return False


def _require_text(data: dict[str, Any], key: str, location: str) -> str:
    if key not in data:
        raise ExtractionPayloadError(f"{location}.{key} is required")

    value = data[key]
    if not isinstance(value, str):
        raise ExtractionPayloadError(f"{location}.{key} must be a string")

    text = value.strip()
    if not text:
        raise ExtractionPayloadError(f"{location}.{key} must be a non-empty string")
    return text


def _optional_text(data: dict[str, Any], key: str, location: str) -> str:
    if key not in data or data[key] is None:
        return ""

    value = data[key]
    if not isinstance(value, str):
        raise ExtractionPayloadError(f"{location}.{key} must be a string")
    return value.strip()


def _optional_text_list(data: dict[str, Any], key: str, location: str) -> list[str]:
    if key not in data or data[key] is None:
        return []

    value = data[key]
    if not isinstance(value, list):
        raise ExtractionPayloadError(f"{location}.{key} must be a list")

    result: list[str] = []
    for item_index, item in enumerate(value):
        if not isinstance(item, str):
            raise ExtractionPayloadError(f"{location}.{key}[{item_index}] must be a string")
        text = item.strip()
        if text:
            result.append(text)
    return result


def _optional_queries(
    source_id: str,
    raw_concept: dict[str, Any],
    fallback_evidence: list[ConceptEvidence],
    concept_index: int,
) -> list[ExtractedQuery]:
    if "queries" not in raw_concept or raw_concept["queries"] is None:
        return []

    raw_queries = raw_concept["queries"]
    if not isinstance(raw_queries, list):
        raise ExtractionPayloadError(f"concept[{concept_index}].queries must be a list")

    queries: list[ExtractedQuery] = []
    for query_index, raw_query in enumerate(raw_queries):
        location = f"concept[{concept_index}].queries[{query_index}]"
        if not isinstance(raw_query, dict):
            raise ExtractionPayloadError(f"{location} must be an object")
        evidence = _optional_evidence(source_id, raw_query, location, fallback_evidence)
        source_ids = sorted({item.source_id for item in evidence})
        queries.append(
            ExtractedQuery(
                title=_require_text(raw_query, "title", location),
                slug=_require_text(raw_query, "slug", location),
                summary=_require_text(raw_query, "summary", location),
                answer=_require_text(raw_query, "answer", location),
                evidence=evidence,
                source_ids=source_ids,
                related=_optional_text_list(raw_query, "related", location),
            )
        )
    return queries


def _optional_article(raw_concept: dict[str, Any], concept_index: int) -> ConceptArticle | None:
    if "article" not in raw_concept or raw_concept["article"] is None:
        return None

    raw_article = raw_concept["article"]
    location = f"concept[{concept_index}].article"
    if not isinstance(raw_article, dict):
        raise ExtractionPayloadError(f"{location} must be an object")

    article = ConceptArticle(
        core_thesis=_optional_text(raw_article, "core_thesis", location),
        source_synthesis=_optional_text(raw_article, "source_synthesis", location),
        key_dimensions=_optional_text_list(raw_article, "key_dimensions", location),
        recent_shifts=_optional_text_list(raw_article, "recent_shifts", location),
        open_tensions=_optional_text_list(raw_article, "open_tensions", location),
        how_to_use=_optional_text(raw_article, "how_to_use", location),
        boundaries=_optional_text(raw_article, "boundaries", location),
        open_questions=_optional_text_list(raw_article, "open_questions", location),
    )
    return None if article.is_empty() else article


def _optional_evidence(
    default_source_id: str,
    data: dict[str, Any],
    location: str,
    fallback_evidence: list[ConceptEvidence],
) -> list[ConceptEvidence]:
    if "evidence" not in data or data["evidence"] is None:
        return list(fallback_evidence)

    raw_evidence = data["evidence"]
    if not isinstance(raw_evidence, list) or not raw_evidence:
        raise ExtractionPayloadError(f"{location}.evidence must be a non-empty list")

    evidence: list[ConceptEvidence] = []
    for evidence_index, item in enumerate(raw_evidence):
        evidence_location = f"{location}.evidence[{evidence_index}]"
        if not isinstance(item, dict):
            raise ExtractionPayloadError(f"{evidence_location} must be an object")
        item_source_id = item.get("source_id", default_source_id)
        if not isinstance(item_source_id, str) or not item_source_id.strip():
            raise ExtractionPayloadError(f"{evidence_location}.source_id must be a non-empty string")
        quote = _require_text(item, "quote", evidence_location)
        if _is_rejected_evidence_quote(quote):
            raise ExtractionPayloadError(f"{evidence_location}.evidence quote is metadata or title-only text")
        evidence.append(
            ConceptEvidence(
                source_id=item_source_id.strip(),
                quote=quote,
                note=_optional_text(item, "note", evidence_location),
            )
        )
    return evidence

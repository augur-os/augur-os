"""Shared wiki page quality heuristics for reporting and maintenance."""
from __future__ import annotations

import re
from typing import Any

from skills.wiki.scripts.wiki_schema import lint_penalties, page_schema, resolve_page_kind
from skills.wiki.scripts.wiki_timeline import extract_compiled_truth, validate_timeline_entries


_INVENTORY_MARKERS = (
    "This hub contains",
    "## Sources",
    "## Current State",
    "## Expected Content",
    "Format breakdown",
)
_PLACEHOLDER_DEEP_MARKERS = (
    "metadata-only seed page generated from scanned sources",
    "it should explain how those materials fit together in practice",
)
_CONTRADICTION_KIND_TAG = "contradiction"
_RAW_METADATA_EVIDENCE_PATTERN = re.compile(
    r"(^|\n)\s*-\s+`[^`]+`:\s+(label|description|title|tags|type|name|status|dispatch|action|x-augur-[a-z0-9_-]+):\s+",
    flags=re.IGNORECASE,
)
_ADR_TITLE_EVIDENCE_PATTERN = re.compile(
    r"(^|\n)\s*-\s+`[^`]+`:\s+ADR-\d{3,}:\s+[^.?!\n]{1,120}(\n|$)",
    flags=re.IGNORECASE,
)
_COMPILED_TRUTH_SOURCE_LINE_PATTERN = re.compile(
    r"(?m)^\s*(?:[-*]\s*)?(?:_at:\s*\S+\s+)?_source:\s*\S+"
)
_GENERIC_TAXONOMY_TAGS = {"wiki", "concept"}
_GENERATED_BOILERPLATE_MARKERS = (
    "This concept is currently supported by",
    "Treat it as durable wiki knowledge",
    "Use this page to connect implementation and maintenance decisions",
)
CONCEPT_DRAFT_SOURCE_THRESHOLD = 3
CONCEPT_CLUSTER_MIN_SOURCES = 8
CONCEPT_CLUSTER_MAX_SOURCES = 15
CONCEPT_MIN_SYNTHESIS_WORDS = 320
CONCEPT_MIN_SYNTHESIS_SECTION_WORDS = 45
_INDEX_LIKE_PROSE_MARKERS = (
    "use this page when future work needs the stable rule behind",
    "start from the thesis, then use the source notes",
    "not a replacement for reviewing the underlying source",
    "not a replacement for reviewing the underlying sources",
    "this synthesis draws on",
    "this synthesis is bounded by",
    "the available source support centers on one durable claim",
    "read against the thesis",
    "source-backed claim:",
    "this page needs a richer article extraction pass",
)
_UNSUPPORTED_ABSTRACTION_TERMS = (
    "operating system",
    "playbook",
    "framework",
    "repertoire",
)
_CONCRETE_USER_SOURCE_MARKERS = (
    "/recipes/",
    "recipe-manager",
    "/notes/lifestyle/apple/reminders/",
    "/health/",
    "sample-fitout-project/assets",
    "/_augur/video-studio/",
)


def _extract_section(body: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*$"
    match = re.search(pattern, body, flags=re.MULTILINE)
    if not match:
        return ""
    start = match.end()
    remainder = body[start:]
    next_heading = re.search(r"^## ", remainder, flags=re.MULTILINE)
    section = remainder[: next_heading.start()] if next_heading else remainder
    return section.strip()


def _has_heading(body: str, heading: str) -> bool:
    return bool(re.search(rf"^## {re.escape(heading)}\s*$", body, flags=re.MULTILINE))


def _has_placeholder_deep_content(body: str) -> bool:
    for heading in ("What This Hub Knows", "Current Thesis", "Current Reality", "Core Pattern"):
        section = _extract_section(body, heading).lower()
        if not section:
            continue
        if any(marker in section for marker in _PLACEHOLDER_DEEP_MARKERS):
            return True
    return False


def _has_generic_current_reality(body: str) -> bool:
    current_reality = (
        _extract_section(body, "What This Hub Knows")
        or _extract_section(body, "Current Reality")
    ).lower()
    return (
        "currently draws most of its working knowledge from" in current_reality
        and "it should explain how those materials fit together in practice" in current_reality
    ) or (
        "currently concentrates on" in current_reality
        and "it should explain how those strands fit together in practice" in current_reality
    )


def _has_generic_source_doctrine(body: str) -> bool:
    core_pattern = (
        _extract_section(body, "Current Thesis")
        or _extract_section(body, "Core Pattern")
    ).lower()
    return (
        _has_generic_current_reality(body)
        and (
            "materials into one practical operating model" in core_pattern
            or "this hub is strongest when it can turn" in core_pattern
            or "this hub is strongest when it can keep" in core_pattern
        )
    )


def _has_richer_article_debt(article_metadata: dict[str, Any] | None) -> bool:
    if not isinstance(article_metadata, dict):
        return False
    if article_metadata.get("needs_richer_article"):
        return True
    flags = article_metadata.get("quality_flags")
    return isinstance(flags, list) and "needs_richer_article" in {
        str(flag).strip() for flag in flags if str(flag).strip()
    }


def _normalized_tag_set(values: list[str] | None) -> set[str]:
    return {
        str(value).strip().lower()
        for value in values or []
        if str(value).strip()
    }


def _ask_outcome_matches_page(
    outcome: dict[str, Any],
    *,
    hub: str,
    tags: list[str],
) -> bool:
    outcome_hub = str(outcome.get("hub", "")).strip().lower()
    if outcome_hub and hub.strip().lower() == outcome_hub:
        return True

    outcome_tags = _normalized_tag_set(
        [str(tag) for tag in outcome.get("tags", []) if str(tag).strip()]
    )
    page_tags = _normalized_tag_set(tags)
    if outcome_tags & page_tags:
        return True

    return False


def _has_contradiction_pressure(
    *,
    hub: str,
    tags: list[str],
    ask_outcomes: list[dict[str, Any]] | None,
) -> bool:
    for outcome in ask_outcomes or []:
        kind = str(outcome.get("kind", "")).strip().lower()
        outcome_tags = _normalized_tag_set(
            [str(tag) for tag in outcome.get("tags", []) if str(tag).strip()]
        )
        if kind != _CONTRADICTION_KIND_TAG and _CONTRADICTION_KIND_TAG not in outcome_tags:
            continue
        if _ask_outcome_matches_page(outcome, hub=hub, tags=tags):
            return True
    return False


def _has_raw_metadata_evidence(body: str) -> bool:
    return bool(
        _RAW_METADATA_EVIDENCE_PATTERN.search(body)
        or _ADR_TITLE_EVIDENCE_PATTERN.search(body)
        or re.search(r"(^|\n)\s*-\s+`[^`]+`:\s+---\s*(\n|$)", body)
    )


def _source_physical_key(source: str) -> str:
    text = str(source).strip()
    if ":" in text:
        _kind, rest = text.split(":", 1)
        return rest.strip()
    return text


def _has_duplicate_physical_sources(sources: list[str]) -> bool:
    keys = [_source_physical_key(source) for source in sources if str(source).strip()]
    return len(keys) != len(set(keys))


def _has_legacy_client_source_path(sources: list[str], body: str) -> bool:
    values = [*sources, body]
    return any(".claude/skills" in value or "/.claude/plugins" in value for value in values)


def _has_generated_boilerplate(body: str) -> bool:
    return any(marker in body for marker in _GENERATED_BOILERPLATE_MARKERS)


def _evidence_bullet_count(body: str) -> int:
    evidence = _extract_section(body, "Evidence")
    return len(re.findall(r"(?m)^\s*-\s+`[^`]+`:", evidence))


def _source_notes_bullet_count(body: str) -> int:
    source_notes = _extract_section(body, "Source Notes") or _extract_section(body, "Source Basis")
    return len(re.findall(r"(?m)^\s*-\s+`[^`]+`:", source_notes))


def _unique_source_count(sources: list[str]) -> int:
    return len({str(source).strip() for source in sources if str(source).strip()})


def _has_concept_article_shape(body: str) -> bool:
    has_v3_shape = (
        _has_heading(body, "Current Thesis")
        and _has_heading(body, "What This Page Knows")
        and _has_heading(body, "Evidence")
        and _has_heading(body, "Source Basis")
    )
    has_v2_shape = (
        _has_heading(body, "Core Thesis")
        and _has_heading(body, "What the Sources Establish")
        and _has_heading(body, "Source Notes")
    )
    return has_v3_shape or has_v2_shape


def _is_index_shaped_page(*, page_kind: str, body: str) -> bool:
    if page_kind != "concept":
        return False
    has_old_card_shape = _has_heading(body, "Summary") and _has_heading(body, "Evidence")
    has_article_shape = _has_concept_article_shape(body)
    return has_old_card_shape and not has_article_shape


def _has_shallow_concept_synthesis(*, body: str, word_count: int) -> bool:
    if word_count < CONCEPT_MIN_SYNTHESIS_WORDS:
        return True
    synthesis = _extract_section(body, "What This Page Knows") or _extract_section(
        body,
        "What the Sources Establish",
    ) or extract_compiled_truth(body)
    if len(synthesis.split()) < CONCEPT_MIN_SYNTHESIS_SECTION_WORDS:
        return True
    return False


def _has_index_like_prose(body: str) -> bool:
    lowered = body.lower()
    if any(marker in lowered for marker in _INDEX_LIKE_PROSE_MARKERS):
        return True
    source_note_count = _source_notes_bullet_count(body)
    if source_note_count >= 3 and _has_heading(body, "What the Sources Establish"):
        return True
    return False


def _has_clipped_inline_code(body: str) -> bool:
    return body.count("`") % 2 == 1


def _contains_unsupported_domain_abstraction(*, sources: list[str], body: str) -> bool:
    lowered_sources = " ".join(str(source).strip().lower() for source in sources if str(source).strip())
    if not any(marker in lowered_sources for marker in _CONCRETE_USER_SOURCE_MARKERS):
        return False

    synthesized_sections = " ".join(
        section
        for section in (
            _extract_section(body, "Current Thesis"),
            _extract_section(body, "What This Page Knows"),
            _extract_section(body, "How to Use This"),
            _extract_section(body, "Summary"),
            _extract_section(body, "Answer"),
        )
        if section
    ).lower()
    if not synthesized_sections:
        return False

    evidence_sections = " ".join(
        section
        for section in (
            _extract_section(body, "Evidence"),
            _extract_section(body, "Source Basis"),
            _extract_section(body, "Source Notes"),
        )
        if section
    ).lower()

    return any(
        term in synthesized_sections and term not in evidence_sections
        for term in _UNSUPPORTED_ABSTRACTION_TERMS
    )


def _is_thin_page(
    *,
    page_kind: str,
    body: str,
    word_count: int,
    cross_ref_count: int,
    min_cross_links: int,
) -> bool:
    if word_count >= 120:
        return False
    if page_kind in {"concept", "query"}:
        if page_kind == "concept":
            has_article_shape = _has_concept_article_shape(body) and _source_notes_bullet_count(body) >= 1
            if has_article_shape:
                return False
        has_summary = bool(_extract_section(body, "Summary"))
        evidence_count = _evidence_bullet_count(body)
        has_evidence = evidence_count >= 2
        has_links = cross_ref_count >= min_cross_links
        has_strong_graph_context = evidence_count >= 1 and cross_ref_count >= 5
        if has_summary and has_evidence and has_links:
            return False
        if has_summary and has_strong_graph_context:
            return False
    return True


def _is_catch_all_page(*, sources: list[str], body: str, word_count: int) -> bool:
    evidence_count = len(re.findall(r"(?m)^\s*-\s+`", body))
    return len(sources) > 30 or evidence_count > 30 or (len(sources) > 20 and word_count > 1000)


def assess_page_quality(
    *,
    page: str,
    page_type: str | None = None,
    hub: str,
    tags: list[str],
    sources: list[str],
    body: str,
    cross_ref_count: int,
    compiler_version: str | None = None,
    article_metadata: dict[str, Any] | None = None,
    ask_outcomes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a simple quality score and flags for a wiki page."""
    flags: list[str] = []
    word_count = len(body.split())
    page_kind = resolve_page_kind(page=page, page_type=page_type)
    schema_entry = page_schema(page=page, page_type=page_type)
    is_overview = page_kind == "overview"
    inventory_markers = sum(1 for marker in _INVENTORY_MARKERS if marker in body)
    required_sections = [
        str(item).strip()
        for item in schema_entry.get("required_sections", [])
        if str(item).strip()
    ]
    min_tags = int(schema_entry.get("min_tags", 3 if not is_overview else 3) or 0)
    min_cross_links = int(schema_entry.get("min_cross_links", 2 if not is_overview else 3) or 0)
    unique_source_count = _unique_source_count(sources)

    if inventory_markers >= 2:
        flags.append("inventory_style")
    if _is_index_shaped_page(page_kind=page_kind, body=body):
        flags.append("index_shaped_page")
    if page_kind == "concept":
        if unique_source_count < CONCEPT_DRAFT_SOURCE_THRESHOLD:
            flags.append("draft_source_basis")
        elif unique_source_count < CONCEPT_CLUSTER_MIN_SOURCES:
            flags.append("pending_source_cluster")
        if unique_source_count < CONCEPT_CLUSTER_MIN_SOURCES:
            flags.append("below_cluster_source_floor")
        if unique_source_count > CONCEPT_CLUSTER_MAX_SOURCES:
            flags.append("overbroad_source_cluster")
        if _has_shallow_concept_synthesis(body=body, word_count=word_count):
            flags.append("shallow_synthesis")
        if _has_index_like_prose(body):
            flags.append("index_like_prose")
        if _has_clipped_inline_code(body):
            flags.append("clipped_evidence")
        timeline_validation = validate_timeline_entries(body)
        flags.extend(timeline_validation.errors)
        flags.extend(timeline_validation.warnings)
        if _has_compiled_truth_source_marker(body):
            flags.append("compiled_truth_contains_source_marker")
        if _is_legacy_concept_article_v3(compiler_version=compiler_version, body=body):
            flags.append("legacy_concept_article_v3")
    if _is_thin_page(
        page_kind=page_kind,
        body=body,
        word_count=word_count,
        cross_ref_count=cross_ref_count,
        min_cross_links=min_cross_links,
    ):
        flags.append("thin_page")
    if cross_ref_count < min_cross_links:
        flags.append("low_cross_links")
    if len(sources) == 0:
        flags.append("missing_sources")
    if _has_duplicate_physical_sources(sources):
        flags.append("duplicate_physical_sources")
    if len(tags) < min_tags:
        flags.append("weak_tag_coverage")
    if page_kind in {"concept", "query"} and _GENERIC_TAXONOMY_TAGS.intersection({tag.lower() for tag in tags}):
        flags.append("generic_taxonomy_tags")
    if _has_raw_metadata_evidence(body):
        flags.append("raw_metadata_evidence")
    if page_kind in {"concept", "query"} and _has_legacy_client_source_path(sources, body):
        flags.append("legacy_client_source_path")
    if page_kind in {"concept", "query"} and _has_generated_boilerplate(body):
        flags.append("generated_boilerplate_sections")
    if page_kind in {"concept", "query"} and _contains_unsupported_domain_abstraction(sources=sources, body=body):
        flags.append("unsupported_domain_abstraction")
    if _is_catch_all_page(sources=sources, body=body, word_count=word_count):
        flags.append("catch_all_page")
    if is_overview and cross_ref_count < min_cross_links:
        flags.append("weak_overview_navigation")
    if is_overview and hub and hub not in {tag.lower() for tag in tags}:
        flags.append("weak_hub_fit")
    if is_overview and "## Current Thesis" not in body and "## What This Wiki Knows" not in body:
        flags.append("non_synthetic_overview")
    if required_sections and any(f"## {heading}" not in body for heading in required_sections):
        if is_overview:
            flags.append("deep_structure_gap")
        else:
            flags.append("schema_required_sections_missing")
    if is_overview and _has_placeholder_deep_content(body):
        flags.append("deep_content_gap")
    if is_overview and _has_generic_current_reality(body):
        flags.append("generic_current_reality")
    if is_overview and _has_generic_source_doctrine(body):
        flags.append("generic_source_doctrine")
    if _has_richer_article_debt(article_metadata):
        flags.append("needs_richer_article")
    if _has_contradiction_pressure(hub=hub, tags=tags, ask_outcomes=ask_outcomes):
        flags.append("contradiction_pressure")

    penalties = lint_penalties()
    score = 100 - sum(int(penalties.get(flag, 0)) for flag in flags)
    return {
        "quality_score": max(score, 0),
        "quality_flags": flags,
        "page_kind": page_kind,
    }


def _is_legacy_concept_article_v3(*, compiler_version: str | None, body: str) -> bool:
    version = str(compiler_version or "").strip()
    return version == "concept-article-v3"


def _has_compiled_truth_source_marker(body: str) -> bool:
    return bool(_COMPILED_TRUTH_SOURCE_LINE_PATTERN.search(extract_compiled_truth(body)))

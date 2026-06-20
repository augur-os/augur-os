"""Write concept-first wiki pages."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
from typing import Any

from src.lib.frontmatter_utils import parse_frontmatter
from skills.wiki.scripts.wiki_concept_merge import MergedConcept
from skills.wiki.scripts.wiki_concept_models import (
    ConceptArticle,
    ConceptEvidence,
    ExtractedQuery,
    SourceDescriptor,
)
from skills.wiki.scripts.wiki_compound_policy import (
    MIN_COMPOUND_SOURCE_COUNT,
    is_compound_source_count,
)
from skills.wiki.scripts.wiki_pages import compute_source_fingerprint
from src.lib.frontmatter_utils import write_vault_frontmatter
from skills.wiki.scripts.wiki_timeline import (
    TimelineEntry,
    append_timeline_entries,
    extract_compiled_truth,
    extract_timeline,
)


CONCEPT_COMPILER_VERSION = "concept-article-v4"
QUERY_COMPILER_VERSION = "concept-article-v3"
MAX_EVIDENCE_ITEMS = 12
MAX_EVIDENCE_PER_SOURCE = 2
KNOWN_WIKI_HUBS = {"adaptive", "brain", "career", "command", "life", "studio"}
GENERIC_METADATA_TAGS = {
    "wiki",
    "concept",
    "page",
    "pages",
    "source",
    "sources",
    "general",
    "how",
    "should",
    "used",
    "use",
}
RAW_EVIDENCE_PREFIXES = (
    "description:",
    "label:",
    "name:",
    "status:",
    "tags:",
    "title:",
    "type:",
    "x-augur-",
    "---",
)
_TIMELINE_ENTRY_HEADER_RE = re.compile(r"^- _at: (?P<at>\S+)\s+_source: (?P<source>\S+)\s*$")


def write_concept_pages(
    wiki_dir: Path,
    concepts: list[MergedConcept],
    *,
    timestamp: str,
    sources_by_id: dict[str, SourceDescriptor] | None = None,
    filter_related_to_known_concepts: bool = False,
) -> list[Path]:
    """Write synthesized concept pages and return their paths."""
# TODO_CLEANUP: This file is 965 lines — consider splitting into smaller modules
    concepts_dir = wiki_dir / "concepts"
    written: list[Path] = []
    known_slugs = {_safe_page_slug(concept.slug) for concept in concepts}
    sources_by_id = sources_by_id or {}

    for concept in sorted(concepts, key=lambda item: item.slug):
        live_related = (
            _filtered_related_items(concept.related, known_slugs=known_slugs)
            if filter_related_to_known_concepts
            else list(concept.related)
        )
        renderable_concept = replace(concept, related=live_related)
        target = concepts_dir / f"{_safe_page_slug(concept.slug)}.md"
        existing_meta, existing_body = _existing_page(target)
        created = _existing_created(existing_meta, fallback=timestamp)
        hub = _metadata_hub(renderable_concept.source_ids, sources_by_id=sources_by_id)
        display_sources = _display_source_ids(renderable_concept.source_ids, sources_by_id=sources_by_id)

        metadata = {
            "title": renderable_concept.title,
            "page_type": "concept",
            "summary": _canonicalize_wikilinks(renderable_concept.summary, known_slugs=known_slugs),
            "hub": hub,
            "tags": _metadata_tags(renderable_concept.slug, renderable_concept.title, renderable_concept.related, hub=hub),
            "sources": display_sources,
            "aliases": list(renderable_concept.aliases),
            "related": _metadata_relationship_links(renderable_concept.related),
            "source_fingerprint": compute_source_fingerprint(display_sources),
            "created": created,
            "compiler_version": CONCEPT_COMPILER_VERSION,
        }
        body = _concept_body(
            renderable_concept,
            known_slugs=known_slugs,
            sources_by_id=sources_by_id,
            timestamp=timestamp,
            existing_meta=existing_meta,
            existing_body=existing_body,
        )
        if _write_frontmatter_if_changed(
            target,
            metadata,
            body,
            timestamp=timestamp,
            existing_meta=existing_meta,
            existing_body=existing_body,
        ):
            written.append(target)

            # ADR-738 — emit typed edges for the concept page just written.
            try:
                import sys as _sys
                _graph_scripts = str(
                    Path(__file__).resolve().parents[2] / "graph" / "scripts"
                )
                if _graph_scripts not in _sys.path:
                    _sys.path.insert(0, _graph_scripts)
                import graph_ops  # type: ignore[import-not-found]

                graph_ops.index_page_from_write_path(target, source_type="concept")
            except Exception:  # noqa: BLE001 — graph is best-effort, never breaks /wiki
                pass

    return written


def write_query_pages(
    wiki_dir: Path,
    concepts: list[MergedConcept],
    *,
    timestamp: str,
    include_default_queries: bool = False,
    sources_by_id: dict[str, SourceDescriptor] | None = None,
) -> list[Path]:
    """Write synthesized query pages from merged concept query specs."""
    queries_dir = wiki_dir / "queries"
    known_slugs = {_safe_page_slug(concept.slug) for concept in concepts}
    sources_by_id = sources_by_id or {}
    queries_by_slug: dict[str, ExtractedQuery] = {}
    for concept in concepts:
        queries = list(concept.queries)
        if include_default_queries:
            default_query = _default_query_for_concept(concept)
            if default_query is not None:
                queries.append(default_query)
        for query in queries:
            queries_by_slug.setdefault(_safe_page_slug(query.slug), query)

    written: list[Path] = []
    for slug in sorted(queries_by_slug):
        query = queries_by_slug[slug]
        renderable_query = replace(query, related=_filtered_related_items(query.related, known_slugs=known_slugs))
        target = queries_dir / f"{slug}.md"
        existing_meta, existing_body = _existing_page(target)
        created = _existing_created(existing_meta, fallback=timestamp)

        source_ids = renderable_query.source_ids or sorted({item.source_id for item in renderable_query.evidence})
        hub = _metadata_hub(source_ids, sources_by_id=sources_by_id)
        display_sources = _display_source_ids(source_ids, sources_by_id=sources_by_id)
        metadata = {
            "title": renderable_query.title,
            "page_type": "query",
            "summary": _canonicalize_wikilinks(renderable_query.summary, known_slugs=known_slugs),
            "hub": hub,
            "tags": _metadata_tags(renderable_query.slug, renderable_query.title, renderable_query.related, extra=["query"], hub=hub),
            "sources": display_sources,
            "related": _metadata_relationship_links(renderable_query.related),
            "source_fingerprint": compute_source_fingerprint(display_sources),
            "created": created,
            "compiler_version": QUERY_COMPILER_VERSION,
        }
        body = _query_body(renderable_query, known_slugs=known_slugs, sources_by_id=sources_by_id)
        if _write_frontmatter_if_changed(
            target,
            metadata,
            body,
            timestamp=timestamp,
            existing_meta=existing_meta,
            existing_body=existing_body,
        ):
            written.append(target)

    return written


def write_wiki_index(wiki_dir: Path, *, timestamp: str) -> Path:
    """Write compact root support pages and return the index path."""
    write_wiki_support_pages(wiki_dir, timestamp=timestamp)
    return wiki_dir / "index.md"


def write_wiki_support_pages(wiki_dir: Path, *, timestamp: str) -> list[Path]:
    """Write compact root support pages that link pages instead of source rows."""
    concept_entries = _page_entries(wiki_dir / "concepts")
    query_entries = _page_entries(wiki_dir / "queries")

    support_fingerprint_inputs = [
        f"concept:{title}:{path.as_posix()}" for title, path in concept_entries
    ] + [
        f"query:{title}:{path.as_posix()}" for title, path in query_entries
    ]
    metadata = {
        "title": "Wiki Index",
        "page_type": "overview",
        "concept_count": len(concept_entries),
        "source_fingerprint": compute_source_fingerprint(support_fingerprint_inputs),
    }
    if query_entries:
        metadata["query_count"] = len(query_entries)

    body = _index_body(concept_entries=concept_entries, query_entries=query_entries)
    target = wiki_dir / "index.md"
    written: list[Path] = []
    if _write_frontmatter_if_changed(target, metadata, body, timestamp=timestamp):
        written.append(target)

    overview_target = wiki_dir / "overview.md"
    if _write_frontmatter_if_changed(
        overview_target,
        {
            **metadata,
            "title": "Wiki Overview",
        },
        _overview_body(concept_entries=concept_entries, query_entries=query_entries),
        timestamp=timestamp,
    ):
        written.append(overview_target)
    return written


def _existing_page(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, ""
    return parse_frontmatter(path, include_sidecar_config=False)


def _existing_created(metadata: dict[str, Any], *, fallback: str) -> str:
    existing_created = str(metadata.get("created") or "").strip()
    return existing_created or fallback


def _metadata_relationship_links(items: list[str]) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for item in items:
        slug = _safe_page_slug(_candidate_concept_slug(item))
        if not slug or slug in seen:
            continue
        seen.add(slug)
        links.append(f"[[{slug}]]")
    return links


def _write_frontmatter_if_changed(
    target: Path,
    metadata_without_updated: dict[str, Any],
    body: str,
    *,
    timestamp: str,
    existing_meta: dict[str, Any] | None = None,
    existing_body: str | None = None,
) -> bool:
    """Write a page only when durable content changed.

    The compiler timestamp is a write marker, not source content. If the
    generated body and metadata are otherwise unchanged, preserve the existing
    updated timestamp and leave the file untouched.
    """
    if existing_meta is None or existing_body is None:
        existing_meta, existing_body = _existing_page(target)

    existing_updated = str(existing_meta.get("updated") or "").strip()
    if existing_updated:
        stable_metadata = {
            **metadata_without_updated,
            "updated": existing_updated,
        }
        if _frontmatter_view_matches(existing_meta, stable_metadata) and _normalized_generated_body(existing_body) == body:
            return False

    write_vault_frontmatter(
        target,
        {
            **metadata_without_updated,
            "updated": timestamp,
        },
        body,
    )
    return True


def _frontmatter_view_matches(existing_meta: dict[str, Any], expected_meta: dict[str, Any]) -> bool:
    """Compare generated fields through parse_frontmatter's migration aliases."""
    return all(existing_meta.get(key) == value for key, value in expected_meta.items())


def _normalized_generated_body(body: str) -> str:
    if body.startswith("\n#"):
        return body[1:]
    return body


def _concept_body(
    concept: MergedConcept,
    *,
    known_slugs: set[str],
    sources_by_id: dict[str, SourceDescriptor],
    timestamp: str,
    existing_meta: dict[str, Any],
    existing_body: str,
) -> str:
    selected_evidence = _selected_evidence(concept.evidence, sources_by_id=sources_by_id)
    timeline_entries = _timeline_entries_from_evidence(selected_evidence, timestamp=timestamp)
    if _is_existing_v4_concept(existing_meta, existing_body):
        return append_timeline_entries(
            existing_body,
            _new_timeline_entries(existing_body, timeline_entries),
        )

    article = concept.article
    core_thesis = _article_text(article, "core_thesis") or concept.summary
    source_synthesis = _article_text(article, "source_synthesis") or _source_synthesis_text(
        concept,
        selected_evidence,
    )
    key_dimensions = _article_list(article, "key_dimensions") or _fallback_key_dimensions(
        concept,
        selected_evidence,
        known_slugs=known_slugs,
    )
    recent_shifts = _article_list(article, "recent_shifts") or _fallback_recent_shifts(
        concept,
        selected_evidence,
    )
    how_to_use = _article_text(article, "how_to_use") or _how_to_use_text(
        concept,
        known_slugs=known_slugs,
    )
    boundaries = _article_text(article, "boundaries") or _boundaries_text(
        concept,
        selected_evidence,
    )
    open_tensions = _article_list(article, "open_tensions")
    open_questions = _article_open_questions(article)
    if not open_tensions:
        open_tensions = [boundaries]

    lines = [
        f"# {concept.title}",
        "",
        "## Compiled truth",
        "",
        "### Current Thesis",
        "",
        _canonicalize_wikilinks(core_thesis, known_slugs=known_slugs),
        "",
        "### What This Page Knows",
        "",
        _canonicalize_wikilinks(source_synthesis, known_slugs=known_slugs),
        "",
        "### Key Dimensions",
        "",
        *_bullet_lines(key_dimensions, known_slugs=known_slugs),
        "",
        "### Recent Shifts",
        "",
        *_bullet_lines(recent_shifts, known_slugs=known_slugs),
        "",
        "### Open Tensions",
        "",
        *_bullet_lines(open_tensions, known_slugs=known_slugs),
        "",
        "### How to Use This",
        "",
        _canonicalize_wikilinks(how_to_use, known_slugs=known_slugs),
        "",
    ]
    if open_questions:
        lines.extend(["### Open Questions", ""])
        lines.extend(f"- {_canonicalize_wikilinks(question, known_slugs=known_slugs)}" for question in open_questions)
        lines.append("")

    lines.extend(["### Source Basis", ""])
    if selected_evidence:
        for item in selected_evidence:
            note = f" {item.note}" if item.note else ""
            lines.append(f"- `{item.source_id}`: {item.quote}{note}")
    else:
        lines.append("- No evidence citations were available for this concept.")

    if concept.related:
        lines.extend(["", "### Related Concepts", ""])
        lines.extend(f"- {_related_item(item, known_slugs=known_slugs)}" for item in concept.related)

    body = "\n".join(lines).strip() + "\n\n## Timeline\n"
    return append_timeline_entries(body, timeline_entries)


def _is_existing_v4_concept(metadata: dict[str, Any], body: str) -> bool:
    return (
        str(metadata.get("page_type") or "").strip() == "concept"
        and str(metadata.get("compiler_version") or "").strip() == CONCEPT_COMPILER_VERSION
        and bool(extract_compiled_truth(body))
    )


def _new_timeline_entries(body: str, entries: list[TimelineEntry]) -> list[TimelineEntry]:
    existing = _timeline_entry_signatures(body)
    return [
        entry
        for entry in entries
        if _timeline_entry_signature(entry.source, entry.observation) not in existing
    ]


def _timeline_entry_signatures(body: str) -> set[tuple[str, str]]:
    signatures: set[tuple[str, str]] = set()
    at: str | None = None
    source: str | None = None
    observation_lines: list[str] = []
    for line in extract_timeline(body).splitlines():
        match = _TIMELINE_ENTRY_HEADER_RE.match(line)
        if match is not None:
            _add_valid_timeline_signature(signatures, at, source, observation_lines)
            at = match.group("at")
            source = match.group("source")
            observation_lines = []
            continue
        if line.startswith("- "):
            _add_valid_timeline_signature(signatures, at, source, observation_lines)
            at = None
            source = None
            observation_lines = []
            continue
        if source is not None and line.strip():
            observation_lines.append(line.strip())
    _add_valid_timeline_signature(signatures, at, source, observation_lines)
    return signatures


def _timeline_entry_signature(source: str, observation: str) -> tuple[str, str]:
    return (str(source).strip(), _canonicalize_timeline_observation(observation))


def _add_valid_timeline_signature(
    signatures: set[tuple[str, str]],
    at: str | None,
    source: str | None,
    observation_lines: list[str],
) -> None:
    if at is None or source is None:
        return
    observation = _canonicalize_timeline_observation(" ".join(observation_lines))
    try:
        TimelineEntry(at=at, source=source, observation=observation)
    except ValueError:
        return
    signatures.add(_timeline_entry_signature(source, observation))


def _timeline_entries_from_evidence(
    evidence: list[ConceptEvidence],
    *,
    timestamp: str,
) -> list[TimelineEntry]:
    entries: list[TimelineEntry] = []
    seen: set[tuple[str, str, str]] = set()
    for item in evidence:
        observation = _canonicalize_timeline_observation(_evidence_claim_text(item))
        if not observation:
            continue
        source = _timeline_source_uri(item.source_id)
        key = (timestamp, source, observation)
        if key in seen:
            continue
        seen.add(key)
        entries.append(TimelineEntry(at=timestamp, source=source, observation=observation))
    return entries


def _canonicalize_timeline_observation(value: str) -> str:
    return " ".join(str(value).split())


def _timeline_source_uri(source_id: str) -> str:
    source = str(source_id).strip()
    if "://" in source:
        return source
    return f"vault://{source}"


def _article_text(article: ConceptArticle | None, field_name: str) -> str:
    if article is None:
        return ""
    value = getattr(article, field_name)
    return value.strip() if isinstance(value, str) else ""


def _article_list(article: ConceptArticle | None, field_name: str) -> list[str]:
    if article is None:
        return []
    value = getattr(article, field_name)
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _article_open_questions(article: ConceptArticle | None) -> list[str]:
    if article is None:
        return []
    return [question.strip() for question in article.open_questions if question.strip()]


def _bullet_lines(items: list[str], *, known_slugs: set[str]) -> list[str]:
    if not items:
        return ["- This page needs a richer article extraction pass before this section can be named responsibly."]
    return [f"- {_canonicalize_wikilinks(item, known_slugs=known_slugs)}" for item in items]


def _fallback_key_dimensions(
    concept: MergedConcept,
    evidence: list[ConceptEvidence],
    *,
    known_slugs: set[str],
) -> list[str]:
    dimensions: list[str] = []
    for item in evidence[:2]:
        claim = _evidence_claim_text(item)
        if claim:
            dimensions.append(f"Source-backed claim: {claim}")
    for related in concept.related[:2]:
        linked = _related_item(related, known_slugs=known_slugs)
        dimensions.append(f"Related concept: {linked}")
    return dimensions


def _fallback_recent_shifts(concept: MergedConcept, evidence: list[ConceptEvidence]) -> list[str]:
    source_count = len({source for source in concept.source_ids if source.strip()})
    if source_count > 1:
        return [
            f"{concept.title} now draws on {source_count} sources, so the page should reconcile those inputs instead of mirroring any single source."
        ]
    if evidence:
        return [
            f"The latest compiled source contributes this durable signal: {_evidence_claim_text(evidence[0])}"
        ]
    return []


def _source_synthesis_text(concept: MergedConcept, evidence: list[ConceptEvidence]) -> str:
    if not evidence:
        return (
            f"The current source set supports {concept.title} at the summary level, "
            "but does not yet provide enough cited body claims to write a richer synthesis."
        )

    claims = [_evidence_claim_text(item) for item in evidence[:4]]
    claims = [claim for claim in claims if claim]
    if not claims:
        return (
            f"The cited sources support {concept.title}, but their usable claims need another extraction pass "
            "before this section can become a stronger synthesis."
        )

    if len(claims) == 1:
        return (
            f"The available source support centers on one durable claim: {claims[0]} "
            f"Read against the thesis, that claim frames {concept.title} as a reusable wiki idea rather than a one-off note."
        )

    joined = " ".join(
        f"{_ordinal_word(index)}, {claim}"
        for index, claim in enumerate(claims, start=1)
    )
    return (
        f"The sources establish several linked claims. {joined} "
        f"Taken together, they turn {concept.title} from a label into a reusable operating idea."
    )


def _how_to_use_text(concept: MergedConcept, *, known_slugs: set[str]) -> str:
    related = [
        _related_item(item, known_slugs=known_slugs)
        for item in concept.related
        if str(item).strip()
    ]
    if related:
        related_text = ", ".join(related[:3])
        return (
            f"Use this page when a future answer needs the stable rule behind {concept.title}. "
            f"Start from the thesis, check the source notes when confidence matters, and follow {related_text} "
            "when the question depends on adjacent concepts."
        )
    return (
        f"Use this page as the first stop for questions about {concept.title}. "
        "Start from the thesis, then inspect the source notes to decide whether a new source changes the rule "
        "or only adds another example."
    )


def _boundaries_text(concept: MergedConcept, evidence: list[ConceptEvidence]) -> str:
    source_count = len({source for source in concept.source_ids if source.strip()})
    evidence_count = len(evidence)
    return (
        f"This synthesis is bounded by {source_count} source"
        f"{'' if source_count == 1 else 's'} and {evidence_count} selected source note"
        f"{'' if evidence_count == 1 else 's'}. Treat it as the current reading of the source set, "
        "not an exhaustive history. Reopen the page when a new source contradicts the thesis, adds a missing "
        "implementation constraint, or turns an example into a broader pattern."
    )


def _sentence_text(value: str) -> str:
    text = " ".join(str(value).split())
    if not text:
        return ""
    return text if text[-1] in ".?!" else f"{text}."


def _evidence_claim_text(item: ConceptEvidence) -> str:
    note = " ".join(str(item.note).split())
    if len(note.split()) >= 4:
        return _sentence_text(note)
    return _sentence_text(item.quote)


def _ordinal_word(index: int) -> str:
    return {
        1: "First",
        2: "Second",
        3: "Third",
        4: "Fourth",
    }.get(index, f"Claim {index}")


def is_publishable_concept(concept: MergedConcept) -> bool:
    source_count = len({source for source in concept.source_ids if source.strip()})
    return is_compound_source_count(source_count)


def _meaning_text(concept: MergedConcept) -> str:
    source_count = len({source for source in concept.source_ids if source.strip()})
    return (
        f"This concept is currently supported by {source_count} "
        f"{'source' if source_count == 1 else 'sources'}. "
        "Treat it as durable wiki knowledge only when the evidence explains an operating rule, architecture pattern, "
        "or repeated workflow rather than a single source inventory item."
    )


def _operational_use_text(concept: MergedConcept) -> str:
    related = [item for item in concept.related if item.strip()]
    if related:
        linked = ", ".join(_safe_page_slug(item) for item in related[:3])
        return f"Use this page to connect implementation and maintenance decisions with related concepts: {linked}."
    return "Use this page as a compact synthesis anchor before returning to raw sources."


def _query_body(
    query: ExtractedQuery,
    *,
    known_slugs: set[str],
    sources_by_id: dict[str, SourceDescriptor],
) -> str:
    lines = [
        f"# {query.title}",
        "",
        "## Summary",
        "",
        _canonicalize_wikilinks(query.summary, known_slugs=known_slugs),
        "",
        "## Answer",
        "",
        _canonicalize_wikilinks(query.answer, known_slugs=known_slugs),
        "",
        "## Evidence",
        "",
    ]
    if query.evidence:
        for item in _selected_evidence(query.evidence, sources_by_id=sources_by_id):
            note = f" {item.note}" if item.note else ""
            lines.append(f"- `{item.source_id}`: {item.quote}{note}")
    else:
        lines.append("- No evidence citations were available for this query.")

    if query.related:
        lines.extend(["", "## Related", ""])
        lines.extend(f"- {_related_item(item, known_slugs=known_slugs)}" for item in query.related)

    return "\n".join(lines).strip() + "\n"


def _metadata_tags(
    slug: str,
    title: str,
    related: list[str],
    *,
    extra: list[str] | None = None,
    hub: str = "general",
) -> list[str]:
    values = [
        slug,
        *[_candidate_concept_slug(item) for item in related],
        *(extra or []),
        *([hub] if hub in KNOWN_WIKI_HUBS else []),
        *_tag_tokens(title),
    ]
    tags: list[str] = []
    seen: set[str] = set()
    for value in values:
        tag = _tag_slug(value)
        if len(tag) < 3 or tag in seen or tag in GENERIC_METADATA_TAGS:
            continue
        tags.append(tag)
        seen.add(tag)
        if len(tags) >= 8:
            break
    while len(tags) < 3:
        fallback = f"wiki-{len(tags) + 1}"
        tags.append(fallback)
    return tags


def _tag_tokens(title: str) -> list[str]:
    return [
        token
        for token in _tag_slug(title).split("-")
        if len(token) >= 4
    ]


def _tag_slug(value: str) -> str:
    tag = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return re.sub(r"-+", "-", tag).strip("-")


def _related_item(item: str, *, known_slugs: set[str]) -> str:
    slug = _safe_page_slug(_candidate_concept_slug(item))
    if slug in known_slugs:
        return f"[[concepts/{slug}]]"
    return item


def _filtered_related_items(items: list[str], *, known_slugs: set[str]) -> list[str]:
    filtered: list[str] = []
    seen: set[str] = set()
    for item in items:
        slug = _safe_page_slug(_candidate_concept_slug(item))
        if slug not in known_slugs or slug in seen:
            continue
        filtered.append(slug)
        seen.add(slug)
    return filtered


def _candidate_concept_slug(value: str) -> str:
    slug = str(value).strip().strip("/")
    if "|" in slug:
        slug = slug.split("|", 1)[0].strip()
    if "#" in slug:
        slug = slug.split("#", 1)[0].strip()
    for prefix in ("concepts/", "queries/"):
        if slug.startswith(prefix):
            slug = slug[len(prefix):]
            break
    return _tag_slug(slug)


def _canonicalize_wikilinks(text: str, *, known_slugs: set[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        target = match.group("target").strip()
        anchor = match.group("anchor") or ""
        label = match.group("label") or ""
        slug = _candidate_concept_slug(target)
        if slug in known_slugs:
            return f"[[concepts/{slug}{anchor}{label}]]"
        return match.group(0)

    return re.sub(
        r"\[\[(?P<target>[^\]|#]+)(?P<anchor>#[^\]|]+)?(?P<label>\|[^\]]+)?\]\]",
        replace,
        text,
    )


def _selected_evidence(
    evidence: list[ConceptEvidence],
    *,
    sources_by_id: dict[str, SourceDescriptor] | None = None,
) -> list[ConceptEvidence]:
    sources_by_id = sources_by_id or {}
    selected: list[ConceptEvidence] = []
    seen: set[tuple[str, str, str]] = set()
    per_source: dict[str, int] = {}
    for item in evidence:
        display_source_id = _display_source_id(item.source_id, sources_by_id=sources_by_id)
        quote = " ".join(str(item.quote).split())
        note = " ".join(str(item.note).split())
        if not quote or _is_raw_metadata_quote(quote):
            continue
        if per_source.get(display_source_id, 0) >= MAX_EVIDENCE_PER_SOURCE:
            continue
        key = (display_source_id, quote, note)
        if key in seen:
            continue
        selected.append(ConceptEvidence(source_id=display_source_id, quote=quote, note=note))
        seen.add(key)
        per_source[display_source_id] = per_source.get(display_source_id, 0) + 1
        if len(selected) >= MAX_EVIDENCE_ITEMS:
            break
    return selected


def _display_source_ids(
    source_ids: list[str],
    *,
    sources_by_id: dict[str, SourceDescriptor],
) -> list[str]:
    return [
        item
        for item in dict.fromkeys(
            _display_source_id(source_id, sources_by_id=sources_by_id)
            for source_id in source_ids
            if str(source_id).strip()
        )
        if item
    ]


def _display_source_id(
    source_id: str,
    *,
    sources_by_id: dict[str, SourceDescriptor],
) -> str:
    descriptor = sources_by_id.get(source_id)
    kind, raw_path = _split_source_id(source_id)
    if descriptor is not None:
        kind = descriptor.kind or kind
        raw_path = descriptor.source_path or raw_path

    if kind in {"skill", "skills"}:
        skill_name = _skill_name_from_path(raw_path)
        if skill_name:
            return f"skill:{skill_name}"

    # ADR-814 publish-by-construction: source citations must stay portable.
    # Vault/documents/ADR refs can carry an absolute machine path; relativize
    # it against the known roots so no /Users/<name>/ path lands in the brain.
    portable = _portable_source_path(raw_path)
    if portable != raw_path:
        return f"{kind}:{portable}" if kind else portable

    return source_id


def _portable_source_path(raw_path: str) -> str:
    """Strip a known machine root prefix from an absolute source path.

    Returns the path relative to the vault or documents root when it lives
    under one of them; otherwise returns the input unchanged. Keeps generated
    wiki citations free of machine-specific absolute paths (ADR-814).
    """
    text = str(raw_path).strip()
    if not text.startswith("/"):
        return text
    try:
        from src.config.paths import get_documents_dir, get_vault_dir

        roots = [get_vault_dir(), get_documents_dir()]
    except Exception:  # noqa: BLE001 — config unavailable; leave path as-is
        return text
    for root in roots:
        root_s = str(Path(root).expanduser())
        if text == root_s:
            return ""
        if text.startswith(root_s + "/"):
            return text[len(root_s) + 1:]
    return text


def _split_source_id(source_id: str) -> tuple[str, str]:
    if ":" not in source_id:
        return "", source_id
    kind, raw_path = source_id.split(":", 1)
    return kind.strip(), raw_path.strip()


def _skill_name_from_path(raw_path: str) -> str:
    path = str(raw_path).strip().replace("\\", "/").strip("/")
    if not path:
        return ""
    parts = [part for part in path.split("/") if part]
    if not parts:
        return ""
    if parts[-1].lower() == "skill.md" and len(parts) >= 2:
        return parts[-2]
    for index, part in enumerate(parts):
        if part == "skills" and index + 1 < len(parts):
            candidate = parts[index + 1]
            if candidate and candidate.lower() != "skill.md":
                return candidate
    return Path(path).stem


def _is_raw_metadata_quote(quote: str) -> bool:
    normalized = quote.strip().lower()
    return any(normalized.startswith(prefix) for prefix in RAW_EVIDENCE_PREFIXES)


def _default_query_for_concept(concept: MergedConcept) -> ExtractedQuery | None:
    source_count = len({source for source in concept.source_ids if source.strip()})
    if source_count < MIN_COMPOUND_SOURCE_COUNT:
        return None
    slug = _safe_page_slug(concept.slug)
    title = f"How should {concept.title} be used?"
    return ExtractedQuery(
        title=title,
        slug=f"how-should-{slug}-be-used",
        summary=f"A reusable answer for applying [[concepts/{slug}]].",
        answer=(
            f"{concept.summary}\n\n"
            f"Use [[concepts/{slug}]] as the source-backed synthesis page before returning to raw evidence."
        ),
        evidence=_selected_evidence(concept.evidence),
        source_ids=list(concept.source_ids),
        related=[slug, *list(concept.related[:3])],
    )


def _metadata_hub(
    source_ids: list[str],
    *,
    sources_by_id: dict[str, SourceDescriptor],
) -> str:
    hub_counts: dict[str, int] = {}
    for source_id in source_ids:
        descriptor = sources_by_id.get(source_id)
        candidates: list[str] = []
        if descriptor is not None:
            candidates.append(str(descriptor.metadata.get("hub") or ""))
            candidates.append(descriptor.source_path)
            candidates.append(descriptor.source_id)
        candidates.append(source_id)
        for value in candidates:
            hub = _canonical_hub(value)
            if hub:
                hub_counts[hub] = hub_counts.get(hub, 0) + 1
                break
    if not hub_counts:
        return "general"
    return sorted(hub_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _canonical_hub(value: str) -> str:
    text = str(value).strip().lower()
    if not text or text in {"unknown", "general"}:
        return ""
    text = text.replace("\\", "/")
    if text in KNOWN_WIKI_HUBS:
        return text
    if any(
        marker in text
        for marker in (
            "venture-augur",
            "linkedin-writer",
            "websites",
            "presentations",
            "market-research",
            "geo-",
            "/geo",
            "codex-primary-runtime/slides",
            "codex-primary-runtime/spreadsheets",
            "imagegen",
            "frontend-design",
            "ui-ux",
        )
    ):
        return "studio"
    if any(marker in text for marker in ("career-ops", "/career/", "interview", "cv.md", "job-search", "second-career", "sample-fitout-project")):
        return "career"
    if any(marker in text for marker in ("finance", "health", "lifestyle", "family", "recipe", "apple/", "eisenhower", "/growth/")):
        return "life"
    if any(
        marker in text
        for marker in (
            "skills/augur-core",
            "/commands/",
            "command",
            "adr",
            "codex",
            "plugin-creator",
            "skill-installer",
            "openai-docs",
            "claude-md-management",
            "claude-skills-guide",
            "mcp-enhanced",
        )
    ):
        return "command"
    if any(
        marker in text
        for marker in (
            "skills/routine-",
            "daemon",
            "platform-admin",
            "adaptive",
            "ide-integration",
            "superpowers",
            "code-architect",
            "code-explorer",
            "code-reviewer",
            "test-driven-development",
            "systematic-debugging",
            "using-git-worktrees",
        )
    ):
        return "adaptive"
    if any(marker in text for marker in ("memory", "knowledge", "advisor", "brain")):
        return "brain"
    return ""


def _index_body(
    *,
    concept_entries: list[tuple[str, Path]],
    query_entries: list[tuple[str, Path]],
) -> str:
    lines = ["# Wiki Index", "", "## Concepts", ""]
    if concept_entries:
        lines.extend(f"- [{title}]({path.as_posix()})" for title, path in concept_entries)
    else:
        lines.append("- No concept pages have been compiled yet.")

    if query_entries:
        lines.extend(["", "## Queries", ""])
        lines.extend(f"- [{title}]({path.as_posix()})" for title, path in query_entries)

    return "\n".join(lines).strip() + "\n"


def _overview_body(
    *,
    concept_entries: list[tuple[str, Path]],
    query_entries: list[tuple[str, Path]],
) -> str:
    lines = [
        "# Wiki Overview",
        "",
        "This wiki is organized around durable concepts extracted from source material and compiled into reusable synthesis pages.",
        "",
        "## Navigation",
        "",
        "- [Wiki Index](index.md)",
        "",
        "## Current Thesis",
        "",
        _overview_thesis(concept_entries=concept_entries, query_entries=query_entries),
        "",
        "## What This Wiki Knows",
        "",
        _overview_coverage(concept_entries=concept_entries, query_entries=query_entries),
        "",
        "## Recent Additions",
        "",
    ]
    if concept_entries:
        lines.extend(f"- [{title}]({path.as_posix()})" for title, path in concept_entries[-10:])
    else:
        lines.append("- No concept pages have been compiled yet.")

    lines.extend([
        "",
        "## Concepts",
        "",
    ])
    if concept_entries:
        lines.extend(f"- [{title}]({path.as_posix()})" for title, path in concept_entries[:20])
    else:
        lines.append("- No concept pages have been compiled yet.")

    if query_entries:
        lines.extend(["", "## Queries", ""])
        lines.extend(f"- [{title}]({path.as_posix()})" for title, path in query_entries[:20])

    return "\n".join(lines).strip() + "\n"


def _overview_thesis(
    *,
    concept_entries: list[tuple[str, Path]],
    query_entries: list[tuple[str, Path]],
) -> str:
    if not concept_entries:
        return "The wiki has not compiled enough concepts yet to form a durable thesis."
    return (
        f"The wiki currently contains {len(concept_entries)} concept pages"
        f" and {len(query_entries)} reusable query pages. "
        "Its strongest pages should explain stable operating ideas, not mirror source indexes."
    )


def _overview_coverage(
    *,
    concept_entries: list[tuple[str, Path]],
    query_entries: list[tuple[str, Path]],
) -> str:
    if not concept_entries:
        return "Coverage is empty; run a bounded concept extraction cycle before relying on the wiki."
    sample_titles = ", ".join(title for title, _path in concept_entries[:5])
    suffix = " Query pages are present for reusable answers." if query_entries else ""
    return f"Current coverage starts with: {sample_titles}.{suffix}"


def _page_entries(directory: Path) -> list[tuple[str, Path]]:
    if not directory.exists():
        return []

    entries: list[tuple[str, Path]] = []
    for path in sorted(directory.glob("*.md")):
        metadata, _body = parse_frontmatter(path)
        title = str(metadata.get("title") or path.stem.replace("-", " ").title()).strip()
        entries.append((title, Path(directory.name) / path.name))
    return entries


def _safe_page_slug(value: str) -> str:
    slug = value.strip().strip("/")
    if not slug or "/" in slug or slug in {".", ".."}:
        raise ValueError(f"Invalid concept slug: {value!r}")
    return slug

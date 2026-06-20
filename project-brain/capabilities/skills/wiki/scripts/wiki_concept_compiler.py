"""Agent-orchestrated coordinator for concept-first wiki compilation."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from skills.wiki.scripts.wiki_concept_extraction import build_extraction_prompt, parse_extraction_payload
from skills.wiki.scripts.wiki_concept_merge import MergedConcept, merge_extracted_concepts
from skills.wiki.scripts.wiki_concept_models import ExtractedConcept, SourceDescriptor
from skills.wiki.scripts.wiki_compound_policy import (
    MAX_CLUSTER_CONTEXT_SOURCES,
    MIN_COMPOUND_SOURCE_COUNT,
    TARGET_COMPOUND_SOURCE_MAX,
    TARGET_COMPOUND_SOURCE_MIN,
    target_source_count_label,
)
from skills.wiki.scripts.wiki_concept_pages import (
    is_publishable_concept,
    write_concept_pages,
    write_query_pages,
    write_wiki_support_pages,
)
from skills.wiki.scripts.wiki_concept_state import (
    COMPILER_VERSION,
    WikiCompilerState,
    save_compiler_state,
    source_is_already_bound,
    source_needs_extraction,
)
from src.config.paths import get_compiled_wiki_dir
from src.lib.frontmatter_utils import parse_frontmatter


PROMPT_PREVIEW_LIMIT = 240
SOURCE_FAMILY_ORDER = {
    "ask": 0,
    "asks": 0,
    "synthesis": 1,
    "syntheses": 1,
    "vault": 2,
    "documents": 3,
    "document": 3,
    "docs": 3,
    "doc": 3,
    "adrs": 4,
    "adr": 4,
    "pages": 5,
    "page": 5,
    "integrations": 6,
    "integration": 6,
    "skills": 7,
    "skill": 7,
    "commands": 8,
    "command": 8,
    "actions": 9,
    "action": 9,
}
SOURCE_FAMILY_TIER = {
    "ask": 0,
    "asks": 0,
    "synthesis": 0,
    "syntheses": 0,
    "vault": 0,
    "documents": 0,
    "document": 0,
    "docs": 0,
    "doc": 0,
    "adrs": 1,
    "adr": 1,
    "pages": 1,
    "page": 1,
    "integrations": 1,
    "integration": 1,
    "skills": 2,
    "skill": 2,
    "commands": 2,
    "command": 2,
    "actions": 2,
    "action": 2,
}
SOURCE_SIGNAL_PRIORITY = {
    "user_ask_or_note": 0,
    "user_created_skill": 1,
    "personal_data": 10,
    "saved_reference": 20,
    "augur_technical": 30,
}
NEAR_DUPLICATE_CLUSTER_SCORE = 90


@dataclass(frozen=True)
class ExtractionBatchItem:
    source: SourceDescriptor
    prompt: str
    cluster_sources: list[SourceDescriptor] = field(default_factory=list)


@dataclass(frozen=True)
class ExtractionBatch:
    items: list[ExtractionBatchItem] = field(default_factory=list)


@dataclass(frozen=True)
class ApplyResult:
    pages_written: list[str]
    concepts_written: int
    concepts_deferred: int = 0
    sources_processed: int = 0
    sources_generated: int = 0
    queries_written: int = 0
    draft_concepts: int = 0
    overbroad_concepts: int = 0
    stale_sources_pruned: int = 0
    cluster_min_sources: int = MIN_COMPOUND_SOURCE_COUNT
    cluster_max_sources: int = TARGET_COMPOUND_SOURCE_MAX


def prepare_extraction_batch(
    sources: list[SourceDescriptor],
    state: WikiCompilerState,
    *,
    limit: int,
    weight_by_source_id: dict[str, float] | None = None,
) -> ExtractionBatch:
    if limit <= 0:
        return ExtractionBatch()

    changed_sources = [
        source
        for source in sources
        if not source_is_already_bound(state, source.source_id)
        and source_needs_extraction(state, source.source_id, source.checksum)
    ]
    ordered_sources = _order_sources_for_extraction(changed_sources)
    if weight_by_source_id:
        ordered_sources = _apply_signal_weights(ordered_sources, weight_by_source_id)
    cluster_lookup = {
        source.source_id: _related_source_cluster(source, sources)
        for source in ordered_sources[:limit]
    }

    return ExtractionBatch(
        items=[
            ExtractionBatchItem(
                source=source,
                prompt=build_extraction_prompt(
                    source,
                    _read_source_body(source),
                    cluster_context=_source_cluster_context(cluster_lookup[source.source_id]),
                ),
                cluster_sources=cluster_lookup[source.source_id],
            )
            for source in ordered_sources[:limit]
        ]
    )


def _apply_signal_weights(
    sources: list[SourceDescriptor],
    weight_by_source_id: dict[str, float],
) -> list[SourceDescriptor]:
    indexed = {source.source_id: index for index, source in enumerate(sources)}
    return sorted(
        sources,
        key=lambda source: (
            -float(weight_by_source_id.get(source.source_id, 1.0)),
            indexed[source.source_id],
        ),
    )


def _order_sources_for_extraction(sources: list[SourceDescriptor]) -> list[SourceDescriptor]:
    """Order sources by explicit user signal, then compound-size topical cohesion."""
# TODO_CLEANUP: This file is 905 lines — consider splitting into smaller modules
    by_signal: dict[int, list[SourceDescriptor]] = {}
    for source in sources:
        by_signal.setdefault(_source_signal_priority(source), []).append(source)

    ordered: list[SourceDescriptor] = []
    deferred_cohesive_groups: list[tuple[int, list[SourceDescriptor]]] = []
    residual_by_signal: dict[int, list[SourceDescriptor]] = {}
    for signal_priority in sorted(by_signal):
        signal_sources = by_signal[signal_priority]
        if signal_priority <= SOURCE_SIGNAL_PRIORITY["user_created_skill"]:
            ordered.extend(_order_sources_within_signal(signal_sources))
            continue

        cohesive_groups, remaining_sources = _cohesive_topical_groups(signal_sources)
        deferred_cohesive_groups.extend(
            (signal_priority, group_sources)
            for group_sources in cohesive_groups
        )
        residual_by_signal[signal_priority] = remaining_sources

    for _signal_priority, group_sources in sorted(
        deferred_cohesive_groups,
        key=_deferred_cohesive_group_sort_key,
    ):
        ordered.extend(_order_cohesive_group_sources(group_sources))

    for signal_priority in sorted(residual_by_signal):
        ordered.extend(_order_sources_within_signal(residual_by_signal[signal_priority]))
    return ordered


def _order_sources_within_signal(sources: list[SourceDescriptor]) -> list[SourceDescriptor]:
    """Spread bounded batches across source families, ranking within each family."""
    cohesive_groups, remaining_sources = _cohesive_topical_groups(sources)
    if cohesive_groups:
        ordered: list[SourceDescriptor] = []
        for group_sources in cohesive_groups:
            ordered.extend(_order_cohesive_group_sources(group_sources))
        return ordered + _order_sources_within_signal(remaining_sources)

    by_family: dict[str, list[SourceDescriptor]] = {}

    for source in sources:
        by_family.setdefault(_source_family(source), []).append(source)
    for family_sources in by_family.values():
        family_sources.sort(key=lambda item: (-item.priority, item.source_id))

    family_names = _ordered_source_families(by_family)
    if _has_ambient_sources(by_family) or any(
        len(family_sources) >= TARGET_COMPOUND_SOURCE_MIN
        for family_sources in by_family.values()
    ):
        return _round_robin_family_sources(by_family, family_names)

    while family_names:
        tier = _source_family_tier(family_names[0])
        tier_families = [
            family for family in family_names if _source_family_tier(family) == tier
        ]
        ordered = _round_robin_family_sources(by_family, tier_families)
        remaining_families = [
            family for family in family_names if family not in tier_families and by_family[family]
        ]
        family_names = remaining_families
        if ordered:
            return ordered + _order_sources_within_signal(
                [
                    source
                    for family in remaining_families
                    for source in by_family[family]
                ]
            )
    return []


def _round_robin_family_sources(
    by_family: dict[str, list[SourceDescriptor]],
    family_names: list[str],
) -> list[SourceDescriptor]:
    ordered: list[SourceDescriptor] = []
    family_names = list(family_names)
    while family_names:
        remaining: list[str] = []
        for family in family_names:
            family_sources = by_family[family]
            if not family_sources:
                continue
            ordered.append(family_sources.pop(0))
            if family_sources:
                remaining.append(family)
        family_names = remaining
    return ordered


def _cohesive_topical_groups(
    sources: list[SourceDescriptor],
) -> tuple[list[list[SourceDescriptor]], list[SourceDescriptor]]:
    by_topic: dict[tuple[str, str], list[SourceDescriptor]] = {}
    for source in sources:
        hub = _source_hub(source)
        family = _source_family(source)
        if not hub or not family:
            continue
        by_topic.setdefault((hub, family), []).append(source)

    groups = [
        group_sources
        for group_sources in by_topic.values()
        if len(group_sources) >= TARGET_COMPOUND_SOURCE_MIN
    ]
    groups.sort(key=_cohesive_group_sort_key)
    grouped_source_ids = {
        source.source_id
        for group_sources in groups
        for source in group_sources
    }
    remaining = [
        source for source in sources if source.source_id not in grouped_source_ids
    ]
    return groups, remaining


def _cohesive_group_sort_key(sources: list[SourceDescriptor]) -> tuple[int, int, int, str, str, str]:
    first = sources[0]
    family = _source_family(first)
    hub = _source_hub(first)
    return (
        -len(sources),
        -max(source.priority for source in sources),
        _source_family_tier(family),
        hub,
        family,
        min(source.source_id for source in sources),
    )


def _deferred_cohesive_group_sort_key(
    item: tuple[int, list[SourceDescriptor]],
) -> tuple[int, int, int, int, str, str, str]:
    signal_priority, sources = item
    return (signal_priority, *_cohesive_group_sort_key(sources))


def _order_cohesive_group_sources(sources: list[SourceDescriptor]) -> list[SourceDescriptor]:
    remaining = sorted(sources, key=lambda item: (-item.priority, item.source_id))
    ordered: list[SourceDescriptor] = []
    while remaining:
        previous = ordered[-1] if ordered else None
        candidate = min(
            remaining,
            key=lambda item: _cohesive_candidate_sort_key(item, previous),
        )
        ordered.append(candidate)
        remaining.remove(candidate)
    return ordered


def _cohesive_candidate_sort_key(
    candidate: SourceDescriptor,
    previous: SourceDescriptor | None,
) -> tuple[int, int, str]:
    near_duplicate_penalty = 0
    if previous is not None and _source_cluster_score(previous, candidate) >= NEAR_DUPLICATE_CLUSTER_SCORE:
        near_duplicate_penalty = 1
    return (near_duplicate_penalty, -candidate.priority, candidate.source_id)


def _ordered_source_families(by_family: dict[str, list[SourceDescriptor]]) -> list[str]:
    if _has_ambient_sources(by_family):
        return sorted(
            by_family,
            key=lambda family: (
                -max(
                    int(source.metadata.get("ambient_detected_rank", 0) or 0)
                    for source in by_family[family]
                ),
                family,
            ),
        )
    if any(len(family_sources) >= TARGET_COMPOUND_SOURCE_MIN for family_sources in by_family.values()):
        return sorted(
            by_family,
            key=lambda family: (
                0 if len(by_family[family]) >= TARGET_COMPOUND_SOURCE_MIN else 1,
                _source_family_tier(family),
                -len(by_family[family]),
                SOURCE_FAMILY_ORDER.get(family, SOURCE_FAMILY_ORDER.get(family.rstrip("s"), 99)),
                family,
            ),
        )
    return sorted(
        by_family,
        key=lambda family: (
            _source_family_tier(family),
            SOURCE_FAMILY_ORDER.get(family, SOURCE_FAMILY_ORDER.get(family.rstrip("s"), 99)),
            family,
        ),
        )


def _has_ambient_sources(by_family: dict[str, list[SourceDescriptor]]) -> bool:
    return any(
        bool(source.metadata.get("ambient_detected"))
        for family_sources in by_family.values()
        for source in family_sources
    )


def _source_signal_priority(source: SourceDescriptor) -> int:
    """Rank wiki inputs by user signal before technical coverage volume.

    P1: user-authored asks, syntheses, notes, and user-created skills.
    P2: personal documents such as CV/resume/career collateral.
    P3: saved reference material such as web links, books, and installed skills.
    P4: Augur technical infrastructure such as ADRs, repo skills, commands, and actions.
    """
    kind = source.kind.strip().lower()
    family = _source_family(source).strip().lower()
    source_path = _normalized_source_path(source.source_path)

    if kind in {"ask", "asks", "synthesis", "syntheses"} or family in {"ask", "asks", "synthesis", "syntheses"}:
        return SOURCE_SIGNAL_PRIORITY["user_ask_or_note"]

    if kind in {"adr", "adrs", "command", "commands", "action", "actions", "page", "pages", "integration", "integrations"}:
        return SOURCE_SIGNAL_PRIORITY["augur_technical"]

    if kind in {"skill", "skills"}:
        if _is_user_created_skill_path(source_path):
            return SOURCE_SIGNAL_PRIORITY["user_created_skill"]
        if _is_installed_external_skill_path(source_path):
            return SOURCE_SIGNAL_PRIORITY["saved_reference"]
        return SOURCE_SIGNAL_PRIORITY["augur_technical"]

    if _is_augur_technical_path(source_path):
        return SOURCE_SIGNAL_PRIORITY["augur_technical"]

    if _is_personal_data_path(source_path):
        return SOURCE_SIGNAL_PRIORITY["personal_data"]

    if _is_saved_reference_path(source_path):
        return SOURCE_SIGNAL_PRIORITY["saved_reference"]

    if kind in {"document", "documents", "doc", "docs"}:
        if _is_technical_document_path(source_path):
            return SOURCE_SIGNAL_PRIORITY["augur_technical"]
        return SOURCE_SIGNAL_PRIORITY["personal_data"]

    if kind in {"vault"}:
        return SOURCE_SIGNAL_PRIORITY["user_ask_or_note"]

    return SOURCE_SIGNAL_PRIORITY["augur_technical"]


def _normalized_source_path(source_path: str) -> str:
    return str(source_path).strip().replace("\\", "/").lower()


def _is_user_created_skill_path(source_path: str) -> bool:
    if "/plugins/cache/" in source_path:
        return False
    return (
        "/.claude/skills/" in source_path
        or "/.codex/skills/" in source_path
        or "/.agents/skills/" in source_path
        or "/.gemini/skills/" in source_path
    )


def _is_installed_external_skill_path(source_path: str) -> bool:
    return "/plugins/cache/" in source_path


def _is_saved_reference_path(source_path: str) -> bool:
    markers = (
        "/sources/web/",
        "/sources/",
        "/books/",
        "/reading-list/",
        "/articles/",
        "/web/",
    )
    return any(marker in source_path for marker in markers)


def _is_personal_data_path(source_path: str) -> bool:
    markers = (
        "/career-ops/",
        "/cv",
        "/resume",
        "/applications",
        "/pipeline",
        "/profile",
        "/portfolio",
    )
    return any(marker in source_path for marker in markers)


def _is_augur_technical_path(source_path: str) -> bool:
    markers = (
        "/daemon/",
        "/ai/ide-integration/",
        "/document-extractor/",
        "/platform-admin/",
        "/remote-access/",
        "/updater/",
    )
    return any(marker in source_path for marker in markers)


def _is_technical_document_path(source_path: str) -> bool:
    return (
        "/adrs/" in source_path
        or source_path.startswith("docs/")
        or source_path.startswith("skills/")
        or "/docs/generated/" in source_path
    )


def _source_family_tier(family: str) -> int:
    return SOURCE_FAMILY_TIER.get(family, SOURCE_FAMILY_TIER.get(family.rstrip("s"), 3))


def _source_family(source: SourceDescriptor) -> str:
    raw = source.metadata.get("source_family") if isinstance(source.metadata, dict) else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if source.kind:
        return source.kind
    return "unknown"


def _related_source_cluster(source: SourceDescriptor, sources: list[SourceDescriptor]) -> list[SourceDescriptor]:
    scored: list[tuple[int, int, str, SourceDescriptor]] = []
    for candidate in sources:
        score = _source_cluster_score(source, candidate)
        if score <= 0:
            continue
        scored.append((-score, -candidate.priority, candidate.source_id, candidate))
    scored.sort()
    return [candidate for *_prefix, candidate in scored[:MAX_CLUSTER_CONTEXT_SOURCES]]


def _source_cluster_score(source: SourceDescriptor, candidate: SourceDescriptor) -> int:
    if candidate.source_id == source.source_id:
        return 10_000

    score = 0
    if _source_family(candidate) == _source_family(source):
        score += 40
    if _source_hub(candidate) and _source_hub(candidate) == _source_hub(source):
        score += 25
    if candidate.kind == source.kind:
        score += 15
    score += _relationship_cluster_score(source, candidate)
    score += 5 * len(_title_tokens(candidate.title) & _title_tokens(source.title))
    return score


def _relationship_cluster_score(source: SourceDescriptor, candidate: SourceDescriptor) -> int:
    source_targets = _relationship_targets(source)
    candidate_targets = _relationship_targets(candidate)
    if not source_targets and not candidate_targets:
        return 0

    source_target_keys = {_relationship_key(target) for target in source_targets}
    candidate_target_keys = {_relationship_key(target) for target in candidate_targets}
    candidate_identity = _relationship_identity_keys(candidate)
    source_identity = _relationship_identity_keys(source)

    score = 0
    if source_target_keys & candidate_identity:
        score += 80
    if candidate_target_keys & source_identity:
        score += 80
    shared_targets = source_target_keys & candidate_target_keys
    score += 35 * len(shared_targets)
    return score


def _relationship_targets(source: SourceDescriptor) -> list[str]:
    metadata = source.metadata if isinstance(source.metadata, dict) else {}
    targets = metadata.get("relationship_targets")
    if isinstance(targets, list):
        return [str(target).strip() for target in targets if str(target).strip()]

    relationships = metadata.get("relationships")
    if not isinstance(relationships, dict):
        return []
    values: list[str] = []
    for field_targets in relationships.values():
        if not isinstance(field_targets, list):
            continue
        values.extend(str(target).strip() for target in field_targets if str(target).strip())
    return list(dict.fromkeys(values))


def _relationship_identity_keys(source: SourceDescriptor) -> set[str]:
    source_path = Path(source.source_path)
    return {
        key
        for raw in (
            source.title,
            source.source_id,
            source.source_path,
            source_path.stem,
            source_path.with_suffix("").as_posix(),
        )
        if (key := _relationship_key(raw))
    }


def _relationship_key(value: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith("[[") and raw.endswith("]]"):
        raw = raw[2:-2]
    raw = raw.split("|", 1)[0].split("#", 1)[0].strip()
    raw = raw.removesuffix(".md")
    raw = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return raw


def _source_hub(source: SourceDescriptor) -> str:
    metadata = source.metadata if isinstance(source.metadata, dict) else {}
    return str(metadata.get("hub") or "").strip()


def _title_tokens(title: str) -> set[str]:
    stopwords = {"a", "an", "and", "for", "in", "of", "on", "the", "to", "with"}
    return {
        token
        for token in re.split(r"[^a-z0-9]+", title.lower())
        if len(token) >= 3 and token not in stopwords
    }


_CLUSTER_EXCERPT_SOURCES = 5
_CLUSTER_EXCERPT_CHARS = 600


def _source_cluster_context(cluster_sources: list[SourceDescriptor]) -> str:
    if len(cluster_sources) <= 1:
        return ""
    lines = [
        f"Target source density: {target_source_count_label()} sources per published concept page.",
        "Use this cluster to decide whether the source should strengthen an existing/compound concept, remain pending, or justify a rare new page.",
    ]
    for index, cluster_source in enumerate(cluster_sources, start=1):
        lines.append(
            f"{index}. {cluster_source.source_id} | {cluster_source.kind} | {cluster_source.title} | {cluster_source.source_path}"
        )

    # Include short body excerpts from the top-K most-related cluster sources.
    # Without this the synthesizer can only see metadata for related sources
    # and cannot actually synthesize a compound concept across the cluster.
    # Cap at 5 sources × ~600 chars each (~3KB) to keep prompts bounded.
    excerpt_lines: list[str] = []
    for index, cluster_source in enumerate(cluster_sources[:_CLUSTER_EXCERPT_SOURCES], start=1):
        body = _read_source_body(cluster_source).strip()
        if not body or body == cluster_source.title:
            continue
        excerpt = body[:_CLUSTER_EXCERPT_CHARS].rstrip()
        if len(body) > _CLUSTER_EXCERPT_CHARS:
            excerpt += "..."
        excerpt_lines.append(
            f"\n[cluster source {index} | {cluster_source.source_id}]\n{excerpt}"
        )
    if excerpt_lines:
        lines.append("")
        lines.append(
            f"Body excerpts for the {len(excerpt_lines)} most-related cluster sources "
            "(synthesize across these when an 8-15-source compound concept genuinely emerges):"
        )
        lines.extend(excerpt_lines)
    return "\n".join(lines)


def write_extraction_batch_file(
    runtime_wiki_dir: Path,
    batch: ExtractionBatch,
    *,
    mode: str,
    timestamp: str | None = None,
) -> Path:
    """Persist full extraction prompts outside the MCP response payload."""
    timestamp = timestamp or datetime.now(UTC).isoformat()
    batch_dir = Path(runtime_wiki_dir) / "concept-batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    target = batch_dir / f"{_safe_batch_mode(mode)}.json"
    payload = {
        "mode": mode,
        "created": timestamp,
        "items": [
            {
                "source": item.source.to_dict(),
                "cluster_sources": [
                    source.to_dict()
                    for source in getattr(item, "cluster_sources", []) or []
                ],
                "prompt": item.prompt,
            }
            for item in batch.items
        ],
    }
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def summarize_extraction_batch(batch: ExtractionBatch, *, batch_file: Path) -> dict[str, Any]:
    """Return bounded metadata for an extraction batch."""
    items = []
    for item in batch.items:
        cluster_sources = list(getattr(item, "cluster_sources", []) or [])
        items.append(
            {
                "source": item.source.to_dict(),
                "source_id": item.source.source_id,
                "kind": item.source.kind,
                "title": item.source.title,
                "checksum": item.source.checksum,
                "prompt_handle": item.source.source_id,
                "prompt_preview": _prompt_preview(item.prompt),
                "prompt_length": len(item.prompt),
                "source_cluster": {
                    "target_source_count": target_source_count_label(),
                    "count": len(cluster_sources),
                    "source_ids": [source.source_id for source in cluster_sources],
                },
            }
        )
    return {
        "batch_file": str(batch_file),
        "batch_handle": Path(batch_file).stem,
        "items": items,
        "count": len(items),
    }


def apply_extraction_batch(
    wiki_dir: Path,
    runtime_wiki_dir: Path,
    state: WikiCompilerState,
    sources: list[SourceDescriptor],
    payloads: dict[str, list[dict[str, Any]]],
    timestamp: str,
) -> ApplyResult:
    # ``wiki_dir`` is the durable compiled wiki. Compiler mechanics stay in
    # runtime, but the context-rich wiki pages are portable vault content.
    output_wiki_dir = get_compiled_wiki_dir(wiki_dir)
    source_by_id = {source.source_id: source for source in sources}
    unknown_source_ids = sorted(set(payloads) - set(source_by_id))
    if unknown_source_ids:
        raise ValueError(f"Unknown source IDs in extraction payloads: {', '.join(unknown_source_ids)}")
    stale_sources_pruned = _prune_stale_state_sources(state, current_source_ids=set(source_by_id))

    prune_legacy_wiki_pages(output_wiki_dir)
    concepts_by_source_id: dict[str, list[ExtractedConcept]] = {}
    processed_source_ids: set[str] = set()

    for source_id in sorted(payloads):
        source = source_by_id[source_id]
        concepts = parse_extraction_payload(source_id, payloads[source_id])
        if concepts:
            state.record_extraction(source_id, source.checksum, concepts, timestamp)
        else:
            state.record_processed(source_id, source.checksum, timestamp)
        concepts_by_source_id[source_id] = concepts
        processed_source_ids.add(source_id)

    for source in sources:
        if source.source_id in processed_source_ids:
            continue
        if source.source_id not in state.sources:
            continue
        concepts_by_source_id[source.source_id] = [
            ExtractedConcept.from_dict(item)
            for item in state.extracted_concepts.get(source.source_id, [])
        ]

    merged_concepts = merge_extracted_concepts(
        [
            concept
            for source_id in sorted(concepts_by_source_id)
            for concept in concepts_by_source_id[source_id]
        ]
    )
    publishable_concepts = [
        concept for concept in merged_concepts if is_publishable_concept(concept)
    ]
    deferred_concepts = len(merged_concepts) - len(publishable_concepts)
    draft_concepts = sum(
        1
        for concept in merged_concepts
        if len({source for source in concept.source_ids if source.strip()}) < MIN_COMPOUND_SOURCE_COUNT
    )
    overbroad_concepts = sum(
        1
        for concept in merged_concepts
        if len({source for source in concept.source_ids if source.strip()}) > TARGET_COMPOUND_SOURCE_MAX
    )
    written_paths = write_concept_pages(
        output_wiki_dir,
        publishable_concepts,
        timestamp=timestamp,
        sources_by_id=source_by_id,
        filter_related_to_known_concepts=True,
    )
    query_paths = write_query_pages(
        output_wiki_dir,
        publishable_concepts,
        timestamp=timestamp,
        include_default_queries=True,
        sources_by_id=source_by_id,
    )
    written_paths.extend(query_paths)
    _prune_obsolete_concept_pages(output_wiki_dir, publishable_concepts)
    _prune_obsolete_query_pages(output_wiki_dir, publishable_concepts, include_default_queries=True)
    written_paths.extend(write_wiki_support_pages(output_wiki_dir, timestamp=timestamp))

    generated_source_ids = _refresh_source_generation_state(
        state,
        publishable_concepts,
        current_source_ids=set(source_by_id),
        timestamp=timestamp,
    )
    state.compiler_version = COMPILER_VERSION
    save_compiler_state(runtime_wiki_dir, state)

    return ApplyResult(
        pages_written=[_relative_page_path(output_wiki_dir, path) for path in written_paths],
        concepts_written=len(publishable_concepts),
        concepts_deferred=deferred_concepts,
        sources_processed=len(processed_source_ids),
        sources_generated=len(generated_source_ids),
        queries_written=len(query_paths),
        draft_concepts=draft_concepts,
        overbroad_concepts=overbroad_concepts,
        stale_sources_pruned=stale_sources_pruned,
    )


def _read_source_body(source: SourceDescriptor) -> str:
    source_path = Path(source.source_path)
    body = _read_file_if_available(source_path)
    if body is not None:
        return body

    rag_entry = source.metadata.get("rag_entry")
    if isinstance(rag_entry, str) and rag_entry.strip():
        body = _read_file_if_available(Path(rag_entry))
        if body is not None:
            return body

    return source.title


def _prompt_preview(prompt: str) -> str:
    collapsed = " ".join(prompt.split())
    if len(collapsed) <= PROMPT_PREVIEW_LIMIT:
        return collapsed
    return collapsed[: PROMPT_PREVIEW_LIMIT - 3].rstrip() + "..."


def _safe_batch_mode(mode: str) -> str:
    safe_mode = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in mode).strip("-")
    return safe_mode or "batch"


def _read_file_if_available(path: Path) -> str | None:
    try:
        if path.is_file():
            raw = path.read_bytes()
            if _looks_like_binary_bytes(raw):
                return None
            return raw.decode("utf-8")
    except (OSError, UnicodeError):
        return None
    return None


def _looks_like_binary_bytes(raw: bytes) -> bool:
    if not raw:
        return False
    if b"\x00" in raw:
        return True
    binary_magic_prefixes = (
        b"%PDF-",
        b"PK\x03\x04",
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
        b"\x89PNG\r\n\x1a\n",
        b"\xff\xd8\xff",
        b"GIF87a",
        b"GIF89a",
    )
    if any(raw.startswith(prefix) for prefix in binary_magic_prefixes):
        return True
    return False


def _prune_obsolete_concept_pages(wiki_dir: Path, merged_concepts: list[MergedConcept]) -> None:
    concepts_dir = wiki_dir / "concepts"
    if not concepts_dir.exists():
        return

    live_slugs = {concept.slug for concept in merged_concepts}
    for path in concepts_dir.glob("*.md"):
        if path.stem not in live_slugs:
            path.unlink()


def _prune_obsolete_query_pages(
    wiki_dir: Path,
    merged_concepts: list[MergedConcept],
    *,
    include_default_queries: bool = False,
) -> None:
    queries_dir = wiki_dir / "queries"
    if not queries_dir.exists():
        return

    live_slugs = {
        query.slug
        for concept in merged_concepts
        for query in concept.queries
    }
    if include_default_queries:
        live_slugs.update(
            f"how-should-{concept.slug}-be-used"
            for concept in merged_concepts
            if len({source for source in concept.source_ids if source.strip()}) >= 2
        )
    for path in queries_dir.glob("*.md"):
        if path.stem not in live_slugs:
            path.unlink()


def prune_legacy_wiki_pages(wiki_dir: Path) -> list[str]:
    """Remove retired source inventory and source-summary pages from the active wiki."""
    wiki_dir = Path(wiki_dir)
    removed: list[str] = []

    sources_dir = wiki_dir / "sources"
    if sources_dir.exists():
        removed.extend(
            path.relative_to(wiki_dir).as_posix()
            for path in sorted(sources_dir.rglob("*.md"))
        )
        shutil.rmtree(sources_dir)

    if not wiki_dir.exists():
        return removed

    for path in sorted(wiki_dir.rglob("*.md")):
        if not path.is_file():
            continue
        try:
            metadata, _body = parse_frontmatter(path)
        except (OSError, ValueError):
            continue
        if str(metadata.get("page_type") or "").strip() not in {"source-summary", "query-output"}:
            continue
        removed.append(path.relative_to(wiki_dir).as_posix())
        path.unlink()

    return sorted(dict.fromkeys(removed))


def _refresh_source_generation_state(
    state: WikiCompilerState,
    merged_concepts: list[MergedConcept],
    *,
    current_source_ids: set[str],
    timestamp: str,
) -> set[str]:
    generated_source_ids = {
        source_id
        for concept in merged_concepts
        for source_id in concept.source_ids
    }
    slugs_by_source_id: dict[str, set[str]] = {}
    for concept in merged_concepts:
        for source_id in concept.source_ids:
            slugs_by_source_id.setdefault(source_id, set()).add(concept.slug)

    for source_id in sorted(current_source_ids):
        source_state = state.sources.get(source_id)
        if source_state is None:
            continue
        if source_id in slugs_by_source_id:
            source_state.generated_at = timestamp
            source_state.concept_slugs = sorted(slugs_by_source_id[source_id])
        else:
            source_state.generated_at = None
            source_state.concept_slugs = []

    return generated_source_ids


def _prune_stale_state_sources(state: WikiCompilerState, *, current_source_ids: set[str]) -> int:
    stale_source_ids = sorted(set(state.sources) - current_source_ids)
    for source_id in stale_source_ids:
        state.sources.pop(source_id, None)
        state.extracted_concepts.pop(source_id, None)
    return len(stale_source_ids)


def _relative_page_path(wiki_dir: Path, path: Path) -> str:
    return path.relative_to(wiki_dir).as_posix()

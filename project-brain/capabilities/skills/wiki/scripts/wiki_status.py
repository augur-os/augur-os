"""Aggregated operational status for the concept-first wiki."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import yaml

from skills.wiki.scripts.wiki_compound_policy import (
    MIN_COMPOUND_SOURCE_COUNT,
    target_source_count_label,
)
from skills.wiki.scripts.wiki_concept_state import (
    load_compiler_state,
    reconcile_state_from_compiled_wiki,
    source_is_already_bound,
    source_needs_extraction,
)
from skills.wiki.scripts.wiki_maintenance import lint_wiki
from skills.wiki.scripts.wiki_source_inventory import build_source_inventory
from src.config.paths import (
    get_compiled_wiki_dir,
    get_rag_category_dir,
    get_rag_dir,
    get_runtime_dir,
    get_vault_dir,
    resolve_wiki_dir,
)
from src.lib.frontmatter_utils import parse_frontmatter


def build_wiki_status(
    *,
    wiki_dir: Path | None = None,
    rag_dir: Path | None = None,
    runtime_wiki_dir: Path | None = None,
    rag_wiki_dir: Path | None = None,
) -> dict[str, Any]:
    """Return structure, compiler, batch, coverage, and index status for the wiki."""
    active_wiki_dir = Path(wiki_dir) if wiki_dir is not None else resolve_wiki_dir()
    resolved_wiki_dir = get_compiled_wiki_dir(active_wiki_dir)
    resolved_rag_dir = Path(rag_dir) if rag_dir is not None else get_rag_dir()
    resolved_runtime_wiki_dir = (
        Path(runtime_wiki_dir) if runtime_wiki_dir is not None else get_runtime_dir() / "wiki"
    )
    resolved_rag_wiki_dir = (
        Path(rag_wiki_dir) if rag_wiki_dir is not None else get_rag_category_dir("wiki")
    )

    lint = lint_wiki(wiki_dir=resolved_wiki_dir)
    sources = build_source_inventory(rag_dir=resolved_rag_dir, wiki_dir=resolved_wiki_dir)
    compiler_error: str | None = None
    try:
        state = load_compiler_state(resolved_runtime_wiki_dir)
    except (OSError, ValueError) as exc:
        compiler_error = str(exc)
        state = None

    state_repair: dict[str, Any] | None = None
    if state is not None:
        state_repair = reconcile_state_from_compiled_wiki(
            state,
            sources=sources,
            wiki_dir=resolved_wiki_dir,
        )
    compiler = _compiler_status(sources, state) if state is not None else _empty_compiler_status(sources)
    if state_repair and state_repair.get("changed"):
        compiler["state_repair"] = state_repair
    if compiler_error:
        compiler["error"] = compiler_error

    batches = _batch_status(resolved_runtime_wiki_dir)
    coverage = _coverage_status(sources, state)
    index = _index_status(resolved_rag_wiki_dir)
    structure = _structure_status(lint)
    compounding = {"queries": load_compounding_queries()}
    compounding_health = _compounding_health(resolved_wiki_dir, structure=structure)
    telemetry = _telemetry_block(resolved_runtime_wiki_dir)
    verdict = _status_verdict(
        structure_ok=bool(lint.get("ok")),
        compiler=compiler,
        batches=batches,
        coverage=coverage,
    )

    payload: dict[str, Any] = {
        "success": True,
        "verdict": verdict,
        "healthy": verdict == "healthy",
        "wiki_dir": str(resolved_wiki_dir),
        "runtime_wiki_dir": str(resolved_runtime_wiki_dir),
        "rag_wiki_dir": str(resolved_rag_wiki_dir),
        "structure": structure,
        "compiler": compiler,
        "batches": batches,
        "coverage": coverage,
        "index": index,
        "compounding": compounding,
        "compounding_health": compounding_health,
        "telemetry": telemetry,
        "signals_seen_by_tier": telemetry["signals_seen_by_tier"],
        "last_extraction_ts": telemetry["last_extraction_ts"],
        "tokens_spent_last_run": telemetry["tokens_spent_last_run"],
        "dropped_low_noise_count": telemetry["dropped_low_noise_count"],
        "actions": _recommended_actions(
            structure=structure,
            compiler=compiler,
            batches=batches,
            coverage=coverage,
            index=index,
            compounding_health=compounding_health,
        ),
    }
    payload.update(lint)
    return payload


def load_compounding_queries(vault_dir: Path | None = None) -> list[str]:
    """Return configured wiki compounding queries from the active wiki YAML."""
    if vault_dir is None:
        wiki_root = resolve_wiki_dir()
        candidates = [wiki_root / "queries.yaml", wiki_root / "config.yaml"]
    else:
        root = Path(vault_dir)
        candidates = [root / "wiki" / "queries.yaml", root / "wiki" / "config.yaml"]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        queries = _extract_compounding_queries(data)
        if queries:
            return queries
    return []


def _extract_compounding_queries(data: Any) -> list[str]:
    if isinstance(data, list):
        return [str(item).strip() for item in data if str(item).strip()]
    if not isinstance(data, dict):
        return []
    queries = data.get("queries")
    if isinstance(queries, list):
        return [str(item).strip() for item in queries if str(item).strip()]
    if isinstance(queries, dict):
        return [str(query_id).strip() for query_id in queries if str(query_id).strip()]
    compounding = data.get("compounding")
    if isinstance(compounding, dict):
        compounding_queries = compounding.get("queries")
        if isinstance(compounding_queries, list):
            return [str(item).strip() for item in compounding_queries if str(item).strip()]
    return []


def _structure_status(lint: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(lint.get("ok")),
        "pages": int(lint.get("pages", 0) or 0),
        "hubs": int(lint.get("hubs", 0) or 0),
        "missing_required": lint.get("missing_required", []),
        "missing_links": lint.get("missing_links", []),
        "orphan_pages": lint.get("orphan_pages", []),
        "duplicate_titles": lint.get("duplicate_titles", []),
        "broken_links": lint.get("broken_links", []),
        "legacy_pages": lint.get("legacy_pages", []),
        "duplicate_aliases": lint.get("duplicate_aliases", []),
        "schema_violations": lint.get("schema_violations", []),
    }


def _compiler_status(sources: list[Any], state: Any) -> dict[str, Any]:
    state_sources = getattr(state, "sources", {})
    source_ids = {source.source_id for source in sources}
    compiled = 0
    processed_no_concepts = 0
    pending_or_changed = 0
    by_kind: dict[str, int] = {}
    pending_by_kind: dict[str, int] = {}
    pending_by_family: dict[str, int] = {}

    for source in sources:
        by_kind[source.kind] = by_kind.get(source.kind, 0) + 1
        current_state = state_sources.get(source.source_id)
        is_pending = (
            not source_is_already_bound(state, source.source_id)
            and source_needs_extraction(state, source.source_id, source.checksum)
        )
        if is_pending:
            pending_or_changed += 1
            pending_by_kind[source.kind] = pending_by_kind.get(source.kind, 0) + 1
            family = _source_family(source)
            pending_by_family[family] = pending_by_family.get(family, 0) + 1
            continue
        if current_state is None:
            continue
        if getattr(current_state, "concept_slugs", []):
            compiled += 1
        else:
            processed_no_concepts += 1

    stale_or_missing = len(set(state_sources) - source_ids)
    return {
        "compiler_version": getattr(state, "compiler_version", ""),
        "sources_total": len(sources),
        "sources_in_state": len(state_sources),
        "sources_tracked_current": len(source_ids & set(state_sources)),
        "sources_compiled_with_concepts": compiled,
        "sources_processed_no_concepts": processed_no_concepts,
        "sources_pending_or_changed": pending_or_changed,
        "sources_stale_or_missing": stale_or_missing,
        "current": pending_or_changed == 0,
        "by_kind": dict(sorted(by_kind.items())),
        "pending_by_kind": dict(sorted(pending_by_kind.items())),
        "pending_by_family": dict(sorted(pending_by_family.items())),
    }


def _empty_compiler_status(sources: list[Any]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    pending_by_family: dict[str, int] = {}
    for source in sources:
        by_kind[source.kind] = by_kind.get(source.kind, 0) + 1
        family = _source_family(source)
        pending_by_family[family] = pending_by_family.get(family, 0) + 1
    return {
        "compiler_version": "",
        "sources_total": len(sources),
        "sources_in_state": 0,
        "sources_tracked_current": 0,
        "sources_compiled_with_concepts": 0,
        "sources_processed_no_concepts": 0,
        "sources_pending_or_changed": len(sources),
        "sources_stale_or_missing": 0,
        "current": len(sources) == 0,
        "by_kind": dict(sorted(by_kind.items())),
        "pending_by_kind": dict(sorted(by_kind.items())),
        "pending_by_family": dict(sorted(pending_by_family.items())),
    }


def _coverage_status(sources: list[Any], state: Any | None) -> dict[str, Any]:
    state_sources = getattr(state, "sources", {}) if state is not None else {}
    family_totals: dict[str, int] = {}
    family_compiled: dict[str, int] = {}

    for source in sources:
        family = _source_family(source)
        family_totals[family] = family_totals.get(family, 0) + 1
        source_state = state_sources.get(source.source_id)
        if source_state is None:
            continue
        if (
            not source_is_already_bound(state, source.source_id)
            and source_needs_extraction(state, source.source_id, source.checksum)
        ):
            continue
        if getattr(source_state, "concept_slugs", []):
            family_compiled[family] = family_compiled.get(family, 0) + 1

    uncovered = [
        {
            "family": family,
            "total": total,
            "compiled_with_concepts": family_compiled.get(family, 0),
            "uncovered": total - family_compiled.get(family, 0),
        }
        for family, total in sorted(family_totals.items())
        if total - family_compiled.get(family, 0) > 0
    ]
    uncovered.sort(key=lambda item: (-int(item["uncovered"]), str(item["family"])))
    total_sources = len(sources)
    compiled = sum(family_compiled.values())
    return {
        "concept_coverage_ratio": round(compiled / total_sources, 3) if total_sources else 1.0,
        "top_uncovered_source_families": uncovered[:5],
    }


def _batch_status(runtime_wiki_dir: Path) -> dict[str, Any]:
    batch_dir = runtime_wiki_dir / "concept-batches"
    batch_files = sorted(batch_dir.glob("*.json")) if batch_dir.is_dir() else []
    last_batch = max(batch_files, key=lambda path: path.stat().st_mtime) if batch_files else None
    last_batch_created = None
    last_batch_mode = None
    if last_batch is not None:
        try:
            payload = json.loads(last_batch.read_text(encoding="utf-8"))
            last_batch_created = payload.get("created")
            last_batch_mode = payload.get("mode")
        except (OSError, json.JSONDecodeError):
            last_batch_created = None
            last_batch_mode = None

    needs_update_flag = runtime_wiki_dir / "needs-update.flag"
    return {
        "batch_count": len(batch_files),
        "last_batch": str(last_batch) if last_batch is not None else None,
        "last_batch_handle": last_batch.stem if last_batch is not None else None,
        "last_batch_created": last_batch_created,
        "last_batch_mode": last_batch_mode,
        "needs_update": needs_update_flag.exists(),
        "needs_update_flag": str(needs_update_flag) if needs_update_flag.exists() else None,
    }


def _index_status(rag_wiki_dir: Path) -> dict[str, Any]:
    entries = list(rag_wiki_dir.rglob("*.md")) if rag_wiki_dir.is_dir() else []
    return {
        "wiki_rag_dir": str(rag_wiki_dir),
        "wiki_rag_entries": len(entries),
        "indexed": rag_wiki_dir.is_dir(),
    }


def _telemetry_block(runtime_wiki_dir: Path) -> dict[str, Any]:
    last_ts_path = runtime_wiki_dir / "last-extraction.ts"
    telemetry_path = runtime_wiki_dir / "telemetry.json"

    last_ts: float | None = None
    if last_ts_path.is_file():
        try:
            last_ts = float(last_ts_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            last_ts = None

    signals: dict[str, int] = {}
    tokens_spent: int | None = None
    dropped: int | None = None
    if telemetry_path.is_file():
        try:
            payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload.get("signals_seen_by_tier"), dict):
            signals = {
                str(key): int(value)
                for key, value in payload["signals_seen_by_tier"].items()
            }
        if "tokens_spent_last_run" in payload:
            try:
                tokens_spent = int(payload["tokens_spent_last_run"])
            except (TypeError, ValueError):
                tokens_spent = None
        if "dropped_low_noise_count" in payload:
            try:
                dropped = int(payload["dropped_low_noise_count"])
            except (TypeError, ValueError):
                dropped = None

    return {
        "last_extraction_ts": last_ts,
        "signals_seen_by_tier": signals,
        "tokens_spent_last_run": tokens_spent,
        "dropped_low_noise_count": dropped,
    }


def _compounding_health(wiki_dir: Path, *, structure: dict[str, Any]) -> dict[str, Any]:
    concept_pages = _concept_page_records(wiki_dir)
    source_counts = [int(page["source_count"]) for page in concept_pages]
    average_sources = round(sum(source_counts) / len(source_counts), 2) if source_counts else 0.0
    thin_pages = [
        {"page": str(page["page"]), "source_count": int(page["source_count"])}
        for page in concept_pages
        if 0 < int(page["source_count"]) < MIN_COMPOUND_SOURCE_COUNT
    ]
    duplicate_clusters = _duplicate_concept_clusters(concept_pages)
    return {
        "target_sources_per_page": target_source_count_label(),
        "minimum_sources_per_page": MIN_COMPOUND_SOURCE_COUNT,
        "concept_page_count": len(concept_pages),
        "average_sources_per_concept_page": average_sources,
        "thin_page_count": len(thin_pages),
        "thin_pages": thin_pages[:20],
        "thin_pages_truncated": len(thin_pages) > 20,
        "orphan_page_count": len(structure.get("orphan_pages", []) or []),
        "duplicate_concept_cluster_count": len(duplicate_clusters),
        "duplicate_concept_clusters": duplicate_clusters,
    }


def _concept_page_records(wiki_dir: Path) -> list[dict[str, Any]]:
    concepts_dir = wiki_dir / "concepts"
    if not concepts_dir.is_dir():
        return []

    records: list[dict[str, Any]] = []
    for path in sorted(concepts_dir.glob("*.md")):
        try:
            metadata, _body = parse_frontmatter(path)
        except (OSError, ValueError):
            continue
        if str(metadata.get("page_type") or "").strip() != "concept":
            continue
        sources = metadata.get("sources") or []
        if not isinstance(sources, list):
            sources = []
        aliases = metadata.get("aliases") or []
        if not isinstance(aliases, list):
            aliases = []
        records.append(
            {
                "page": path.relative_to(wiki_dir).as_posix(),
                "title": str(metadata.get("title") or path.stem),
                "aliases": [str(alias) for alias in aliases if str(alias).strip()],
                "source_count": len({str(source) for source in sources if str(source).strip()}),
            }
        )
    return records


def _duplicate_concept_clusters(concept_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pages_by_key: dict[str, set[str]] = {}
    for page in concept_pages:
        names = [str(page.get("title") or ""), *[str(item) for item in page.get("aliases", [])]]
        for name in names:
            key = _duplicate_key(name)
            if key:
                pages_by_key.setdefault(key, set()).add(str(page["page"]))

    clusters = [
        {"key": key, "pages": sorted(pages)}
        for key, pages in pages_by_key.items()
        if len(pages) > 1
    ]
    clusters.sort(key=lambda item: (str(item["key"]), item["pages"]))
    return clusters[:10]


def _duplicate_key(value: str) -> str:
    tokens = [
        token
        for token in re.split(r"[^a-z0-9]+", value.lower())
        if len(token) >= 3 and token not in {"and", "for", "the", "with"}
    ]
    return " ".join(tokens)


def _recommended_actions(
    *,
    structure: dict[str, Any],
    compiler: dict[str, Any],
    batches: dict[str, Any],
    coverage: dict[str, Any],
    index: dict[str, Any],
    compounding_health: dict[str, Any],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []

    if compiler.get("error"):
        actions.append(
            {
                "id": "repair-compiler-state",
                "priority": "critical",
                "tool": "wiki-reset",
                "command": "/wiki reset",
                "reason": "compiler state could not be loaded; reset rebuilds runtime compiler state from durable sources",
                "inputs": {"full_compile": False},
            }
        )
        return actions

    if not structure.get("ok"):
        actions.append(
            {
                "id": "inspect-structure",
                "priority": "critical",
                "tool": "wiki-lint",
                "command": "/wiki lint",
                "reason": "wiki structure has lint failures that should be inspected before compilation",
                "inputs": {},
            }
        )

    pending = int(compiler.get("sources_pending_or_changed", 0) or 0)
    if pending > 0:
        actions.append(
            {
                "id": "prepare-incremental-batch",
                "priority": "high",
                "tool": "wiki-update",
                "command": "/wiki update",
                "reason": f"{pending} {_pluralize('pending or changed source', pending)} need concept extraction",
                "inputs": {"limit": 20},
            }
        )
    elif batches.get("needs_update"):
        actions.append(
            {
                "id": "prepare-incremental-batch",
                "priority": "high",
                "tool": "wiki-update",
                "command": "/wiki update",
                "reason": "runtime needs-update.flag is present; prepare a bounded incremental concept batch",
                "inputs": {"limit": 20},
            }
        )

    pages = int(structure.get("pages", 0) or 0)
    indexed = bool(index.get("indexed"))
    wiki_rag_entries = int(index.get("wiki_rag_entries", 0) or 0)
    if pages > 0 and (not indexed or wiki_rag_entries == 0):
        actions.append(
            {
                "id": "refresh-wiki-index",
                "priority": "medium",
                "tool": "wiki-reindex",
                "command": "/wiki reindex",
                "reason": "compiled wiki pages are not indexed for browse/search",
                "inputs": {},
            }
        )

    if not actions and float(coverage.get("concept_coverage_ratio", 1.0) or 0.0) <= 0.0:
        actions.append(
            {
                "id": "rebuild-concepts",
                "priority": "medium",
                "tool": "wiki-rebuild",
                "command": "/wiki rebuild",
                "reason": "sources are current but no source has publishable concepts",
                "inputs": {"limit": 20},
            }
        )

    return actions


def _status_verdict(
    *,
    structure_ok: bool,
    compiler: dict[str, Any],
    batches: dict[str, Any],
    coverage: dict[str, Any],
) -> str:
    if compiler.get("error"):
        return "compiler_state_error"
    if not structure_ok:
        return "structure_broken"
    if int(compiler.get("sources_total", 0) or 0) == 0 and int(compiler.get("sources_in_state", 0) or 0) == 0:
        return "empty"
    if int(compiler.get("sources_pending_or_changed", 0) or 0) > 0 or batches.get("needs_update"):
        return "structure_ok_compile_backlog"
    if float(coverage.get("concept_coverage_ratio", 1.0) or 0.0) <= 0.0:
        return "current_low_coverage"
    return "healthy"


def _pluralize(label: str, count: int) -> str:
    return label if count == 1 else f"{label}s"


def _source_family(source: Any) -> str:
    metadata = getattr(source, "metadata", {})
    if isinstance(metadata, dict):
        family = str(metadata.get("source_family") or "").strip()
        if family:
            return family
    return str(getattr(source, "kind", "") or "unknown").strip() or "unknown"

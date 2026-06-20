"""Read-only wiki status from persisted runtime state only.

This module exposes ``read_persisted_wiki_status()`` which returns a
wiki status dict by reading persisted files from the runtime and RAG
directories — it does NOT invoke the live wiki engine (no imports from
the wiki skill bundle). This lets ``brain_insights.py`` (ingest skill)
surface wiki health without pulling in the full wiki dependency.

Fields populated from persisted state:
- ``compiler``    — from concept-compiler-state.json (sources_in_state,
                   sources_compiled_with_concepts, compiler_version, …)
- ``structure``   — page count from the compiled wiki dir (no live lint;
                   missing_links/orphan_pages left as empty lists)
- ``coverage``    — concept_coverage_ratio from compiler state
                   (top_uncovered_source_families left as [] — family
                   metadata is not in the persisted state)
- ``compounding_health`` — from a pure frontmatter scan of wiki concepts
- ``index``       — from RAG wiki dir file count
- ``batches``     — from concept-batches dir + needs-update.flag
- ``actions``     — derived from the above
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── local constants that mirror wiki_compound_policy ─────────────────────────
# Duplicated here to avoid a cross-bundle import (wiki skill ↔ src/lib).
_STATE_FILENAME = "concept-compiler-state.json"
_MIN_COMPOUND_SOURCE_COUNT = 8  # mirrors wiki_compound_policy.MIN_COMPOUND_SOURCE_COUNT
_TARGET_SOURCE_COUNT_LABEL = "10-15"  # mirrors wiki_compound_policy.target_source_count_label()


def read_persisted_wiki_status(
    *,
    runtime_wiki_dir: Path | None = None,
    rag_wiki_dir: Path | None = None,
) -> dict[str, Any]:
    """Return a wiki status dict populated from persisted runtime state.

    Reads ``concept-compiler-state.json``, wiki concept pages, and
    batch/flag files.  Does NOT import the wiki skill bundle or run any
    live scanning.  Falls back gracefully when dirs are absent.
    """
    from src.config.paths import (
        get_compiled_wiki_dir,
        get_rag_category_dir,
        get_runtime_dir,
        resolve_wiki_dir,
    )

    resolved_runtime_wiki_dir = Path(runtime_wiki_dir) if runtime_wiki_dir is not None else get_runtime_dir() / "wiki"
    resolved_rag_wiki_dir = Path(rag_wiki_dir) if rag_wiki_dir is not None else get_rag_category_dir("wiki")

    batches = _batch_status(resolved_runtime_wiki_dir)
    index = _index_status(resolved_rag_wiki_dir)

    raw_state = _load_compiler_state_raw(resolved_runtime_wiki_dir)
    compiler = _compiler_from_state(raw_state)
    coverage = _coverage_from_state(raw_state)

    # Pure file-scan for structure + compounding health
    try:
        wiki_dir: Path | None = get_compiled_wiki_dir(resolve_wiki_dir())
    except Exception:  # noqa: BLE001
        wiki_dir = None
    structure = _structure_from_wiki_dir(wiki_dir)
    compounding_health = _compounding_health_from_wiki_dir(wiki_dir, structure=structure)

    # Simplified verdict derivable from persisted data
    sources_in_state = int(compiler.get("sources_in_state", 0) or 0)
    if sources_in_state == 0:
        verdict = "empty"
    elif batches.get("needs_update"):
        verdict = "structure_ok_compile_backlog"
    elif float(coverage.get("concept_coverage_ratio", 0.0) or 0.0) <= 0.0:
        verdict = "current_low_coverage"
    else:
        verdict = "healthy"

    actions = _recommended_actions(
        structure=structure,
        compiler=compiler,
        batches=batches,
        coverage=coverage,
        index=index,
        compounding_health=compounding_health,
    )

    return {
        "verdict": verdict,
        "healthy": True,
        "structure": structure,
        "compiler": compiler,
        "coverage": coverage,
        "index": index,
        "batches": batches,
        "compounding_health": compounding_health,
        "actions": actions,
    }


# ── persisted compiler state ──────────────────────────────────────────────────


def _load_compiler_state_raw(runtime_wiki_dir: Path) -> dict[str, Any]:
    """Read concept-compiler-state.json as raw JSON — no skill-bundle imports."""
    state_file = runtime_wiki_dir / _STATE_FILENAME
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))  # type: ignore[return-value]
    except (OSError, json.JSONDecodeError):
        return {}


def _compiler_from_state(raw_state: dict[str, Any]) -> dict[str, Any]:
    """Derive compiler status dict from the raw persisted state JSON."""
    sources = raw_state.get("sources") or {}
    if not isinstance(sources, dict):
        sources = {}

    compiled_with_concepts = 0
    processed_no_concepts = 0
    for src_data in sources.values():
        if not isinstance(src_data, dict):
            continue
        slugs = src_data.get("concept_slugs") or []
        if isinstance(slugs, list) and slugs:
            compiled_with_concepts += 1
        else:
            processed_no_concepts += 1

    sources_in_state = len(sources)
    return {
        "compiler_version": str(raw_state.get("compiler_version") or ""),
        # sources_total mirrors sources_in_state — live source scan not available here
        "sources_total": sources_in_state,
        "sources_in_state": sources_in_state,
        "sources_tracked_current": sources_in_state,
        "sources_compiled_with_concepts": compiled_with_concepts,
        "sources_processed_no_concepts": processed_no_concepts,
        # pending/stale/current cannot be determined without live sources
        "sources_pending_or_changed": 0,
        "sources_stale_or_missing": 0,
        "current": None,
        "by_kind": {},
        "pending_by_kind": {},
        "pending_by_family": {},
    }


def _coverage_from_state(raw_state: dict[str, Any]) -> dict[str, Any]:
    """Derive coverage from the persisted compiler state."""
    sources = raw_state.get("sources") or {}
    if not isinstance(sources, dict):
        return {"concept_coverage_ratio": 0.0, "top_uncovered_source_families": []}

    total = len(sources)
    compiled = sum(
        1
        for src in sources.values()
        if isinstance(src, dict) and isinstance(src.get("concept_slugs"), list) and src.get("concept_slugs")
    )
    return {
        "concept_coverage_ratio": round(compiled / total, 3) if total else 1.0,
        # family metadata is not persisted in the state file
        "top_uncovered_source_families": [],
    }


# ── structure: pure wiki-dir file count (no live lint) ────────────────────────


def _structure_from_wiki_dir(wiki_dir: Path | None) -> dict[str, Any]:
    """Count wiki pages from the compiled wiki directory (no live lint)."""
    if wiki_dir is None or not wiki_dir.is_dir():
        return {"ok": False, "pages": 0, "missing_links": [], "orphan_pages": []}
    pages = list(wiki_dir.rglob("*.md"))
    return {
        "ok": len(pages) > 0,
        "pages": len(pages),
        # missing_links / orphan_pages require live lint — not available here
        "missing_links": [],
        "orphan_pages": [],
    }


# ── compounding health: pure frontmatter scan ─────────────────────────────────


def _compounding_health_from_wiki_dir(
    wiki_dir: Path | None,
    *,
    structure: dict[str, Any],
) -> dict[str, Any]:
    """Compute compounding health by scanning wiki concept-page frontmatter."""
    concept_pages = _concept_page_records(wiki_dir) if wiki_dir else []
    source_counts = [int(page["source_count"]) for page in concept_pages]
    average_sources = round(sum(source_counts) / len(source_counts), 2) if source_counts else 0.0
    thin_pages = [
        {"page": str(page["page"]), "source_count": int(page["source_count"])}
        for page in concept_pages
        if 0 < int(page["source_count"]) < _MIN_COMPOUND_SOURCE_COUNT
    ]
    return {
        "concept_page_count": len(concept_pages),
        "average_sources_per_concept_page": average_sources,
        "thin_page_count": len(thin_pages),
        "target_sources_per_page": _TARGET_SOURCE_COUNT_LABEL,
    }


def _concept_page_records(wiki_dir: Path) -> list[dict[str, Any]]:
    """Read concept page source counts from frontmatter (pure file scan)."""
    from src.lib.frontmatter_utils import parse_frontmatter

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
        records.append(
            {
                "page": path.relative_to(wiki_dir).as_posix(),
                "source_count": len({str(s) for s in sources if str(s).strip()}),
            }
        )
    return records


# ── batch / index helpers (unchanged from original) ──────────────────────────


def _batch_status(runtime_wiki_dir: Path) -> dict[str, Any]:
    batch_dir = runtime_wiki_dir / "concept-batches"
    batch_files = sorted(batch_dir.glob("*.json")) if batch_dir.is_dir() else []
    last_batch = max(batch_files, key=lambda p: p.stat().st_mtime) if batch_files else None
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


# ── recommended actions ───────────────────────────────────────────────────────


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

    pending = int(compiler.get("sources_pending_or_changed", 0) or 0)
    if pending > 0:
        actions.append(
            {
                "id": "prepare-incremental-batch",
                "priority": "high",
                "tool": "wiki-update",
                "command": "/wiki update",
                "reason": (
                    f"{pending} pending or changed "
                    f"{'source' if pending == 1 else 'sources'} need concept extraction"
                ),
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
                "reason": ("runtime needs-update.flag is present; " "prepare a bounded incremental concept batch"),
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

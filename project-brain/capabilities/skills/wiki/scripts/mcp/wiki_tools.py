"""MCP tool definitions for wiki operations and ask compounding inputs."""
from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import yaml

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_skill_root = Path(__file__).resolve().parents[2]
_scripts_dir = _skill_root / "scripts"
if str(_skill_root) not in sys.path:
    sys.path.insert(0, str(_skill_root))
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

try:
    from src.mcp.augur_shared.logging import get_entity_logger
    from src.mcp.augur_shared.annotations import tool_annotations
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        return importlib.import_module("logging").getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

from skills.wiki.scripts.wiki_concept_compiler import (
    PROMPT_PREVIEW_LIMIT as PROMPT_PREVIEW_LIMIT,
    apply_extraction_batch,
    prepare_extraction_batch,
    summarize_extraction_batch,
    write_extraction_batch_file,
)
from src.config.paths import (
    get_compiled_wiki_dir,
    get_runtime_dir,
    get_wiki_dir,
    get_wiki_signals_config_path,
    resolve_wiki_dir,
)
from skills.wiki.scripts.wiki_concept_state import (
    WikiCompilerState,
    load_compiler_state,
    reconcile_state_from_compiled_wiki,
    save_compiler_state,
    source_is_already_bound,
    source_needs_extraction,
)
from skills.wiki.scripts.wiki_extraction_guard import should_skip, write_last_ts
from skills.wiki.scripts.wiki_source_inventory import build_source_inventory
from skills.wiki.scripts.wiki_status import build_wiki_status
from skills.wiki.scripts.wiki_signals_config import load_config as load_wiki_signals
from skills.wiki.scripts.wiki_tier import tier_for_surface, tier_meets_filter, weight_for_tier
from skills.wiki.scripts.wiki_tier_caps import apply_tier_caps
from skills.wiki.scripts.mcp.wiki_queries_tools import register_wiki_queries_tools
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.wiki_utils import WIKILINK_RE

try:
    from skills.wiki.scripts.wiki_reset import run_wiki_reset
except ImportError:
    run_wiki_reset = None  # type: ignore[assignment]

logger = get_entity_logger("wiki")

_wiki_pages = None
_scanner = None


def _write_report_sidecar(*, html_path: Path, slug: str, stats: dict[str, Any], today: str) -> Path:
    """Write the ADR-723 sidecar next to the HTML report."""
    sidecar_path = html_path.with_suffix("").with_suffix(".meta.yaml")
    n_pages = stats.get("total_pages", stats.get("pages", 0))
    n_hubs = stats.get("total_hubs", stats.get("hubs", 0))
    n_sources = stats.get("total_sources", stats.get("sources", 0))
    n_words = stats.get("total_words", stats.get("words", 0))
    n_cross = stats.get("total_cross_refs", stats.get("cross_refs", 0))

    sidecar = {
        "slug": slug,
        "title": f"Second Brain Intelligence Report - {today}",
        "kind": "generated",
        "hub": "brain",
        "source": {
            "type": "agent-synthesized",
            "origin": (
                f"Augur wiki snapshot - {n_pages} pages across {n_hubs} hubs, "
                f"{n_sources} sources, {n_words} words, {n_cross} cross-references"
            ),
            "generator": (
                "project-brain/capabilities/skills/wiki/scripts/mcp/wiki_tools.py + "
                "agent-step synthesis per /wiki report"
            ),
        },
        "tags": ["wiki", "report", "second-brain"],
        "created_at": datetime.now(UTC).isoformat(),
        "notes": "",
    }
    sidecar_path.write_text(yaml.safe_dump(sidecar, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return sidecar_path


def _generate_report_html(report: dict[str, Any], output_dir: str = "") -> str:
    """Render rich-dict report to HTML, PDF, and ADR-723 sidecar.

    Pre-condition: ``validate_rich_dict(report).success`` is true.
    """
    from datetime import date

    from skills.wiki.scripts.wiki_report import ReportData
    from skills.wiki.scripts.wiki_report_charts import (
        render_hub_distribution,
        render_knowledge_graph,
        render_radar_chart,
    )
    from skills.wiki.scripts.wiki_report_render import render_html, render_pdf
    from src.config.paths import get_documents_dir, get_runtime_dir

    report_hubs = report.get("hubs")
    if not isinstance(report_hubs, dict):
        report_hubs = {
            h["name"]: {
                "page_count": 0,
                "source_count": h.get("source_count", 0),
                "word_count": 0,
                "tags": [],
            }
            for h in report.get("hub_sections", [])
            if isinstance(h, dict) and "name" in h
        }
    report_pages = report.get("pages")
    report_connections = report.get("connections")
    data = ReportData(
        stats=report.get("stats", {}),
        hubs=report_hubs,
        pages=report_pages if isinstance(report_pages, list) else [],
        connections=report_connections if isinstance(report_connections, list) else [],
        portfolio=report.get("portfolio", {}),
    )

    chart_dir = get_runtime_dir() / "wiki" / "report-assets"
    chart_dir.mkdir(parents=True, exist_ok=True)
    report["charts"] = {
        "radar": str(render_radar_chart(data, output_dir=chart_dir)),
        "graph": str(render_knowledge_graph(data, output_dir=chart_dir)),
        "distribution": str(render_hub_distribution(data, output_dir=chart_dir)),
    }

    out = Path(output_dir) if output_dir else (get_documents_dir() / "brain" / "artifacts")
    out.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    slug = f"second-brain-report-{today}"

    template_dir = _skill_root / "assets" / "templates"
    html_path = render_html(report, output_path=out / f"{slug}.html", template_dir=template_dir)
    pdf_path = render_pdf(report, output_path=out / f"{slug}.pdf")
    sidecar_path = _write_report_sidecar(
        html_path=html_path,
        slug=slug,
        stats=report.get("stats", {}),
        today=today,
    )

    return json.dumps(
        {
            "success": True,
            "pdf_path": str(pdf_path),
            "html_path": str(html_path),
            "sidecar_path": str(sidecar_path),
        },
        indent=2,
    )


def _get_wiki_pages():
    global _wiki_pages
    if _wiki_pages is None:
        from skills.wiki.scripts.wiki_pages import WikiPages
        try:
            from src.config.paths import get_runtime_dir
            runtime_wiki = get_runtime_dir() / "wiki"
            wiki_dir = get_compiled_wiki_dir(resolve_wiki_dir())
        except ImportError:
            runtime_wiki = Path.home() / "Library" / "Application Support" / "Augur" / "state" / "wiki"
            wiki_dir = get_compiled_wiki_dir(resolve_wiki_dir())
        _wiki_pages = WikiPages(wiki_dir=wiki_dir, runtime_wiki_dir=runtime_wiki)
    return _wiki_pages


def _get_scanner():
    global _scanner
    if _scanner is None:
        from skills.wiki.scripts.wiki_scanner import WikiScanner
        try:
            from src.lib.ingest.ask_sync import load_recent_ask_outcomes
            from src.config.paths import (
                get_documents_dir,
                get_logs_dir,
                get_project_root,
                get_runtime_dir,
                get_vault_dir,
            )
            _scanner = WikiScanner(
                vault_dir=get_vault_dir(),
                documents_dir=get_documents_dir(),
                project_root=get_project_root(),
                runtime_dir=get_runtime_dir(),
                logs_dir=get_logs_dir(),
                ask_outcomes_loader=load_recent_ask_outcomes,
            )
        except ImportError:
            _scanner = WikiScanner(
                vault_dir=Path.home() / "Au-vault",
                documents_dir=Path.home() / "Documents",
            )
    return _scanner


def _aggregate_wiki_dashboard_stats(wiki_dir: Path) -> dict[str, Any]:
    """Fast wiki stats for dashboard cards without full source freshness scans."""
# TODO_CLEANUP: This file is 987 lines — consider splitting into smaller modules
    from skills.wiki.scripts.wiki_quality import assess_page_quality
    from skills.wiki.scripts.wiki_schema import lint_penalties

    pages: list[dict[str, Any]] = []
    connections: list[tuple[str, str]] = []
    all_sources: set[str] = set()
    total_words = 0
    semantic_quality_flags = {
        "raw_metadata_evidence",
        "duplicate_physical_sources",
        "catch_all_page",
        "non_synthetic_overview",
        "missing_source_fingerprint",
        "unsupported_domain_abstraction",
    }

    if wiki_dir.is_dir():
        for md_file in sorted(wiki_dir.rglob("*.md")):
            if not md_file.is_file():
                continue
            rel = md_file.relative_to(wiki_dir)
            if rel.parent == Path(".") and rel.name in {"index.md", "overview.md"}:
                continue
            try:
                meta, body = parse_frontmatter(md_file)
            except Exception:
                continue

            page_key = str(rel.with_suffix(""))
            page_hub = str(meta.get("hub") or "general")
            sources = meta.get("sources", []) if isinstance(meta.get("sources"), list) else []
            all_sources.update(str(source) for source in sources)
            direct_targets = {
                match.group(1).strip()
                for match in WIKILINK_RE.finditer(body)
                if match.group(1).strip()
            }
            for target in direct_targets:
                connections.append((page_key, target))

            word_count = len(body.split())
            total_words += word_count
            quality = assess_page_quality(
                page=page_key,
                page_type=str(meta.get("page_type") or ""),
                hub=page_hub,
                tags=meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
                sources=sources,
                body=body,
                cross_ref_count=len(direct_targets),
                compiler_version=str(meta.get("compiler_version") or ""),
            )
            if not meta.get("source_fingerprint") and str(meta.get("page_type") or "") in {"concept", "query", "overview"}:
                quality_flags = list(quality.get("quality_flags", []))
                quality_flags.append("missing_source_fingerprint")
                quality["quality_flags"] = quality_flags
                penalty = int(lint_penalties().get("missing_source_fingerprint", 0))
                quality["quality_score"] = max(int(quality.get("quality_score", 0)) - penalty, 0)

            pages.append(
                {
                    "page": page_key,
                    "hub": page_hub,
                    "word_count": word_count,
                    "sources": sources,
                    "has_source_fingerprint": bool(meta.get("source_fingerprint")),
                    **quality,
                }
            )

    page_keys = {page["page"] for page in pages}
    incoming_counts = {page["page"]: 0 for page in pages}
    outgoing_counts = {page["page"]: 0 for page in pages}
    for source, target in connections:
        outgoing_counts[source] = outgoing_counts.get(source, 0) + 1
        if target in page_keys:
            incoming_counts[target] = incoming_counts.get(target, 0) + 1

    isolated_pages = sum(
        1
        for page in pages
        if incoming_counts.get(page["page"], 0) == 0 or outgoing_counts.get(page["page"], 0) == 0
    )
    rewrite_candidates = sum(
        1
        for page in pages
        if page.get("quality_score", 100) < 75
        or "inventory_style" in page.get("quality_flags", [])
        or semantic_quality_flags.intersection(set(page.get("quality_flags", [])))
    )
    semantic_quality_defects = sum(
        len(semantic_quality_flags.intersection(set(page.get("quality_flags", []))))
        for page in pages
    )
    avg_quality_score = (
        round(sum(page.get("quality_score", 0) for page in pages) / len(pages), 2)
        if pages
        else 0.0
    )

    return {
        "total_pages": len(pages),
        "total_hubs": len({page["hub"] for page in pages}),
        "total_sources": len(all_sources),
        "total_words": total_words,
        "total_cross_refs": len(connections),
        "avg_outgoing_links_per_page": round(len(connections) / len(pages), 2) if pages else 0.0,
        "isolated_pages": isolated_pages,
        "stale_pages": 0,
        "pages_missing_source_fingerprint": sum(1 for page in pages if not page.get("has_source_fingerprint")),
        "filtered_noise_sources": 0,
        "avg_quality_score": avg_quality_score,
        "rewrite_candidates": rewrite_candidates,
        "semantic_quality_defects": semantic_quality_defects,
    }


def _reset_cached_wiki_handles() -> None:
    global _wiki_pages, _scanner
    _wiki_pages = None
    _scanner = None


def _concept_batch_instructions() -> str:
    return (
        "Read full extraction prompts from batch.batch_file. Run each prompt with an agent LLM. "
        "Build a JSON object mapping each source_id to a list of extracted concept objects, then call "
        "wiki-apply-concept-batch with that object serialized as payloads_json. "
        "Use an empty list for sources with no durable concepts."
    )


def _serialize_extraction_batch(batch: Any, *, runtime_wiki_dir: Path, mode: str) -> dict[str, Any]:
    batch_file = write_extraction_batch_file(runtime_wiki_dir, batch, mode=mode)
    return summarize_extraction_batch(batch, batch_file=batch_file)


def _batch_backlog_summary(
    sources: list[Any],
    state: WikiCompilerState,
    batch: Any,
    *,
    limit: int,
) -> dict[str, int]:
    pending_count = sum(
        1
        for source in sources
        if not source_is_already_bound(state, source.source_id)
        and source_needs_extraction(state, source.source_id, source.checksum)
    )
    batch_count = len(getattr(batch, "items", []) or [])
    return {
        "sources_total": len(sources),
        "sources_pending_or_changed": pending_count,
        "batch_count": batch_count,
        "remaining_after_batch": max(pending_count - batch_count, 0),
        "limit": limit,
    }


def _source_metadata(source: Any) -> dict[str, Any]:
    metadata = getattr(source, "metadata", {}) or {}
    return dict(metadata) if isinstance(metadata, dict) else {}


def _source_surface(source: Any) -> str:
    metadata = _source_metadata(source)
    surface = str(metadata.get("source_surface") or "").strip()
    if surface:
        return surface
    kind = str(getattr(source, "kind", "") or "").strip()
    return kind or "medium"


def _source_tier(source: Any) -> str:
    metadata = _source_metadata(source)
    tier = str(metadata.get("tier") or "").strip().lower()
    return tier or tier_for_surface(_source_surface(source))


def _source_weight(source: Any) -> float:
    metadata = _source_metadata(source)
    raw = metadata.get("weight")
    if raw is not None:
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
    return weight_for_tier(_source_tier(source))


def _annotate_source_for_priority(source: Any) -> Any:
    """Return a SourceDescriptor with tier metadata filled when possible."""
    metadata = _source_metadata(source)
    tier = str(metadata.get("tier") or "").strip().lower() or tier_for_surface(_source_surface(source))
    weight = _source_weight(source)
    if metadata.get("tier") == tier and metadata.get("weight") == weight:
        return source
    try:
        from skills.wiki.scripts.wiki_concept_models import SourceDescriptor

        if isinstance(source, SourceDescriptor):
            return SourceDescriptor(
                source_id=source.source_id,
                kind=source.kind,
                title=source.title,
                source_path=source.source_path,
                checksum=source.checksum,
                modified_at=source.modified_at,
                priority=source.priority,
                metadata={**metadata, "tier": tier, "weight": weight, "source_surface": _source_surface(source)},
            )
    except Exception:
        return source
    return source


def _filter_order_and_cap_sources(
    sources: list[Any],
    *,
    tier: str,
    tier_caps: dict[str, int],
) -> tuple[list[Any], int]:
    annotated = [_annotate_source_for_priority(source) for source in sources]
    filtered = [source for source in annotated if tier_meets_filter(_source_tier(source), tier)]
    dropped_count = len(annotated) - len(filtered)
    filtered.sort(
        key=lambda source: (
            -_source_weight(source),
            str(getattr(source, "modified_at", "") or ""),
            str(getattr(source, "source_id", "") or ""),
        )
    )
    return apply_tier_caps(filtered, tier_caps), dropped_count


def _pending_sources(sources: list[Any], state: WikiCompilerState) -> list[Any]:
    return [
        source
        for source in sources
        if not source_is_already_bound(state, source.source_id)
        and source_needs_extraction(state, source.source_id, source.checksum)
    ]


def _should_report_no_change(
    *,
    sources: list[Any],
    pending_sources: list[Any],
    last_ts_path: Path,
) -> bool:
    """Only skip when there is no unapplied extraction work hidden by the timestamp."""
    if pending_sources:
        return False
    return should_skip(sources, last_ts_path)


def _signal_counts_by_tier(sources: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source in sources:
        tier = _source_tier(source)
        counts[tier] = counts.get(tier, 0) + 1
    return dict(sorted(counts.items()))


def _write_wiki_update_telemetry(
    runtime_wiki_dir: Path,
    *,
    sources: list[Any],
    dropped_count: int,
    tokens_spent: int | None = None,
) -> None:
    runtime_wiki_dir.mkdir(parents=True, exist_ok=True)
    telemetry_path = runtime_wiki_dir / "telemetry.json"
    telemetry_path.write_text(
        json.dumps(
            {
                "signals_seen_by_tier": _signal_counts_by_tier(sources),
                "tokens_spent_last_run": int(tokens_spent or 0),
                "dropped_low_noise_count": int(dropped_count),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _concept_batch_next_steps(batch_summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "read-batch-file",
            "description": "Read the full extraction prompts from the persisted batch file.",
            "path": batch_summary.get("batch_file", ""),
        },
        {
            "id": "extract-concepts",
            "description": "Run each prompt with an IDE or CLI agent and build source_id keyed concept JSON.",
        },
        {
            "id": "apply-concepts",
            "description": "Apply the extracted concept payloads through the compiler.",
            "tool": "wiki-apply-concept-batch",
            "argument": "payloads_json",
        },
        {
            "id": "check-remaining-status",
            "description": "Check remaining compiler backlog and follow-up actions.",
            "tool": "wiki-status",
        },
    ]


def _post_apply_status_summary(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": status.get("verdict", ""),
        "healthy": bool(status.get("healthy", False)),
        "compiler": status.get("compiler", {}),
        "batches": status.get("batches", {}),
        "compounding_health": status.get("compounding_health", {}),
        "actions": status.get("actions", []),
    }


def _parse_extraction_payloads(payloads_json: str) -> tuple[dict[str, list[dict[str, Any]]] | None, str | None]:
    try:
        payload = json.loads(payloads_json or "{}")
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON in payloads_json: {exc}"

    if not isinstance(payload, dict):
        return None, "payloads_json must be a top-level JSON object mapping source IDs to concept lists"

    parsed: dict[str, list[dict[str, Any]]] = {}
    for source_id, concepts in payload.items():
        if not isinstance(source_id, str) or not source_id.strip():
            return None, "payloads_json keys must be non-empty source ID strings"
        if not isinstance(concepts, list):
            return None, f"payloads_json value for {source_id} must be a list"
        normalized_concepts: list[dict[str, Any]] = []
        for index, concept in enumerate(concepts):
            if not isinstance(concept, dict):
                return None, f"payloads_json value for {source_id}[{index}] must be an object"
            normalized_concepts.append(concept)
        parsed[source_id] = normalized_concepts
    return parsed, None


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _refresh_concept_runtime_metadata(wiki_dir: Path, runtime_wiki_dir: Path) -> dict[str, Any]:
    """Refresh runtime wiki metadata without rewriting concept-first support pages."""
    pages_data: dict[str, Any] = {}
    if wiki_dir.exists():
        for md_file in sorted(wiki_dir.rglob("*.md")):
            rel = md_file.relative_to(wiki_dir)
            if _is_root_system_page(rel):
                continue

            metadata, body = parse_frontmatter(md_file)
            if _is_legacy_wiki_page(rel, metadata):
                continue
            page_key = rel.with_suffix("").as_posix()
            title = str(metadata.get("title") or md_file.stem.replace("-", " ").title()).strip()
            page_type = str(metadata.get("page_type") or metadata.get("type") or "wiki-page").strip()
            fallback_hub = rel.parts[0] if len(rel.parts) > 1 else "general"
            hub = str(metadata.get("hub") or fallback_hub).strip()
            summary = str(metadata.get("summary") or _first_body_paragraph(body)).strip()
            pages_data[page_key] = {
                "type": metadata.get("type", "wiki-page"),
                "hub": hub,
                "tags": metadata.get("tags", []),
                "title": title,
                "sources": metadata.get("sources", []),
                "page_type": page_type,
                "updated": metadata.get("updated", ""),
            }
            if summary:
                pages_data[page_key]["summary"] = summary

    runtime_wiki_dir.mkdir(parents=True, exist_ok=True)
    tags_path = runtime_wiki_dir / "tags.yaml"
    tags_path.write_text(
        yaml.dump(
            {"pages": pages_data},
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    return {"tags_path": str(tags_path), "pages_indexed": len(pages_data)}


def _clear_needs_update_flag(runtime_wiki_dir: Path) -> bool:
    flag_path = Path(runtime_wiki_dir) / "needs-update.flag"
    if not flag_path.exists():
        return False
    flag_path.unlink()
    return True


async def _run_wiki_update(limit: int = 20, tier: str = "") -> str:
    """Pure-Python entry point for wiki-update."""
    try:
        from src.config.paths import get_rag_dir, get_runtime_dir, resolve_wiki_dir

        wiki_dir = resolve_wiki_dir()
        runtime_wiki_dir = get_runtime_dir() / "wiki"
        signals_cfg = load_wiki_signals(get_wiki_signals_config_path())
        requested_limit = max(int(limit), 0)
        effective_limit = (
            signals_cfg.extraction_limit
            if requested_limit <= 0
            else min(requested_limit, signals_cfg.extraction_limit)
        )

        raw_sources = build_source_inventory(rag_dir=get_rag_dir(), wiki_dir=wiki_dir)
        sources, dropped_count = _filter_order_and_cap_sources(
            raw_sources,
            tier=tier or "",
            tier_caps=signals_cfg.tier_caps,
        )
        state = load_compiler_state(runtime_wiki_dir)
        state_repair = reconcile_state_from_compiled_wiki(
            state,
            sources=raw_sources,
            wiki_dir=wiki_dir,
        )
        if state_repair.get("changed"):
            save_compiler_state(runtime_wiki_dir, state)
        pending_sources = _pending_sources(sources, state)
        last_ts_path = runtime_wiki_dir / "last-extraction.ts"

        if _should_report_no_change(
            sources=sources,
            pending_sources=pending_sources,
            last_ts_path=last_ts_path,
        ):
            _write_wiki_update_telemetry(
                runtime_wiki_dir,
                sources=sources,
                dropped_count=dropped_count,
                tokens_spent=0,
            )
            return json.dumps(
                {
                    "success": True,
                    "status": "no_change",
                    "mode": "update",
                    "tier": tier or "",
                    "sources_considered": len(sources),
                    "dropped_low_noise_count": dropped_count,
                    "limit": effective_limit,
                    "state_repair": state_repair if state_repair.get("changed") else None,
                },
                indent=2,
                default=str,
            )

        weight_by_source_id = {source.source_id: _source_weight(source) for source in sources}
        batch = prepare_extraction_batch(
            sources,
            state,
            limit=effective_limit,
            weight_by_source_id=weight_by_source_id,
        )
        batch_summary = _serialize_extraction_batch(
            batch,
            runtime_wiki_dir=runtime_wiki_dir,
            mode="update",
        )
        backlog = _batch_backlog_summary(sources, state, batch, limit=effective_limit)
        needs_update_cleared = False
        status = "agent_action_required"
        next_steps = _concept_batch_next_steps(batch_summary)
        instructions = _concept_batch_instructions()
        batch_count = int(backlog.get("batch_count", 0) or 0)

        if backlog["sources_pending_or_changed"] == 0 and batch_count == 0:
            needs_update_cleared = _clear_needs_update_flag(runtime_wiki_dir)
            status = "current"
            next_steps = [
                {
                    "id": "check-remaining-status",
                    "description": "Check wiki health after the no-op update.",
                    "tool": "wiki-status",
                }
            ]
            instructions = "No changed wiki sources were found. Stale needs-update flags are cleared automatically."

        _write_wiki_update_telemetry(
            runtime_wiki_dir,
            sources=sources,
            dropped_count=dropped_count,
            tokens_spent=0,
        )
        return json.dumps(
            {
                "success": True,
                "status": status,
                "mode": "update",
                "tier": tier or "",
                "batch": batch_summary,
                "backlog": backlog,
                "next_steps": next_steps,
                "instructions": instructions,
                "needs_update_cleared": needs_update_cleared,
                "dropped_low_noise_count": dropped_count,
                "state_repair": state_repair if state_repair.get("changed") else None,
            },
            indent=2,
            default=str,
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


async def _run_wiki_migrate_v4(apply: bool = False) -> str:
    """Pure-Python entry point for the ADR-740 v3-to-v4 wiki migration."""
    from skills.wiki.scripts.wiki_v4_migration import migrate_wiki_dir

    normalized_apply = bool(apply)
    result = migrate_wiki_dir(
        wiki_dir=resolve_wiki_dir(),
        runtime_dir=get_runtime_dir(),
        apply=normalized_apply,
    )
    return json.dumps(
        {
            "success": True,
            "apply": normalized_apply,
            "changed_pages": [str(path) for path in result.changed_pages],
            "backup_dir": str(result.backup_dir) if result.backup_dir else None,
            "diffs": result.diffs,
            "skipped_pages": [str(path) for path in result.skipped_pages],
            "warnings": result.warnings,
        },
        indent=2,
        default=str,
    )


def _is_root_system_page(rel: Path) -> bool:
    return rel.parent == Path(".") and rel.name in {"index.md", "overview.md", "log.md"}


def _is_legacy_wiki_page(rel: Path, metadata: dict[str, Any]) -> bool:
    if rel.parts and rel.parts[0] == "sources":
        return True
    return str(metadata.get("page_type") or "").strip() in {"source-summary", "query-output"}


def _first_body_paragraph(body: str) -> str:
    for paragraph in body.split("\n\n"):
        text = " ".join(line.strip() for line in paragraph.splitlines() if line.strip())
        if text and not text.startswith("#") and not text.startswith("- "):
            return text
    return ""


def register_wiki_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register wiki MCP tools."""
    register_wiki_queries_tools(mcp, mcp_tool_interceptor, metrics)

    @mcp.tool(
        name="wiki-read",
        annotations=tool_annotations({"title": "Wiki Read", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_read(page: str = "") -> str:
        """Read a wiki page by hub-relative path (e.g., 'finance/budgeting')."""
        metrics.track_tool("wiki_read", skill="wiki")
        try:
            result = _get_wiki_pages().read(page)
            if result is None:
                return json.dumps({"success": False, "error": f"Page not found: {page}"})
            return json.dumps({"success": True, **result}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-write",
        annotations=tool_annotations({"title": "Wiki Write", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_write(
        page: str = "", title: str = "", tags: str = "[]",
        sources: str = "[]", body: str = "", hub: str = "",
    ) -> str:
        """Write or update a wiki page. Creates hub directory if needed."""
        metrics.track_tool("wiki_write", skill="wiki")
        try:
            parsed_tags = json.loads(tags) if isinstance(tags, str) else tags
            parsed_sources = json.loads(sources) if isinstance(sources, str) else sources
            path = _get_wiki_pages().write(
                page=page, title=title, tags=parsed_tags,
                sources=parsed_sources, body=body, hub=hub,
            )
            return json.dumps({"success": True, "path": str(path), "created_or_updated": "ok"}, indent=2)
        except Exception as exc:
            logger.error("wiki-write failed: %s", exc, exc_info=True)
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-list",
        annotations=tool_annotations({"title": "Wiki List", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_list(hub: str = "") -> str:
        """List all wiki pages, optionally filtered by hub."""
        metrics.track_tool("wiki_list", skill="wiki")
        try:
            pages = _get_wiki_pages().list_pages(hub=hub or None)
            return json.dumps({"success": True, "pages": pages, "count": len(pages)}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-tags",
        annotations=tool_annotations({"title": "Wiki Tags", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_tags() -> str:
        """Read the tag manifest — maps pages to their tags for fast matching."""
        metrics.track_tool("wiki_tags", skill="wiki")
        try:
            tags = _get_wiki_pages().read_tags()
            return json.dumps({"success": True, **tags}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-log",
        annotations=tool_annotations({"title": "Wiki Log", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_log(entry: str = "") -> str:
        """Append a session summary to the wiki log (rolling 30 entries)."""
        metrics.track_tool("wiki_log", skill="wiki")
        try:
            _get_wiki_pages().log(entry)
            return json.dumps({"success": True, "logged_at": "ok"}, indent=2)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-search",
        annotations=tool_annotations({"title": "Wiki Search", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_search(query: str = "", tags: str = "[]") -> str:
        """Search wiki pages by content, optionally filtered by tags."""
        metrics.track_tool("wiki_search", skill="wiki")
        try:
            parsed_tags = json.loads(tags) if isinstance(tags, str) and tags else None
            matches = _get_wiki_pages().search(query, tags=parsed_tags)
            return json.dumps({"success": True, "matches": matches, "count": len(matches)}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-lint",
        annotations=tool_annotations({"title": "Wiki Lint", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_lint() -> str:
        """Run structural wiki lint for missing roots, broken links, orphans, and duplicate titles."""
        metrics.track_tool("wiki_lint", skill="wiki")
        try:
            from skills.wiki.scripts.wiki_maintenance import lint_wiki
            result = lint_wiki(wiki_dir=get_compiled_wiki_dir(resolve_wiki_dir()))
            return json.dumps({"success": True, **result}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-status",
        annotations=tool_annotations({"title": "Wiki Status", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_status() -> str:
        """Return wiki structure, compiler backlog, batch, coverage, and index status."""
        metrics.track_tool("wiki_status", skill="wiki")
        try:
            return json.dumps(build_wiki_status(), indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-purge",
        annotations=tool_annotations({"title": "Wiki Purge", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_purge() -> str:
        """Delete the compiled wiki plus runtime wiki artifacts for a clean rebuild."""
        metrics.track_tool("wiki_purge", skill="wiki")
        try:
            from src.config.paths import get_rag_category_dir, get_runtime_dir

            runtime_wiki_dir = get_runtime_dir() / "wiki"
            compiled_wiki_dir = get_compiled_wiki_dir(resolve_wiki_dir())
            rag_wiki_dir = get_rag_category_dir("wiki")

            removed_wiki = compiled_wiki_dir.exists()
            removed_runtime_wiki = runtime_wiki_dir.exists()
            removed_rag_wiki = rag_wiki_dir.exists()

            if removed_runtime_wiki:
                shutil.rmtree(runtime_wiki_dir)
            if removed_wiki:
                shutil.rmtree(compiled_wiki_dir)
            if removed_rag_wiki:
                shutil.rmtree(rag_wiki_dir)

            _reset_cached_wiki_handles()
            return json.dumps(
                {
                    "success": True,
                    "wiki_dir": str(compiled_wiki_dir),
                    "runtime_wiki_dir": str(runtime_wiki_dir),
                    "rag_wiki_dir": str(rag_wiki_dir),
                    "removed_wiki": removed_wiki,
                    "removed_runtime_wiki": removed_runtime_wiki,
                    "removed_rag_wiki": removed_rag_wiki,
                },
                indent=2,
                default=str,
            )
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-reset",
        annotations=tool_annotations({"title": "Wiki Reset", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_reset(full_compile: bool = False) -> str:
        """Run a safe clean-slate reset: purge wiki and RAG, rebuild, reindex, and lint."""
        metrics.track_tool("wiki_reset", skill="wiki")
        try:
            if run_wiki_reset is None:
                raise ImportError("wiki reset helper is unavailable")

            _reset_cached_wiki_handles()
            result = run_wiki_reset(full_compile=full_compile)
            _reset_cached_wiki_handles()
            return json.dumps({"success": True, **result}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-migrate-v4",
        annotations=tool_annotations({"title": "Wiki Migrate V4", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_migrate_v4(apply: bool = False) -> str:
        """Dry-run or apply the ADR-740 v3-to-v4 concept page migration."""
        metrics.track_tool("wiki_migrate_v4", skill="wiki")
        try:
            return await _run_wiki_migrate_v4(apply=apply)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-scan-sources",
        annotations=tool_annotations({"title": "Wiki Scan Sources", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}),
    )
    @mcp_tool_interceptor
    async def wiki_scan_sources(hub: str = "") -> str:
        """List wiki-feeding content across vault, documents, skills, repo docs, project deltas, git history, runtime memory, logs, `/ask`, and targeted ADRs."""
        metrics.track_tool("wiki_scan_sources", skill="wiki")
        try:
            scanner = _get_scanner()
            sources = scanner.scan(hub=hub or None)
            return json.dumps({"success": True, "sources": sources, "count": len(sources)}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-rebuild",
        annotations=tool_annotations({"title": "Wiki Rebuild", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_rebuild(limit: int = 20) -> str:
        """Prepare a fresh concept extraction batch without deleting existing wiki files."""
        metrics.track_tool("wiki_rebuild", skill="wiki")
        try:
            from src.config.paths import get_rag_dir, get_runtime_dir, resolve_wiki_dir

            sources = build_source_inventory(rag_dir=get_rag_dir(), wiki_dir=resolve_wiki_dir())
            state = WikiCompilerState()
            normalized_limit = max(int(limit), 0)
            batch = prepare_extraction_batch(
                sources,
                state,
                limit=normalized_limit,
            )
            batch_summary = _serialize_extraction_batch(
                batch,
                runtime_wiki_dir=get_runtime_dir() / "wiki",
                mode="rebuild",
            )
            return json.dumps(
                {
                    "success": True,
                    "status": "agent_action_required",
                    "mode": "rebuild",
                    "batch": batch_summary,
                    "backlog": _batch_backlog_summary(sources, state, batch, limit=normalized_limit),
                    "next_steps": _concept_batch_next_steps(batch_summary),
                    "instructions": _concept_batch_instructions(),
                },
                indent=2,
                default=str,
            )
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="wiki-update",
        annotations=tool_annotations({"title": "Wiki Update", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_update(limit: int = 20, tier: str = "") -> str:
        """Prepare an incremental concept extraction batch for new or changed sources."""
        metrics.track_tool("wiki_update", skill="wiki")
        return await _run_wiki_update(limit=limit, tier=tier)

    @mcp.tool(
        name="wiki-apply-concept-batch",
        annotations=tool_annotations({"title": "Wiki Apply Concept Batch", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def wiki_apply_concept_batch(payloads_json: str = "{}") -> str:
        """Apply agent-extracted concept JSON and write concept wiki pages."""
        metrics.track_tool("wiki_apply_concept_batch", skill="wiki")
        payloads, error = _parse_extraction_payloads(payloads_json)
        if error is not None:
            return json.dumps({"success": False, "error": error}, indent=2)

        try:
            from src.config.paths import get_rag_dir, get_runtime_dir, resolve_wiki_dir

            wiki_dir = resolve_wiki_dir()
            runtime_wiki_dir = get_runtime_dir() / "wiki"
            result = apply_extraction_batch(
                wiki_dir=wiki_dir,
                runtime_wiki_dir=runtime_wiki_dir,
                state=load_compiler_state(runtime_wiki_dir),
                sources=build_source_inventory(rag_dir=get_rag_dir(), wiki_dir=wiki_dir),
                payloads=payloads or {},
                timestamp=_utc_timestamp(),
            )
            last_extraction_ts_written = False
            if int(getattr(result, "sources_processed", 0) or 0) > 0:
                write_last_ts(runtime_wiki_dir / "last-extraction.ts", time.time())
                last_extraction_ts_written = True
            runtime_metadata = _refresh_concept_runtime_metadata(
                get_compiled_wiki_dir(wiki_dir),
                runtime_wiki_dir,
            )
            needs_update_cleared = (
                _clear_needs_update_flag(runtime_wiki_dir)
                if int(getattr(result, "sources_processed", 0) or 0) > 0
                else False
            )
            post_apply_status = build_wiki_status(
                wiki_dir=wiki_dir,
                rag_dir=get_rag_dir(),
                runtime_wiki_dir=runtime_wiki_dir,
            )
            return json.dumps(
                {
                    "success": True,
                    "pages_written": result.pages_written,
                    "concepts_written": result.concepts_written,
                    "concepts_deferred": getattr(result, "concepts_deferred", 0),
                    "queries_written": getattr(result, "queries_written", 0),
                    "draft_concepts": getattr(result, "draft_concepts", 0),
                    "overbroad_concepts": getattr(result, "overbroad_concepts", 0),
                    "stale_sources_pruned": getattr(result, "stale_sources_pruned", 0),
                    "cluster_min_sources": getattr(result, "cluster_min_sources", 8),
                    "cluster_max_sources": getattr(result, "cluster_max_sources", 15),
                    "sources_processed": result.sources_processed,
                    "sources_generated": result.sources_generated,
                    "last_extraction_ts_written": last_extraction_ts_written,
                    "runtime_metadata": runtime_metadata,
                    "needs_update_cleared": needs_update_cleared,
                    "post_apply_status": _post_apply_status_summary(post_apply_status),
                },
                indent=2,
                default=str,
            )
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="ask-sync-data",
        annotations=tool_annotations({"title": "Ask Sync Data", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def ask_sync_data(days_back: int = 7, limit: int = 20) -> str:
        """Gather recent retained `/ask` outcomes from synthesis and memory layers."""
        metrics.track_tool("ask_sync_data", skill="wiki")
        try:
            from src.lib.ingest.ask_sync import load_recent_ask_outcomes

            items = load_recent_ask_outcomes(days_back=days_back, limit=limit)
            return json.dumps({"success": True, "items": items, "count": len(items)}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(
        name="ask-sync-clusters",
        annotations=tool_annotations({"title": "Ask Sync Clusters", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    )
    @mcp_tool_interceptor
    async def ask_sync_clusters(days_back: int = 7, limit: int = 20) -> str:
        """Cluster recent retained `/ask` outcomes for wiki compounding."""
        metrics.track_tool("ask_sync_clusters", skill="wiki")
        try:
            from src.lib.ingest.ask_sync import load_recent_ask_outcomes
            from src.lib.ingest.ask_sync_clusters import (
                cluster_ask_outcomes,
                suggest_page_targets,
            )

            items = load_recent_ask_outcomes(days_back=days_back, limit=limit)
            clusters = cluster_ask_outcomes(items)
            clusters = suggest_page_targets(clusters, _get_wiki_pages().read_tags())
            return json.dumps({"success": True, "clusters": clusters, "count": len(clusters)}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(name="wiki-report-data", annotations=tool_annotations({"title": "Wiki Report Data", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def wiki_report_data(hub: str = "", lightweight: bool = False) -> str:
        """Aggregate wiki stats, pages, connections, and portfolio for report generation."""
        metrics.track_tool("wiki_report_data", skill="wiki")
        try:
            from skills.wiki.scripts.wiki_report_contract import SYNTHESIS_SCHEMA, hub_sections_skeleton
            from skills.wiki.scripts.wiki_report import aggregate_report_data
            from src.config.paths import get_documents_dir, get_runtime_dir, get_vault_dir
            runtime_wiki_dir = get_runtime_dir() / "wiki"
            if lightweight:
                stats = _aggregate_wiki_dashboard_stats(get_compiled_wiki_dir(resolve_wiki_dir()))
                return json.dumps(
                    {
                        "success": True,
                        "stats": stats,
                        "hubs": {},
                        "hub_sections": [],
                        "pages": [],
                        "connections": [],
                        "portfolio": {},
                        "synthesis_schema": SYNTHESIS_SCHEMA,
                    },
                    indent=2,
                    default=str,
                )
            vault_dir = None if lightweight else get_vault_dir()
            documents_dir = None if lightweight else get_documents_dir()
            data = aggregate_report_data(
                wiki_dir=get_compiled_wiki_dir(resolve_wiki_dir()),
                runtime_wiki_dir=runtime_wiki_dir,
                portfolio_dir=get_vault_dir() / "portfolio",
                vault_dir=vault_dir,
                documents_dir=documents_dir,
                hub=hub or None,
            )
            # Convert to serializable dict
            result = {
                "stats": data.stats,
                "hubs": data.hubs,
                "hub_sections": hub_sections_skeleton(data.hubs),
                "pages": data.pages,
                "connections": data.connections,
                "consolidation": getattr(data, "consolidation", []),
                "portfolio": data.portfolio,
                "synthesis_schema": SYNTHESIS_SCHEMA,
            }
            return json.dumps({"success": True, **result}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(name="wiki-rewrite-candidates", annotations=tool_annotations({"title": "Wiki Rewrite Candidates", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def wiki_rewrite_candidates(limit: int = 20) -> str:
        """Return pages whose quality heuristics suggest an editorial rewrite."""
        metrics.track_tool("wiki_rewrite_candidates", skill="wiki")
        try:
            from skills.wiki.scripts.wiki_maintenance import find_rewrite_candidates

            candidates = find_rewrite_candidates(wiki_dir=get_compiled_wiki_dir(resolve_wiki_dir()))
            bounded = candidates[: max(limit, 0)]
            return json.dumps(
                {"success": True, "candidates": bounded, "count": len(bounded), "total": len(candidates)},
                indent=2,
                default=str,
            )
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(name="wiki-rewrite-proposals", annotations=tool_annotations({"title": "Wiki Rewrite Proposals", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def wiki_rewrite_proposals(limit: int = 20) -> str:
        """Return page-level rewrite proposals enriched with ask and shipped-change signals."""
        metrics.track_tool("wiki_rewrite_proposals", skill="wiki")
        try:
            from src.lib.ingest.ask_sync import load_recent_ask_outcomes
            from skills.wiki.scripts.wiki_maintenance import build_rewrite_proposals
            from src.config.paths import get_runtime_dir
            runtime_wiki_dir = get_runtime_dir() / "wiki"

            proposals = build_rewrite_proposals(
                wiki_dir=get_compiled_wiki_dir(resolve_wiki_dir()),
                runtime_wiki_dir=runtime_wiki_dir,
                sources=_get_scanner().scan(),
                ask_outcomes=load_recent_ask_outcomes(),
                max_proposals=max(limit, 0),
            )
            return json.dumps(
                {"success": True, "proposals": proposals, "count": len(proposals)},
                indent=2,
                default=str,
            )
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(name="wiki-apply-top-rewrite-proposal", annotations=tool_annotations({"title": "Wiki Apply Top Rewrite Proposal", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def wiki_apply_top_rewrite_proposal() -> str:
        """Rewrite the highest-priority proposal page using the current proposal queue."""
        metrics.track_tool("wiki_apply_top_rewrite_proposal", skill="wiki")
        try:
            from src.lib.ingest.ask_sync import load_recent_ask_outcomes
            from skills.wiki.scripts.wiki_maintenance import apply_top_rewrite_proposal
            from src.config.paths import get_runtime_dir
            runtime_wiki_dir = get_runtime_dir() / "wiki"

            result = apply_top_rewrite_proposal(
                wiki_dir=get_compiled_wiki_dir(resolve_wiki_dir()),
                runtime_wiki_dir=runtime_wiki_dir,
                sources=_get_scanner().scan(),
                ask_outcomes=load_recent_ask_outcomes(),
            )
            if result is None:
                return json.dumps({"success": True, "applied": False, "message": "No rewrite proposal available"}, indent=2)
            return json.dumps({"success": True, "applied": True, **result}, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(name="wiki-report-generate", annotations=tool_annotations({"title": "Wiki Report Generate", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def wiki_report_generate(report_json: str = "", style: str = "demo", output_dir: str = "") -> str:
        """Generate Second Brain Report as PDF + HTML from a validated rich dict."""
        metrics.track_tool("wiki_report_generate", skill="wiki")
        try:
            from skills.wiki.scripts.wiki_report_contract import validate_rich_dict

            report = json.loads(report_json) if report_json else {}
            validation = validate_rich_dict(report)
            if not validation.success:
                return json.dumps(
                    {
                        "success": False,
                        "error": "agent_step_required",
                        "missing_required": validation.missing_required,
                        "contract_path": "project-brain/capabilities/skills/rag/commands/wiki.md#wiki-report",
                        "hint": (
                            "Run /wiki report from inside Claude Code, Codex, Gemini CLI, Cursor, or Copilot. "
                            "The agent layer is required for editorial synthesis."
                        ),
                    },
                    indent=2,
                )

            return _generate_report_html(report, output_dir=output_dir)
        except Exception as exc:
            logger.error("wiki-report-generate failed: %s", exc, exc_info=True)
            return json.dumps({"success": False, "error": str(exc)})


__all__ = ["_generate_report_html", "_write_report_sidecar", "register_wiki_tools"]

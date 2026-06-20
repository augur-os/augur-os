from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable
from typing import Any

from src.lib.ingest.inbox_models import InboxRunRecord, to_dict
from src.lib.ingest.inbox_store import InboxStore
from src.lib.ingest.wiki_status_read import read_persisted_wiki_status
from src.lib.ingest.rag_demo_verify import verify_demo_rag


DEMO_RAG_QUERY = "investor demo meeting"


def summarize_inbox_run(run: InboxRunRecord | dict[str, Any]) -> dict[str, Any]:
    summary = to_dict(run)
    summary.pop("file_results", None)
    return summary


def _latest_run_demo_artifacts(store: InboxStore) -> list[str]:
    runs = store.list_run_payloads(limit=1, file_results_limit=20)
    if not runs:
        return []
    paths: list[str] = []
    for result in runs[0].get("file_results", []):
        if "demo-meeting" not in str(result.get("source_path", "")):
            continue
        for key in ("source_card_path", "extracted_path"):
            value = result.get(key)
            if value:
                paths.append(str(value))
    return paths


def _empty_wiki_status(*, latest_runs: list[dict[str, Any]], files_indexed: int) -> dict[str, Any]:
    return {
        "verdict": "inbox_sources_ready" if latest_runs else "no_recent_inbox_runs",
        "healthy": True,
        "structure": {"pages": 0, "missing_links": [], "orphan_pages": []},
        "compiler": {
            "sources_total": files_indexed,
            "sources_pending_or_changed": files_indexed,
            "current": False if latest_runs else True,
        },
        "coverage": {
            "concept_coverage_ratio": 0.0,
            "top_uncovered_source_families": [],
        },
        "index": {"indexed": bool(latest_runs), "wiki_rag_entries": 0},
        "batches": {"batch_count": 0, "needs_update": bool(latest_runs)},
        "compounding_health": {
            "concept_page_count": 0,
            "average_sources_per_concept_page": 0,
            "thin_page_count": 0,
            "target_sources_per_page": "10-15",
        },
        "actions": [],
    }


def _wiki_update_action() -> dict[str, Any]:
    return {
        "id": "prepare-incremental-batch",
        "tool": "wiki-update",
        "inputs": {"limit": 20},
        "reason": "Recent inbox source cards are ready for concept compounding.",
    }


def _decorate_wiki_status(
    wiki_status: dict[str, Any],
    *,
    latest_runs: list[dict[str, Any]],
    rag_demo: dict[str, Any],
) -> dict[str, Any]:
    status = deepcopy(wiki_status) if isinstance(wiki_status, dict) else {}
    status.setdefault("verdict", "inbox_sources_ready" if latest_runs else "no_recent_inbox_runs")
    status.setdefault("healthy", True)
    status.setdefault("structure", {"pages": 0, "missing_links": [], "orphan_pages": []})
    status.setdefault("compiler", {})
    status.setdefault("coverage", {"concept_coverage_ratio": 0.0, "top_uncovered_source_families": []})
    status.setdefault("batches", {"batch_count": 0, "needs_update": bool(latest_runs)})
    status.setdefault("compounding_health", {})

    index = dict(status.get("index") or {})
    index.update(
        {
            "demo_query": rag_demo["query"],
            "demo_hit_count": rag_demo["hit_count"],
            "demo_ready": rag_demo["ready"],
            "demo_hits": rag_demo["hits"],
        }
    )
    status["index"] = index

    actions = status.get("actions")
    if not isinstance(actions, list):
        actions = []
    if latest_runs and not any(isinstance(action, dict) and action.get("tool") == "wiki-update" for action in actions):
        actions = [*actions, _wiki_update_action()]
    status["actions"] = actions
    return status


def build_brain_insights(
    *,
    store: InboxStore,
    limit: int = 10,
    wiki_status_builder: Callable[[], dict[str, Any]] = read_persisted_wiki_status,
) -> dict[str, Any]:
    """Build the Brain Inbox compounding status payload."""
    runs = store.list_run_payloads(limit=limit, include_file_results=False)
    latest_runs = [summarize_inbox_run(run) for run in runs]
    files_indexed = sum(run.get("files_indexed", 0) for run in runs)
    latest_demo_artifacts = _latest_run_demo_artifacts(store)
    rag_demo = (
        verify_demo_rag(DEMO_RAG_QUERY, expected_files=latest_demo_artifacts)
        if latest_demo_artifacts
        else {
            "query": DEMO_RAG_QUERY,
            "hit_count": 0,
            "hits": [],
            "ready": False,
        }
    )
    errors: list[str] = []
    try:
        raw_wiki_status = wiki_status_builder()
    except Exception as exc:
        errors.append(f"wiki status unavailable: {exc}")
        raw_wiki_status = _empty_wiki_status(latest_runs=latest_runs, files_indexed=files_indexed)
    wiki_status = _decorate_wiki_status(raw_wiki_status, latest_runs=latest_runs, rag_demo=rag_demo)

    return {
        "success": True,
        "latest_runs": latest_runs,
        "wiki_status": wiki_status,
        "retained_ask_outcomes": [],
        "retained_ask_clusters": [],
        "errors": errors,
    }

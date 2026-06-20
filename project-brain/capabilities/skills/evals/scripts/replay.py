"""Replay orchestration -- rerun captured queries against live retrieval, score them.

`replay()` is the measurement core (spec section 4.5):

1. Load captured + external query records, deduplicated by `id`.
2. Load judgments keyed by `query_id`.
3. For each query WITH at least one labeled relevant doc, rerun the recorded
   `tool` with the recorded params against **current** retrieval -- NOT the
   captured `returned` set, because the point of replay is to test today's code.
4. Score the fresh `retrieved` list against the judgment's `relevant_doc_ids`.
5. Detect `index_drift` by comparing the live `vault_manifest_hash()` against
   each query's recorded value.

Queries with no judgment / `|R| == 0` are skipped and counted under
`unlabeled_queries` (spec section 4.4). `--config <path>` overrides the recorded
retrieval params with a YAML config for A/B testing.

No model calls. Replay is deterministic given the same `augur_commit` +
`vault_manifest_hash`.
"""

from __future__ import annotations

import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)

import logging
from pathlib import Path
from typing import Any

import yaml

import capture  # sibling -- shares the doc-id extraction contract
import metrics
import records

logger = logging.getLogger("evals.replay")


# --------------------------------------------------------------------------
# Live retrieval -- rerun a query through the recorded tool
# --------------------------------------------------------------------------


def _retrieve_unified_search(
    query: str,
    mode: str,
    top_k: int,
    scopes: list[str] | None,
    project: str | None,
) -> list[dict[str, Any]]:
    """Rerun a query through the live `unified-search` retrieval path.

    Mirrors what the `unified-search` MCP tool does internally (UnifiedSearcher),
    so replay tests the same code path that capture observed.
    """
    from src.lib.knowledge import UnifiedSearcher

    searcher = UnifiedSearcher(scopes=scopes)
    results = searcher.search(query=query, scopes=scopes, top_k=top_k)
    rows = [r if isinstance(r, dict) else r.to_dict() for r in results]
    return rows


def _retrieve_project_index(query: str, top_k: int) -> list[dict[str, Any]]:
    """Rerun a query through the live `knowledge-project-index-search` path."""
    from src.config.paths import get_rag_dir

    rag_dir = get_rag_dir()
    manifest_path = rag_dir / "_meta" / "manifest.yaml"
    if not manifest_path.exists():
        return []
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    entries = manifest.get("entries", [])
    if not isinstance(entries, list):
        return []
    query_words = set(query.lower().split())
    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        text = (
            f"{entry.get('name', '')} {entry.get('description', '')} "
            f"{entry.get('hub', '')}"
        ).lower()
        entry_words = set(text.split())
        if not query_words:
            continue
        overlap = query_words & entry_words
        score = len(overlap) / len(query_words)
        if score > 0:
            scored.append(
                (
                    score,
                    {
                        "name": entry.get("name", ""),
                        "path": entry.get("path", ""),
                        "score": round(score, 3),
                    },
                )
            )
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[: max(top_k, 1)]]


def run_retrieval(
    tool: str,
    query: str,
    *,
    mode: str = "hybrid",
    top_k: int = 10,
    scopes: list[str] | None = None,
    project: str | None = None,
) -> list[str]:
    """Rerun `query` through the live `tool`; return a ranked list of doc ids.

    Uses `capture.extract_doc_id` so the id of a given result row matches what
    capture would have recorded -- keeping capture and replay on one id contract.
    """
    tool = capture.normalize_tool_name(tool)
    if tool == "knowledge-project-index-search":
        rows = _retrieve_project_index(query, top_k)
    else:
        # Default + "unified-search": the primary retrieval surface.
        rows = _retrieve_unified_search(query, mode, top_k, scopes, project)

    # Deduplicate by doc id, keeping first (best-ranked) occurrence. A retrieval
    # surface that returns the same document N times (e.g. one hit per matching
    # line) must not count that document N times -- IR scoring is over a ranked
    # list of DISTINCT documents. Dedup also maximizes replay determinism: it
    # collapses order-only churn in a retrieval layer that returns duplicates.
    ranked: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        doc_id = capture.extract_doc_id(row)
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            ranked.append(doc_id)
    return ranked


# --------------------------------------------------------------------------
# Config override (--config)
# --------------------------------------------------------------------------


def _load_config_override(config_path: str | Path | None) -> dict[str, Any]:
    """Load a YAML config that overrides recorded retrieval params for A/B replay."""
    if not config_path:
        return {}
    path = Path(config_path)
    if not path.is_file():
        logger.warning("config override %s not found -- using recorded params", path)
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        logger.warning("config override %s parse failed: %s -- ignoring", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _apply_override(params: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge a config override onto recorded query params. Override wins."""
    merged = dict(params)
    for key in ("mode", "top_k", "scopes", "project", "tool"):
        if key in override:
            merged[key] = override[key]
    return merged


# --------------------------------------------------------------------------
# Corpus filtering
# --------------------------------------------------------------------------


def _corpus_of(record: dict[str, Any]) -> str:
    """Bucket a query record: 'captured' or 'external:<corpus-id>'."""
    source = str(record.get("source", "direct"))
    if source.startswith("external:"):
        return source
    return "captured"


def _corpus_matches(record: dict[str, Any], corpus: str) -> bool:
    bucket = _corpus_of(record)
    if corpus == "all":
        return True
    if corpus == "captured":
        return bucket == "captured"
    if corpus == "external":
        return bucket.startswith("external:")
    # Explicit external corpus id.
    return bucket == corpus or bucket == f"external:{corpus}"


# --------------------------------------------------------------------------
# Replay
# --------------------------------------------------------------------------


def replay(
    config_path: str | Path | None = None,
    corpus: str = "all",
    since: str | None = None,
    *,
    with_ci: bool = False,
) -> dict[str, Any]:
    """Replay captured queries against live retrieval and score them.

    Returns a result dict consumed by `report.write_report`:

        {
          "queries": [<per-query row>, ...],   # scored queries only
          "unlabeled_queries": [<row>, ...],   # skipped: no judgment / |R|==0
          "aggregates": {<overall + per-bucket aggregate dicts>},
          "index_drift": bool,
          "drift_detail": {...} | None,
          "live_commit": str,
          "live_vault_manifest_hash": str,
          "config_override": {...},
          "corpus": str,
          "since": str | None,
          "started_at": iso8601,
          "finished_at": iso8601,
          "counts": {...},
        }
    """
    started_at = records.utc_now_iso()
    override = _load_config_override(config_path)

    all_queries = records.read_query_records(since=since, include_external=True)
    judgments = records.read_judgments(include_external=True)

    queries = [q for q in all_queries if _corpus_matches(q, corpus)]

    live_commit = records.augur_commit()
    live_manifest = records.vault_manifest_hash()

    scored_rows: list[dict[str, Any]] = []
    unlabeled_rows: list[dict[str, Any]] = []
    drift_count = 0

    for record in queries:
        qid = record.get("id")
        if not qid:
            continue
        judgment = judgments.get(qid)
        relevant = judgment.get("relevant_doc_ids", []) if judgment else []

        # Per-query index drift: did the vault change since this query was captured?
        recorded_manifest = (
            (record.get("retrieval_config") or {}).get("vault_manifest_hash") or ""
        )
        query_drift = bool(
            recorded_manifest and live_manifest and recorded_manifest != live_manifest
        )
        if query_drift:
            drift_count += 1

        if not relevant:
            # No judgment, or a judgment with zero relevant docs -> skip for
            # P/R/MRR/nDCG (spec section 4.4). Surfaced as a labeling gap, not 0.
            unlabeled_rows.append(
                {
                    "id": qid,
                    "query": record.get("query", ""),
                    "source": record.get("source", "direct"),
                    "tool": record.get("tool", ""),
                    "corpus": _corpus_of(record),
                    "reason": "no_judgment" if judgment is None else "empty_relevant",
                }
            )
            continue

        params = {
            "tool": record.get("tool", "unified-search"),
            "mode": record.get("mode", "hybrid"),
            "top_k": record.get("top_k", 10) or 10,
            "scopes": record.get("scopes"),
            "project": record.get("project"),
        }
        params = _apply_override(params, override)

        try:
            retrieved = run_retrieval(
                params["tool"],
                record.get("query", ""),
                mode=params["mode"],
                top_k=int(params["top_k"]),
                scopes=params["scopes"],
                project=params["project"],
            )
        except Exception as exc:  # noqa: BLE001 - one bad query must not abort replay
            logger.warning("retrieval failed for query %s: %s", qid, exc)
            retrieved = []

        scores = metrics.score_query(retrieved, relevant)
        if scores is None:
            # Defensive: relevant was non-empty, so score_query should not skip.
            unlabeled_rows.append(
                {
                    "id": qid,
                    "query": record.get("query", ""),
                    "source": record.get("source", "direct"),
                    "tool": params["tool"],
                    "corpus": _corpus_of(record),
                    "reason": "empty_relevant",
                }
            )
            continue

        scored_rows.append(
            {
                "id": qid,
                "query": record.get("query", ""),
                "source": record.get("source", "direct"),
                "tool": params["tool"],
                "mode": params["mode"],
                "corpus": _corpus_of(record),
                "retrieved": retrieved,
                "relevant_doc_ids": list(relevant),
                "index_drift": query_drift,
                "scores": scores,
            }
        )

    # Deterministic ordering: scored rows already follow read_query_records'
    # (ts, id) sort because we iterate `queries` in that order.
    aggregates = _build_aggregates(scored_rows, with_ci=with_ci)

    finished_at = records.utc_now_iso()
    return {
        "queries": scored_rows,
        "unlabeled_queries": unlabeled_rows,
        "aggregates": aggregates,
        "index_drift": drift_count > 0,
        "drift_detail": (
            {"queries_with_drift": drift_count, "total_queries": len(queries)}
            if drift_count
            else None
        ),
        "live_commit": live_commit,
        "live_vault_manifest_hash": live_manifest,
        "config_override": override,
        "corpus": corpus,
        "since": since,
        "started_at": started_at,
        "finished_at": finished_at,
        "counts": {
            "total_queries": len(queries),
            "scored": len(scored_rows),
            "unlabeled": len(unlabeled_rows),
        },
    }


def _build_aggregates(
    scored_rows: list[dict[str, Any]], *, with_ci: bool
) -> dict[str, Any]:
    """Build the overall + per-bucket aggregate tables (spec section 4.4.6).

    Buckets: overall, per `source`, per `tool`, per `mode`, per `corpus`. A
    fixed bootstrap seed keeps the CI deterministic across reruns.
    """

    def _agg(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return metrics.aggregate(
            [r["scores"] for r in rows], with_ci=with_ci, seed=1742
        )

    out: dict[str, Any] = {"overall": _agg(scored_rows)}

    for dim in ("source", "tool", "mode", "corpus"):
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in scored_rows:
            key = str(row.get(dim, ""))
            buckets.setdefault(key, []).append(row)
        # Only include a dimension breakdown when it actually partitions.
        if len(buckets) > 1 or dim == "corpus":
            out[f"by_{dim}"] = {
                key: _agg(rows) for key, rows in sorted(buckets.items())
            }

    return out

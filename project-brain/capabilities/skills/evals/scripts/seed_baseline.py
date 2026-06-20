"""One-time baseline seeding (spec section 4.9).

Reads `references/baseline-seed-queries.yaml` (>= 50 hand-authored query
strings) and runs each through live `unified-search` once, writing an
`eval.query.v1` record per query so the captured baseline isn't empty without
waiting on organic user use.

The seed list is the canonical "Augur's user expects these to work" reference
set. It contains query strings only -- no vault content. Relevance judgments
are hand-authored afterward.

This script writes the seed records directly (it does not depend on contributor
mode / consent -- seeding IS the explicit opt-in act of running it). No model
calls -- it only exercises retrieval and records what came back.
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
import time
from pathlib import Path
from typing import Any

import yaml

import capture
import records
import replay

logger = logging.getLogger("evals.seed_baseline")


def seed_queries_path() -> Path:
    """Path to the hand-authored seed query list."""
    return Path(__file__).resolve().parent.parent / "references" / "baseline-seed-queries.yaml"


def load_seed_queries() -> list[str]:
    """Load the seed query strings. Returns [] when the file is missing/malformed."""
    path = seed_queries_path()
    if not path.is_file():
        logger.warning("seed query file not found: %s", path)
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        logger.warning("seed query file parse failed: %s", exc)
        return []
    if not isinstance(data, dict):
        return []
    queries = data.get("queries", [])
    if not isinstance(queries, list):
        return []
    return [str(q) for q in queries if str(q).strip()]


def seed_baseline(*, source: str = "seed-baseline", top_k: int = 10) -> dict[str, Any]:
    """Run every seed query through live retrieval once and capture the result.

    Each query produces one `eval.query.v1` record under
    `get_documents_dir()/evals/queries/<date>.jsonl` with `source` set to
    `seed-baseline` so the records bucket distinctly from organic `/ask` /
    `direct` capture.

    Returns a summary dict: {seed_count, captured, failed, queries_path}.
    """
    queries = load_seed_queries()
    if not queries:
        return {
            "seed_count": 0,
            "captured": 0,
            "failed": 0,
            "error": "no seed queries loaded",
        }

    captured = 0
    failed = 0
    log_path = records.query_log_path()

    for query in queries:
        try:
            started = time.monotonic_ns()
            rows = replay._retrieve_unified_search(  # noqa: SLF001 - intra-skill reuse
                query, "hybrid", top_k, None, None
            )
            duration_ms = int((time.monotonic_ns() - started) / 1_000_000)
            returned: list[dict[str, Any]] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                doc_id = capture.extract_doc_id(row)
                if not doc_id:
                    continue
                score = row.get("score")
                try:
                    score_val = float(score) if score is not None else None
                except (TypeError, ValueError):
                    score_val = None
                returned.append(
                    {"id": doc_id, "rank": len(returned) + 1, "score": score_val}
                )
            record = records.build_query_record(
                query=query,
                source=source,
                tool="unified-search",
                mode="hybrid",
                top_k=top_k,
                scopes=None,
                project=None,
                returned=returned,
                duration_ms=duration_ms,
            )
            records.write_query_record(record, log_path)
            captured += 1
        except Exception as exc:  # noqa: BLE001 - one bad query must not abort seeding
            logger.warning("seed query failed: %s -- %s", query, exc)
            failed += 1

    return {
        "seed_count": len(queries),
        "captured": captured,
        "failed": failed,
        "queries_path": str(log_path),
        "next_step": (
            "Hand-author judgments under "
            f"{records.judgments_dir()}/<query-id>.md, then run `aug eval replay`."
        ),
    }

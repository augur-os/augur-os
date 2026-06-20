"""LongMemEval external-corpus adapter (spec section 4.6).

Reads a LongMemEval-format JSONL (one entry per question) and emits matching
`eval.query.v1` + `eval.judgment.v1` records under
`get_documents_dir()/evals/external/<corpus-id>/`. The corpus is then replayed
alongside captured queries and bucketed separately in the report.

The repo never vendors a corpus -- the user drops a file in. The expected input
fields and the mapping are documented in `references/longmemeval-format.md`; a
future corpus in a different schema gets a parallel adapter rather than mutating
this code.

No model calls.
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

import json
import logging
from pathlib import Path
from typing import Any

import records

logger = logging.getLogger("evals.longmemeval")


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    """Parse a JSONL file into dict rows; skip blank / malformed lines."""
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("could not read corpus file %s: %s", path, exc)
        return rows
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("skipping malformed corpus line %s:%d", path, line_no)
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def import_corpus(jsonl_path: Path | str, corpus_id: str) -> dict[str, Any]:
    """Convert a LongMemEval JSONL into v1 query + judgment files for `corpus_id`.

    Output layout (per `references/longmemeval-format.md`):

        get_documents_dir()/evals/external/<corpus-id>/
        |-- queries/<corpus-id>.jsonl   eval.query.v1, source = "external:<corpus-id>"
        |-- judgments/<query-id>.md     eval.judgment.v1, one per query

    Returns a summary dict: {corpus_id, query_count, judgment_count, skipped,
    queries_path, judgments_dir}.

    The adapter never raises on a malformed line -- it logs and moves on.
    """
    jsonl_path = Path(jsonl_path)
    if not jsonl_path.is_file():
        return {
            "corpus_id": corpus_id,
            "error": f"input file not found: {jsonl_path}",
            "query_count": 0,
            "judgment_count": 0,
            "skipped": 0,
        }

    rows = _iter_jsonl(jsonl_path)
    source = f"external:{corpus_id}"

    corpus_root = records.external_dir() / corpus_id
    queries_path = corpus_root / "queries" / f"{corpus_id}.jsonl"
    judgments_subdir = corpus_root / "judgments"
    queries_path.parent.mkdir(parents=True, exist_ok=True)
    judgments_subdir.mkdir(parents=True, exist_ok=True)

    # Rewrite from scratch so a re-import is idempotent (no duplicate lines).
    query_lines: list[str] = []
    judgment_count = 0
    skipped = 0
    seen_ids: set[str] = set()

    # Pin the index state once at import time so the whole corpus shares it.
    retrieval_config = {
        "augur_commit": records.augur_commit(),
        "vault_manifest_hash": records.vault_manifest_hash(),
        "rrf_k": None,
        "rrf_weights": None,
    }

    for row in rows:
        question = row.get("question")
        evidence = row.get("evidence_doc_ids")
        if not question or not isinstance(evidence, list):
            skipped += 1
            continue
        question = str(question)
        qid = records.query_id(question, source)
        if qid in seen_ids:
            # Duplicate question folds into the same id -- last one wins.
            pass
        seen_ids.add(qid)

        record = records.build_query_record(
            query=question,
            source=source,
            tool="unified-search",
            mode="hybrid",
            top_k=10,
            scopes=None,
            project=None,
            returned=[],
            retrieval_config=dict(retrieval_config),
        )
        query_lines.append(
            json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)
        )

        judgment = records.build_judgment_record(
            query_id_value=qid,
            query=question,
            relevant_doc_ids=[str(x) for x in evidence],
            labeled_by=f"longmemeval:{corpus_id}",
            notes=f"imported from {jsonl_path.name}",
        )
        records.write_judgment(judgment, judgments_subdir / f"{qid}.md")
        judgment_count += 1

    queries_path.write_text(
        "\n".join(query_lines) + ("\n" if query_lines else ""), encoding="utf-8"
    )

    return {
        "corpus_id": corpus_id,
        "query_count": len(query_lines),
        "judgment_count": judgment_count,
        "skipped": skipped,
        "queries_path": str(queries_path),
        "judgments_dir": str(judgments_subdir),
    }

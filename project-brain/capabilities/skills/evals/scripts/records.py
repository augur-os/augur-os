"""Eval record schemas + reader/writer helpers — the regression contract (spec §4.3).

`records.py` is the leaf module of the eval harness: every other module depends on
these schemas; nothing depends back up. All persistence is JSONL (captured queries)
or markdown-with-frontmatter (judgments) under `get_documents_machine_dir('evals')/`. No
database. No LLM calls.

Schemas:
- `eval.query.v1`    — one JSONL line per captured retrieval-tool call (§4.3.1)
- `eval.judgment.v1` — one markdown file per query id, frontmatter only (§4.3.2)
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

import hashlib
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger("evals.records")

# --------------------------------------------------------------------------
# Schema constants — bumping any of these is a contract change requiring a
# migration script. Never silent. (spec §4.3.4)
# --------------------------------------------------------------------------

QUERY_SCHEMA = "eval.query.v1"
JUDGMENT_SCHEMA = "eval.judgment.v1"

# Fields a well-formed eval.query.v1 record carries. Used by validation +
# tests; additive fields (ADR-738/739 forward compat) extend retrieval_config
# without a schema bump.
QUERY_FIELDS = (
    "_schema",
    "id",
    "ts",
    "query",
    "source",
    "tool",
    "mode",
    "top_k",
    "scopes",
    "project",
    "returned",
    "retrieval_config",
    "duration_ms",
)

JUDGMENT_FIELDS = (
    "_schema",
    "query_id",
    "query",
    "relevant_doc_ids",
    "labeled_by",
    "labeled_at",
    "notes",
)


# --------------------------------------------------------------------------
# Path helpers — all eval artifacts live under get_documents_machine_dir('evals')
# --------------------------------------------------------------------------


def _docs_evals_dir() -> Path:
    """Resolve get_documents_machine_dir('evals') — the eval artifact root."""
    from src.config.paths import get_documents_machine_dir

    return get_documents_machine_dir("evals")


def evals_root() -> Path:
    """Public accessor for the eval artifact root."""
    return _docs_evals_dir()


def queries_dir() -> Path:
    return _docs_evals_dir() / "queries"


def judgments_dir() -> Path:
    return _docs_evals_dir() / "judgments"


def reports_dir() -> Path:
    return _docs_evals_dir() / "reports"


def external_dir() -> Path:
    return _docs_evals_dir() / "external"


def exports_dir() -> Path:
    return _docs_evals_dir() / "exports"


# --------------------------------------------------------------------------
# Identity + index-state hashing
# --------------------------------------------------------------------------


def query_id(query: str, source: str) -> str:
    """Content hash of query + source — `sha1(query + "\\x00" + source)[:12]`.

    The same query from the same caller folds into the same id, so a judgment
    for `id=X` covers every future invocation of `X`. Replay deduplicates by id.
    """
    digest = hashlib.sha1(f"{query}\x00{source}".encode("utf-8"), usedforsecurity=False)
    return digest.hexdigest()[:12]


def augur_commit() -> str:
    """Current HEAD sha (short). Empty string when git is unavailable."""
    try:
        from src.config.paths import get_project_root

        root = get_project_root()
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as exc:  # noqa: BLE001 - never let hashing break capture/replay
        logger.warning("augur_commit() failed: %s", exc)
    return ""


def vault_manifest_hash() -> str:
    """`sha256` of sorted `(relpath, mtime_ns)` tuples over vault files, `[:12]`.

    O(n) file stats, no reads — sub-second on a 10k-file vault. Together with
    `augur_commit()` this defines the index state for deterministic replay.
    Empty string when the vault is unavailable.
    """
    try:
        from src.config.paths import get_vault_dir

        vault = get_vault_dir()
        if not vault.exists():
            return ""
        entries: list[str] = []
        for path in sorted(vault.rglob("*")):
            if not path.is_file():
                continue
            # Skip hidden / VCS noise so the hash tracks content, not git state.
            rel = path.relative_to(vault)
            if any(part.startswith(".") for part in rel.parts):
                continue
            try:
                mtime_ns = path.stat().st_mtime_ns
            except OSError:
                continue
            entries.append(f"{rel.as_posix()}:{mtime_ns}")
        joined = "\n".join(entries)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]
    except Exception as exc:  # noqa: BLE001
        logger.warning("vault_manifest_hash() failed: %s", exc)
        return ""


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string with a trailing Z (no microseconds)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# --------------------------------------------------------------------------
# Query record construction + IO
# --------------------------------------------------------------------------


def build_query_record(
    *,
    query: str,
    source: str,
    tool: str,
    mode: str = "hybrid",
    top_k: int = 10,
    scopes: list[str] | None = None,
    project: str | None = None,
    returned: list[dict[str, Any]] | None = None,
    retrieval_config: dict[str, Any] | None = None,
    duration_ms: int | None = None,
    ts: str | None = None,
) -> dict[str, Any]:
    """Assemble a normalized `eval.query.v1` record dict.

    `id` is derived from `query + source`; `retrieval_config` defaults to the
    live commit + vault manifest hash with the ADR-739 reserved fields nulled.
    """
    if retrieval_config is None:
        retrieval_config = {
            "augur_commit": augur_commit(),
            "vault_manifest_hash": vault_manifest_hash(),
            "rrf_k": None,
            "rrf_weights": None,
        }
    return {
        "_schema": QUERY_SCHEMA,
        "id": query_id(query, source),
        "ts": ts or utc_now_iso(),
        "query": query,
        "source": source,
        "tool": tool,
        "mode": mode,
        "top_k": top_k,
        "scopes": scopes,
        "project": project,
        "returned": returned if returned is not None else [],
        "retrieval_config": retrieval_config,
        "duration_ms": duration_ms,
    }


def query_log_path(ts: str | None = None) -> Path:
    """Daily-rotated JSONL path for a capture timestamp (defaults to today UTC)."""
    if ts:
        day = ts[:10]
    else:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return queries_dir() / f"{day}.jsonl"


def write_query_record(record: dict[str, Any], path: Path | None = None) -> Path:
    """Append one JSON line to the daily query log. Creates the directory first.

    Append-only, no fsync per line — a torn tail never corrupts the prefix
    (spec §4.3.1).
    """
    target = path or query_log_path(record.get("ts"))
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str))
        handle.write("\n")
    return target


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    """Yield parsed JSON objects from a JSONL file; skip blank / malformed lines."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("could not read %s: %s", path, exc)
        return
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # A torn tail line is recoverable from logs; the prefix is intact.
            logger.warning("skipping malformed JSONL line %s:%d", path, line_no)
            continue
        if isinstance(obj, dict):
            yield obj


def _ts_in_range(ts: str, since: str | None, until: str | None) -> bool:
    if since is not None and ts < since:
        return False
    if until is not None and ts > until:
        return False
    return True


def read_query_records(
    since: str | None = None,
    until: str | None = None,
    *,
    include_external: bool = True,
) -> list[dict[str, Any]]:
    """Read all captured + external query records, deduplicated by `id`.

    Dedup rule (spec §4.5): last write wins per id. Cross-day duplicates collapse
    to the record with the most recent `ts`. `since`/`until` filter on `ts`
    (ISO-8601 string comparison, inclusive bounds).
    """
    by_id: dict[str, dict[str, Any]] = {}

    def _ingest(path: Path) -> None:
        for record in _iter_jsonl(path):
            rid = record.get("id")
            if not rid:
                continue
            ts = record.get("ts", "")
            if not _ts_in_range(ts, since, until):
                continue
            existing = by_id.get(rid)
            if existing is None or ts >= existing.get("ts", ""):
                by_id[rid] = record

    qdir = queries_dir()
    if qdir.exists():
        for path in sorted(qdir.glob("*.jsonl")):
            _ingest(path)

    if include_external:
        ext = external_dir()
        if ext.exists():
            for corpus in sorted(ext.iterdir()):
                if not corpus.is_dir():
                    continue
                cqueries = corpus / "queries"
                if cqueries.exists():
                    for path in sorted(cqueries.glob("*.jsonl")):
                        _ingest(path)

    # Stable ordering: by ts then id, so replay output is deterministic.
    return sorted(by_id.values(), key=lambda r: (r.get("ts", ""), r.get("id", "")))


# --------------------------------------------------------------------------
# Judgment file construction + IO
# --------------------------------------------------------------------------


def build_judgment_record(
    *,
    query_id_value: str,
    query: str,
    relevant_doc_ids: list[str],
    labeled_by: str = "",
    labeled_at: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """Assemble a normalized `eval.judgment.v1` frontmatter dict."""
    return {
        "_schema": JUDGMENT_SCHEMA,
        "query_id": query_id_value,
        "query": query,
        "relevant_doc_ids": list(relevant_doc_ids),
        "labeled_by": labeled_by,
        "labeled_at": labeled_at or utc_now_iso(),
        "notes": notes,
    }


def _render_frontmatter(data: dict[str, Any]) -> str:
    """Render an ordered YAML frontmatter block for a judgment file.

    Builds an ordered dict (stable `JUDGMENT_FIELDS` order, then any extras) and
    serializes it as one `yaml.safe_dump` block between `---` fences. One clean
    YAML document — no per-scalar dumping, so no stray `...` document markers
    leak into the frontmatter.
    """
    import yaml

    ordered: dict[str, Any] = {}
    for key in JUDGMENT_FIELDS:
        if key in data:
            ordered[key] = data[key]
    # Preserve any non-schema extras (e.g. a future additive field) deterministically.
    for key in sorted(data):
        if key not in ordered and key != "notes_body":
            ordered[key] = data[key]

    body = yaml.safe_dump(
        ordered, default_flow_style=False, sort_keys=False, allow_unicode=True
    ).rstrip()
    return f"---\n{body}\n---"


def write_judgment(record: dict[str, Any], path: Path | None = None) -> Path:
    """Write an `eval.judgment.v1` markdown file (frontmatter + freeform body)."""
    target = path or (judgments_dir() / f"{record['query_id']}.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    body = record.get("notes_body", "")
    content = _render_frontmatter(record) + "\n\n" + (body or "")
    target.write_text(content.rstrip() + "\n", encoding="utf-8")
    return target


def parse_judgment_file(path: Path) -> dict[str, Any] | None:
    """Parse a single judgment markdown file → its frontmatter dict, or None."""
    import yaml

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("could not read judgment %s: %s", path, exc)
        return None
    if not text.startswith("---"):
        logger.warning("judgment %s missing frontmatter", path)
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        logger.warning("judgment %s has malformed frontmatter", path)
        return None
    try:
        front = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        logger.warning("judgment %s frontmatter parse failed: %s", path, exc)
        return None
    if not isinstance(front, dict):
        return None
    # Normalize the relevant_doc_ids field to a list of strings.
    rel = front.get("relevant_doc_ids") or []
    if not isinstance(rel, list):
        rel = []
    front["relevant_doc_ids"] = [str(x) for x in rel]
    return front


def read_judgments(*, include_external: bool = True) -> dict[str, dict[str, Any]]:
    """Parse every `judgments/*.md`, keyed by `query_id`.

    Includes external-corpus judgments under `external/<corpus-id>/judgments/`.
    """
    out: dict[str, dict[str, Any]] = {}

    def _ingest(directory: Path) -> None:
        if not directory.exists():
            return
        for path in sorted(directory.glob("*.md")):
            front = parse_judgment_file(path)
            if front is None:
                continue
            qid = front.get("query_id")
            if not qid:
                continue
            out[str(qid)] = front

    _ingest(judgments_dir())

    if include_external:
        ext = external_dir()
        if ext.exists():
            for corpus in sorted(ext.iterdir()):
                if corpus.is_dir():
                    _ingest(corpus / "judgments")

    return out


def validate_query_record(record: dict[str, Any]) -> list[str]:
    """Return a list of schema problems for a query record (empty == valid)."""
    problems: list[str] = []
    if record.get("_schema") != QUERY_SCHEMA:
        problems.append(f"_schema is not {QUERY_SCHEMA!r}")
    for field in QUERY_FIELDS:
        if field not in record:
            problems.append(f"missing field {field!r}")
    returned = record.get("returned")
    if returned is not None and not isinstance(returned, list):
        problems.append("returned is not a list")
    return problems

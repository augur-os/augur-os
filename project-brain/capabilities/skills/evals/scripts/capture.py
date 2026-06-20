"""Opt-in retrieval-query capture — observer, consent flow, caller tagging (spec §4.2).

Capture is **off by default**. It is a no-op unless BOTH:
  1. `AUGUR_CONTRIBUTOR_MODE=1` is set in the environment (read per-call), AND
  2. `get_documents_dir()/evals/consent.md` exists.

The observer rides on `src/mcp/augur_shared/mcp_sdk.py::mcp_tool_interceptor` via a
single import-time registration (`register_capture_observer()`). It is consulted
after a retrieval tool returns; on any failure it logs WARN and is swallowed — a
broken eval skill can never break live search.

This module is the ONLY part of the eval harness the rest of Augur imports.
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

import contextvars
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

_augur_scripts_dir = str(_AugurPath(__file__).resolve().parent)
if _augur_scripts_dir not in _augur_sys.path:
    _augur_sys.path.insert(0, _augur_scripts_dir)

import records  # sibling module — scripts/ is on sys.path via bootstrap

logger = logging.getLogger("evals.capture")

# Tools the observer watches. A tool name not in this list is never captured.
# Stored in canonical dashed MCP-tool form.
CAPTURE_ALLOWLIST = frozenset({"unified-search", "knowledge-project-index-search"})


def normalize_tool_name(name: str) -> str:
    """Normalize a tool identifier to its canonical dashed MCP-tool name.

    `mcp_tool_interceptor` sees the Python function name (e.g.
    `unified_search_tool`), while the allowlist and captured records use the
    dashed MCP name (`unified-search`). This maps the former to the latter and
    leaves an already-dashed name untouched.
    """
    candidate = name.strip()
    if "-" in candidate and "_" not in candidate:
        return candidate
    stripped = candidate
    if stripped.endswith("_tool"):
        stripped = stripped[: -len("_tool")]
    return stripped.replace("_", "-")

CONTRIBUTOR_ENV = "AUGUR_CONTRIBUTOR_MODE"

# Caller-tagging contextvar: the /ask command body (or the dashboard MCP client)
# may set this before invoking a retrieval tool so the captured record carries
# `source: "/ask"` etc. When unset, source defaults to "direct".
_ACTIVE_CALLER: contextvars.ContextVar[str] = contextvars.ContextVar(
    "evals_active_caller", default="direct"
)

# Idempotency guard for register_capture_observer().
_OBSERVER_REGISTERED = False

# Stderr consent banner is printed at most once per process to avoid log spam.
_CONSENT_BANNER_SHOWN = False


# --------------------------------------------------------------------------
# Caller tagging
# --------------------------------------------------------------------------


def set_caller(name: str) -> contextvars.Token:
    """Tag the active caller for capture `source`. Returns a token for reset()."""
    return _ACTIVE_CALLER.set(name)


def reset_caller(token: contextvars.Token) -> None:
    """Restore the caller contextvar to its prior value."""
    try:
        _ACTIVE_CALLER.reset(token)
    except (ValueError, LookupError):
        pass


def active_caller() -> str:
    """Current caller tag, or 'direct' when unset."""
    return _ACTIVE_CALLER.get()


# --------------------------------------------------------------------------
# Consent
# --------------------------------------------------------------------------


def consent_path() -> Path:
    """Path to the opt-in consent file."""
    return records.evals_root() / "consent.md"


def has_consent() -> bool:
    """True when consent.md exists and is non-empty."""
    path = consent_path()
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def consent_terms() -> str:
    """The explicit terms text written into consent.md."""
    return (
        "This file records your opt-in to Augur retrieval-query capture (ADR-742).\n\n"
        "## What is captured\n\n"
        "When `AUGUR_CONTRIBUTOR_MODE=1` and this file exists, calls to retrieval\n"
        "tools (`unified-search`, `knowledge-project-index-search`) append a record to\n"
        "`<documents>/evals/queries/<date>.jsonl` containing:\n\n"
        "- the query text you searched for\n"
        "- the ids, ranks, and scores of the documents retrieval returned\n"
        "- timestamps and the retrieval configuration used\n\n"
        "## What is NOT captured\n\n"
        "- document bodies or any vault prose\n"
        "- LLM responses\n"
        "- anything when `AUGUR_CONTRIBUTOR_MODE` is unset, or when this file is deleted\n\n"
        "## How to opt out\n\n"
        "Delete this file, or unset `AUGUR_CONTRIBUTOR_MODE`. Capture stops immediately —\n"
        "the env var is read per call. Captured data already on disk is yours; delete\n"
        "`<documents>/evals/` to remove it.\n"
    )


def write_consent() -> Path:
    """Write consent.md with a UTC timestamp + the explicit terms. Idempotent."""
    path = consent_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "---\n"
        f"_schema: eval.consent.v1\n"
        f"opted_in_at: {records.utc_now_iso()}\n"
        "---\n\n"
        "# Augur Retrieval-Query Capture Consent\n\n"
        + consent_terms()
    )
    path.write_text(content, encoding="utf-8")
    return path


def consent_banner() -> str:
    """One-line stderr banner shown when contributor mode is on but consent is missing."""
    return (
        "[evals] AUGUR_CONTRIBUTOR_MODE=1 but no consent.md — capture suppressed. "
        "Run `aug eval capture-consent` to opt in (captures query text + returned doc "
        "ids/scores/timestamps; never vault content)."
    )


def contributor_mode_enabled() -> bool:
    """True when AUGUR_CONTRIBUTOR_MODE is set to '1'. Read per-call (not cached)."""
    return os.environ.get(CONTRIBUTOR_ENV) == "1"


def capture_enabled() -> bool:
    """True only when contributor mode is on AND consent has been recorded."""
    return contributor_mode_enabled() and has_consent()


# --------------------------------------------------------------------------
# Result parsing — turn a retrieval tool's JSON-string result into `returned[]`
# --------------------------------------------------------------------------


def extract_doc_id(row: dict[str, Any]) -> str | None:
    """Extract a stable doc id from a retrieval result row.

    Retrieval surfaces disagree on the id field: `unified-search` rows carry
    `file` (an absolute path), project-index rows carry `path`/`name`, and
    future graph/timeline rows may carry `id`/`uri`. This priority order is the
    single source of truth for both capture and replay so the same row always
    yields the same id (deterministic scoring).
    """
    doc_id = (
        row.get("id")
        or row.get("uri")
        or row.get("doc_id")
        or row.get("file")
        or row.get("path")
        or row.get("name")
    )
    return str(doc_id) if doc_id else None


def _extract_returned(result: Any, top_k: int) -> list[dict[str, Any]]:
    """Parse a retrieval tool's result into a ranked `returned` list.

    Retrieval tools return a JSON string. We never store document bodies — only
    the stable doc id, the 1-indexed rank, and the score.
    """
    payload: Any = result
    if isinstance(result, str):
        try:
            payload = json.loads(result)
        except json.JSONDecodeError:
            return []
    if not isinstance(payload, dict):
        return []
    rows = payload.get("results")
    if not isinstance(rows, list):
        return []
    returned: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        doc_id = extract_doc_id(row)
        if not doc_id:
            continue
        score = row.get("score")
        try:
            score_val = float(score) if score is not None else None
        except (TypeError, ValueError):
            score_val = None
        # Rank is the 1-indexed position among VALID rows, so ranks are dense.
        returned.append({"id": str(doc_id), "rank": len(returned) + 1, "score": score_val})
        if len(returned) >= max(top_k, 1) * 4:
            # Hard cap so a pathological result can't bloat the JSONL line.
            break
    return returned


def _coerce_args(args: tuple, kwargs: dict) -> dict[str, Any]:
    """Best-effort extraction of retrieval params from the tool's call args.

    Retrieval tools are called as keyword args by the MCP SDK, so kwargs is the
    common path; positional args are tolerated but rarely used.
    """
    merged: dict[str, Any] = dict(kwargs)
    # The retrieval tools accept `query` or the dashboard alias `q`.
    query = merged.get("query") or merged.get("q") or ""
    if not query and args:
        first = args[0]
        if isinstance(first, str):
            query = first
    scopes = merged.get("scopes")
    if scopes is not None and not isinstance(scopes, list):
        scopes = None
    top_k = merged.get("top_k") or merged.get("max_results") or 10
    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        top_k = 10
    return {
        "query": str(query),
        "mode": str(merged.get("mode", "hybrid")),
        "top_k": top_k,
        "scopes": scopes,
        "project": merged.get("project"),
    }


# --------------------------------------------------------------------------
# The observer
# --------------------------------------------------------------------------


def observe_tool_call(
    tool_name: str,
    args: tuple,
    kwargs: dict,
    result: Any,
    duration_ms: int | None = None,
) -> None:
    """Capture observer — consulted by mcp_tool_interceptor after a tool returns.

    No-op unless the tool is allowlisted AND contributor mode is on AND consent
    exists. Wrapped end-to-end in try/except: any failure logs WARN and is
    swallowed so capture can never break live retrieval.
    """
    global _CONSENT_BANNER_SHOWN
    try:
        canonical = normalize_tool_name(tool_name)
        if canonical not in CAPTURE_ALLOWLIST:
            return
        if not contributor_mode_enabled():
            return
        if not has_consent():
            if not _CONSENT_BANNER_SHOWN:
                print(consent_banner(), file=sys.stderr)
                _CONSENT_BANNER_SHOWN = True
            return

        params = _coerce_args(args, kwargs)
        query = params["query"]
        if not query:
            return  # nothing meaningful to capture

        source = active_caller()
        returned = _extract_returned(result, params["top_k"])
        record = records.build_query_record(
            query=query,
            source=source,
            tool=canonical,
            mode=params["mode"],
            top_k=params["top_k"],
            scopes=params["scopes"],
            project=params["project"],
            returned=returned,
            duration_ms=duration_ms,
        )
        records.write_query_record(record)
    except Exception as exc:  # noqa: BLE001 - never raise into the tool path
        logger.warning("eval capture observer failed (swallowed): %s", exc)


# --------------------------------------------------------------------------
# Registration — the single import-time hook mcp_sdk.py consults
# --------------------------------------------------------------------------


def register_capture_observer() -> Any:
    """Return the observer callable for mcp_tool_interceptor to consult.

    Idempotent: repeated calls return the same observer. `mcp_sdk.py` calls this
    once at import time inside a guarded try/except — a missing or broken eval
    skill yields a no-op observer and never breaks tool registration.
    """
    global _OBSERVER_REGISTERED
    _OBSERVER_REGISTERED = True
    return observe_tool_call


def observer_registered() -> bool:
    """True once register_capture_observer() has run (used by tests)."""
    return _OBSERVER_REGISTERED


# --------------------------------------------------------------------------
# Status — feeds `aug eval capture-status` / the eval-capture-status MCP tool
# --------------------------------------------------------------------------


def capture_status() -> dict[str, Any]:
    """Summarize capture state: enabled / consent / counts / last capture ts."""
    qdir = records.queries_dir()
    total = 0
    today_count = 0
    last_ts: str | None = None
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if qdir.exists():
        for path in sorted(qdir.glob("*.jsonl")):
            for rec in records._iter_jsonl(path):  # noqa: SLF001 - intra-skill helper
                total += 1
                ts = rec.get("ts")
                if ts:
                    if last_ts is None or ts > last_ts:
                        last_ts = ts
                if path.stem == today:
                    today_count += 1
    return {
        "enabled": contributor_mode_enabled(),
        "consent": has_consent(),
        "queries_captured_total": total,
        "queries_today": today_count,
        "last_capture_ts": last_ts,
    }

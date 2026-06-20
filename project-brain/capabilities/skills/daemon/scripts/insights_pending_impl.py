"""insights-pending impl: mtime-cached pending-insight reads (perf fix).

The dashboard polls insights-pending on every page load. insights.yaml can
grow past 1MB (2k+ insights), and parsing it with the pure-Python YAML loader
cost ~640ms of GIL-bound CPU per call — serializing every concurrent MCP tool
call in the server (the GIL turns the page-load burst into a serial drain).

Two mitigations live here:
- The parsed *pending* list is cached keyed by (path, mtime_ns, size); the
  file is only re-parsed when it actually changes.
- libyaml's CSafeLoader is used when available (~10x faster cache misses).

Bare module (no package-relative imports) so both the MCP tool wrapper in
``mcp/_insights.py`` and the skill tests can import it off the scripts dir,
mirroring ``runtime_paths``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Cache of the filtered pending list. Single-slot: there is one insights file
# per runtime; keyed defensively by path anyway.
_CACHE: dict[str, Any] = {"key": None, "pending": []}


def _reset_insights_cache() -> None:
    """Clear the parse cache (tests)."""
    _CACHE["key"] = None
    _CACHE["pending"] = []


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def _pending_insights(path: Path) -> list[dict[str, Any]]:
    """Return pending insights from ``path``, re-parsing only when it changes."""
    try:
        stat = path.stat()
    except OSError:
        return []
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if _CACHE["key"] == key:
        return _CACHE["pending"]

    data = _load_yaml(path)
    all_insights = data.get("insights", [])
    if not isinstance(all_insights, list):
        all_insights = []
    pending = [
        item
        for item in all_insights
        if isinstance(item, dict) and item.get("status") == "pending"
    ]
    _CACHE["key"] = key
    _CACHE["pending"] = pending
    return pending


def build_insights_response(
    path: Path,
    *,
    page: str | None = None,
    count_only: bool = False,
) -> str:
    """Build the insights-pending JSON response.

    count_only keeps the dashboard badge payload tiny — the only dashboard
    consumer reads ``count`` alone, and the full pending list can exceed 1MB.
    """
    if not path.exists():
        return json.dumps({"count": 0, "insights": []})

    try:
        pending = _pending_insights(path)
    except Exception:
        return json.dumps({"count": 0, "insights": []})

    if page:
        pending = [item for item in pending if item.get("page") == page]

    if count_only:
        return json.dumps({"count": len(pending), "insights": []})

    return json.dumps(
        {"count": len(pending), "insights": pending},
        indent=2,
        default=str,
    )

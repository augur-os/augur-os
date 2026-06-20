"""Tests for the insights-pending MCP tool impl: mtime cache + count_only (perf fix).

The dashboard polls insights-pending on every page load; parsing a 1.3MB
insights.yaml with the pure-Python YAML loader cost ~640ms of GIL-bound CPU
per call and serialized every concurrent MCP tool call. The impl now caches
the parsed pending list keyed by (mtime_ns, size) and supports count_only.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from insights_pending_impl import (  # noqa: E402
    _pending_insights,
    _reset_insights_cache,
    build_insights_response,
)


def _write_insights(path: Path, statuses: list[str], pages: list[str] | None = None) -> None:
    pages = pages or ["/browse"] * len(statuses)
    lines = ["insights:"]
    for i, (status, page) in enumerate(zip(statuses, pages)):
        lines += [
            f"  - id: ins-{i}",
            f"    status: {status}",
            f"    page: {page}",
            f"    title: insight {i}",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_pending_filter_and_response_shape(tmp_path: Path) -> None:
    _reset_insights_cache()
    f = tmp_path / "insights.yaml"
    _write_insights(f, ["pending", "resolved", "pending"], ["/a", "/a", "/b"])

    out = json.loads(build_insights_response(f, page=None, count_only=False))
    assert out["count"] == 2
    assert [i["id"] for i in out["insights"]] == ["ins-0", "ins-2"]

    by_page = json.loads(build_insights_response(f, page="/b", count_only=False))
    assert by_page["count"] == 1
    assert by_page["insights"][0]["id"] == "ins-2"


def test_count_only_omits_insights_payload(tmp_path: Path) -> None:
    _reset_insights_cache()
    f = tmp_path / "insights.yaml"
    _write_insights(f, ["pending", "pending"])

    out = json.loads(build_insights_response(f, page=None, count_only=True))
    assert out["count"] == 2
    assert out["insights"] == []


def test_parse_is_cached_until_file_changes(tmp_path: Path) -> None:
    _reset_insights_cache()
    f = tmp_path / "insights.yaml"
    _write_insights(f, ["pending"])

    first = _pending_insights(f)
    second = _pending_insights(f)
    # Unchanged file → cached list object is reused (no reparse).
    assert second is first

    # Changed content (and bumped mtime) → reparse picks up new data.
    _write_insights(f, ["pending", "pending"])
    st = f.stat()
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    third = _pending_insights(f)
    assert third is not first
    assert len(third) == 2


def test_missing_file_returns_empty(tmp_path: Path) -> None:
    _reset_insights_cache()
    out = json.loads(build_insights_response(tmp_path / "absent.yaml", page=None, count_only=False))
    assert out == {"count": 0, "insights": []}

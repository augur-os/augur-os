"""Tests for dream-report-write + dream-last-report (ADR-744 task 6)."""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dream_report.py"
_SPEC = importlib.util.spec_from_file_location("dream_report", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _sample_phases() -> dict:
    return {
        "job_id": "dream-2026-05-14T04-00-00",
        "phases": [
            {
                "id": "orphans",
                "kind": "deterministic",
                "state": "completed",
                "result": {
                    "flagged": [
                        {"slug": "wiki-orphan", "inbound_edges": 0, "timeline_entries": 1}
                    ]
                },
            },
            {
                "id": "dead-citations",
                "kind": "deterministic",
                "state": "completed",
                "result": {
                    "flagged": [
                        {
                            "page_slug": "wiki-orphan",
                            "timeline_at": "2026-05-04T10:00:00Z",
                            "source_uri": "vault://nonexistent-page.md",
                            "scheme": "vault",
                            "reason": "missing",
                        }
                    ]
                },
            },
            {
                "id": "cache-gc",
                "kind": "deterministic",
                "state": "failed",
                "error": "permission denied at /cache/graph/edges.jsonl",
            },
        ],
    }


def test_dream_report_write_creates_dated_markdown(tmp_path: Path):
    report_path = mod.dream_report_write(
        phase_results=_sample_phases(),
        run_date=date(2026, 5, 14),
        output_root=tmp_path,
    )
    assert report_path.exists()
    assert report_path.name == "2026-05-14.md"
    body = report_path.read_text(encoding="utf-8")
    assert "# Dream Cycle Report — 2026-05-14" in body
    # Each phase section appears
    assert "## orphans" in body
    assert "## dead-citations" in body
    assert "## cache-gc" in body
    # Phase counts surface as wiki-linked bullets
    assert "wiki-orphan" in body
    # The job_id from the ADR-743 ledger is referenced in the report footer
    assert "dream-2026-05-14T04-00-00" in body
    # Failed phase is surfaced honestly, not hidden
    assert "failed" in body.lower()


def test_dream_report_write_idempotent_within_same_day(tmp_path: Path):
    """Two writes on the same day overwrite the same file — last write wins."""
    first = mod.dream_report_write(
        phase_results=_sample_phases(),
        run_date=date(2026, 5, 14),
        output_root=tmp_path,
    )
    second_phases = _sample_phases()
    second_phases["job_id"] = "dream-2026-05-14T22-00-00"
    second = mod.dream_report_write(
        phase_results=second_phases,
        run_date=date(2026, 5, 14),
        output_root=tmp_path,
    )
    assert first == second
    body = second.read_text(encoding="utf-8")
    assert "dream-2026-05-14T22-00-00" in body
    assert "dream-2026-05-14T04-00-00" not in body


def test_dream_last_report_returns_most_recent(tmp_path: Path):
    mod.dream_report_write(
        phase_results=_sample_phases(),
        run_date=date(2026, 5, 12),
        output_root=tmp_path,
    )
    mod.dream_report_write(
        phase_results=_sample_phases(),
        run_date=date(2026, 5, 14),
        output_root=tmp_path,
    )
    mod.dream_report_write(
        phase_results=_sample_phases(),
        run_date=date(2026, 5, 13),
        output_root=tmp_path,
    )
    latest = mod.dream_last_report(output_root=tmp_path)
    assert latest["date"] == "2026-05-14"
    assert latest["path"].endswith("2026-05-14.md")


def test_dream_last_report_when_empty(tmp_path: Path):
    """No reports yet → both fields None."""
    latest = mod.dream_last_report(output_root=tmp_path)
    assert latest == {"date": None, "path": None}

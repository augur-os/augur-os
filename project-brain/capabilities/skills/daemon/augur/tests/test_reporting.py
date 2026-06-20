"""Auto-generated importability test for reporting."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from skills.daemon.scripts.adaptive.reporting import CategoryReport, CycleReport


def test_reporting_importable():
    """Verify that reporting can be imported without errors."""
    mod = importlib.import_module("skills.daemon.scripts.adaptive.reporting")
    assert mod is not None


def test_cycle_report_header_separates_skipped_from_ran():
    report = CycleReport(
        loop_name="hardening",
        categories=[
            CategoryReport(
                name="auto-stale-paths",
                trust_before=0.2,
                trust_after=0.2,
                difficulty_before=1,
                difficulty_after=1,
                status="ok",
                outcome="clean",
            ),
            CategoryReport(
                name="auto-macos-only",
                trust_before=0.2,
                trust_after=0.2,
                difficulty_before=1,
                difficulty_after=1,
                status="skipped",
                outcome="skipped_unsupported",
            ),
        ],
    )

    rendered = report.format()
    assert "(1 ran)" in rendered
    assert "1 skipped" in rendered


def test_cycle_report_format_all_includes_skipped_column():
    report = CycleReport(
        loop_name="hardening",
        categories=[
            CategoryReport(
                name="auto-stale-paths",
                trust_before=0.2,
                trust_after=0.2,
                difficulty_before=1,
                difficulty_after=1,
                status="ok",
                outcome="clean",
            ),
            CategoryReport(
                name="auto-macos-only",
                trust_before=0.2,
                trust_after=0.2,
                difficulty_before=1,
                difficulty_after=1,
                status="skipped",
                outcome="skipped_unsupported",
            ),
        ],
    )

    rendered = CycleReport.format_all([report])
    assert "SKIPPED" in rendered
    assert "│      1 │" in rendered

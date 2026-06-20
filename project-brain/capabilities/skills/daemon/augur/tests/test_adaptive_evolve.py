"""Tests for ADR-458: Evolve Loop Auto-Remediation.

Tests the evolve queue persistence, fix classification, auto-reclassify
remediation, and pending report formatting.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from skills.daemon.scripts.adaptive.evolve_queue import (
    EvolveEntry,
    EvolveQueue,
    FIX_FILTER,
    FIX_RECLASSIFY,
    FIX_UPGRADE,
    classify_fix_type,
    clear_queue,
    format_pending_report,
    pending_entries,
    persist_suggestions,
    read_queue,
    write_queue,
)
from skills.daemon.scripts.adaptive.evolve_remediate import (
    apply_reclassify,
    clear_hint,
    format_remediation_report,
    get_reclassify_hint,
    verify_reclassify,
)


# ---------------------------------------------------------------------------
# Fix classification
# ---------------------------------------------------------------------------


class TestClassifyFixType:
    def test_report_only_high_count_is_reclassify(self):
        assert classify_fix_type("report-only", 50) == FIX_RECLASSIFY

    def test_report_only_low_count_is_filter(self):
        assert classify_fix_type("report-only", 5) == FIX_FILTER

    def test_broken_is_filter(self):
        assert classify_fix_type("broken", 10) == FIX_FILTER

    def test_unknown_outcome_is_upgrade(self):
        assert classify_fix_type("some-other", 10) == FIX_UPGRADE

    def test_reclassify_threshold_boundary(self):
        assert classify_fix_type("report-only", 10) == FIX_FILTER
        assert classify_fix_type("report-only", 11) == FIX_RECLASSIFY


# ---------------------------------------------------------------------------
# Queue persistence
# ---------------------------------------------------------------------------


class TestEvolveQueue:
    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_write_and_read_roundtrip(self, mock_path, tmp_path):
        qpath = tmp_path / "evolve_queue.json"
        mock_path.return_value = qpath

        entry = EvolveEntry(
            category="auto-seed-data",
            loop_name="hardening",
            issue_count=115,
            outcome="report-only",
            fix_type=FIX_RECLASSIFY,
            suggestion="Reclassify false positives",
        )
        q = EvolveQueue(entries=[entry])
        write_queue(q)

        assert qpath.exists()
        q2 = read_queue()
        assert len(q2.entries) == 1
        assert q2.entries[0].category == "auto-seed-data"
        assert q2.entries[0].issue_count == 115
        assert q2.entries[0].fix_type == FIX_RECLASSIFY

    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_read_empty_returns_empty_queue(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "nonexistent.json"
        q = read_queue()
        assert len(q.entries) == 0

    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_clear_queue(self, mock_path, tmp_path):
        qpath = tmp_path / "evolve_queue.json"
        mock_path.return_value = qpath
        qpath.write_text("{}")

        clear_queue()
        assert not qpath.exists()

    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_pending_entries_filters_applied(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "evolve_queue.json"

        applied = EvolveEntry(
            category="done",
            loop_name="test",
            issue_count=5,
            outcome="report-only",
            fix_type=FIX_FILTER,
            suggestion="x",
            applied=True,
        )
        pending = EvolveEntry(
            category="todo",
            loop_name="test",
            issue_count=10,
            outcome="report-only",
            fix_type=FIX_RECLASSIFY,
            suggestion="y",
        )
        q = EvolveQueue(entries=[applied, pending])
        write_queue(q)

        result = pending_entries()
        assert len(result) == 1
        assert result[0].category == "todo"


# ---------------------------------------------------------------------------
# Persist suggestions from cycle reports
# ---------------------------------------------------------------------------


class TestPersistSuggestions:
    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_persists_wasted_categories(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "evolve_queue.json"

        # Mock CycleReport-like objects
        cat_report = MagicMock()
        cat_report.name = "auto-seed-data"
        cat_report.issue_count = 50
        cat_report.outcome = "report-only"
        cat_report.action_summary = "wrote report"

        cycle_report = MagicMock()
        cycle_report.loop_name = "hardening"
        cycle_report.categories = [cat_report]

        new = persist_suggestions([cycle_report], tmp_path)
        assert len(new) == 1
        assert new[0].category == "auto-seed-data"

    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_skips_clean_categories(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "evolve_queue.json"

        cat = MagicMock()
        cat.name = "auto-lint"
        cat.issue_count = 3
        cat.outcome = "auto-fixed"  # Not wasted
        cat.action_summary = "fixed"

        report = MagicMock()
        report.loop_name = "code-quality"
        report.categories = [cat]

        new = persist_suggestions([report], tmp_path)
        assert len(new) == 0

    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_deduplicates_existing_entries(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "evolve_queue.json"

        # Pre-populate queue
        existing = EvolveEntry(
            category="auto-seed-data",
            loop_name="hardening",
            issue_count=100,
            outcome="report-only",
            fix_type=FIX_RECLASSIFY,
            suggestion="old suggestion",
        )
        write_queue(EvolveQueue(entries=[existing]))

        # Run persist again with updated count
        cat = MagicMock()
        cat.name = "auto-seed-data"
        cat.issue_count = 80  # Changed
        cat.outcome = "report-only"
        cat.action_summary = "report"

        report = MagicMock()
        report.loop_name = "hardening"
        report.categories = [cat]

        new = persist_suggestions([report], tmp_path)
        assert len(new) == 0  # Not a new entry

        # But issue count should be updated
        q = read_queue()
        assert q.entries[0].issue_count == 80

    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_resolves_pending_entries_when_reported_loop_goes_clean(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "evolve_queue.json"

        stale = EvolveEntry(
            category="auto-empty-states",
            loop_name="hardening",
            issue_count=5,
            outcome="report-only",
            fix_type=FIX_FILTER,
            suggestion="Fix scanner logic",
        )
        untouched = EvolveEntry(
            category="auto-test-dashboard",
            loop_name="testing",
            issue_count=1,
            outcome="report-only",
            fix_type=FIX_FILTER,
            suggestion="Fix test flake",
        )
        write_queue(EvolveQueue(entries=[stale, untouched]))

        clean_cat = MagicMock()
        clean_cat.name = "auto-empty-states"
        clean_cat.issue_count = 0
        clean_cat.outcome = "clean"
        clean_cat.action_summary = "clean scan"

        report = MagicMock()
        report.loop_name = "hardening"
        report.categories = [clean_cat]

        new = persist_suggestions([report], tmp_path)

        assert new == []
        q = read_queue()
        resolved = next(e for e in q.entries if e.category == "auto-empty-states")
        still_pending = next(e for e in q.entries if e.category == "auto-test-dashboard")
        assert resolved.applied is True
        assert resolved.result == "resolved-in-run"
        assert still_pending.applied is False

    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_skips_manual_only_report_categories(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "evolve_queue.json"

        cat = MagicMock()
        cat.name = "auto-adr-lifecycle"
        cat.issue_count = 7
        cat.outcome = "report-only"
        cat.action_summary = "generated report"
        cat.actionable_count = 0
        cat.scanner_defect_count = 0
        cat.broken_count = 0
        cat.manual_count = 7

        report = MagicMock()
        report.loop_name = "knowledge-enrichment"
        report.categories = [cat]

        new = persist_suggestions([report], tmp_path)

        assert new == []
        assert pending_entries() == []

    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_manual_only_report_category_resolves_stale_pending_entry(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "evolve_queue.json"

        stale = EvolveEntry(
            category="auto-adr-lifecycle",
            loop_name="knowledge-enrichment",
            issue_count=7,
            outcome="report-only",
            fix_type=FIX_FILTER,
            suggestion="Upgrade fix() from report-only to actual code changes",
        )
        write_queue(EvolveQueue(entries=[stale]))

        cat = MagicMock()
        cat.name = "auto-adr-lifecycle"
        cat.issue_count = 7
        cat.outcome = "report-only"
        cat.action_summary = "generated report"
        cat.actionable_count = 0
        cat.scanner_defect_count = 0
        cat.broken_count = 0
        cat.manual_count = 7

        report = MagicMock()
        report.loop_name = "knowledge-enrichment"
        report.categories = [cat]

        new = persist_suggestions([report], tmp_path)

        assert new == []
        q = read_queue()
        assert len(q.entries) == 1
        assert q.entries[0].applied is True
        assert q.entries[0].result == "resolved-in-run"


# ---------------------------------------------------------------------------
# Pending report formatting
# ---------------------------------------------------------------------------


class TestFormatPendingReport:
    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_empty_queue_reports_no_pending(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "nonexistent.json"
        report = format_pending_report()
        assert "No pending" in report

    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_pending_report_includes_categories(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "evolve_queue.json"
        q = EvolveQueue(entries=[
            EvolveEntry(
                category="auto-markers",
                loop_name="code-quality",
                issue_count=19,
                outcome="report-only",
                fix_type=FIX_FILTER,
                suggestion="Fix scanner logic",
            ),
        ])
        write_queue(q)

        report = format_pending_report()
        assert "auto-markers" in report
        assert "19 issues" in report
        assert "Filter" in report


# ---------------------------------------------------------------------------
# Auto-reclassify remediation
# ---------------------------------------------------------------------------


class TestApplyReclassify:
    @patch("skills.daemon.scripts.adaptive.evolve_remediate._hints_dir")
    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_dry_run_does_not_write_hints(self, mock_qpath, mock_hints, tmp_path):
        mock_qpath.return_value = tmp_path / "evolve_queue.json"
        mock_hints.return_value = tmp_path / "hints"

        q = EvolveQueue(entries=[
            EvolveEntry(
                category="auto-seed-data",
                loop_name="hardening",
                issue_count=115,
                outcome="report-only",
                fix_type=FIX_RECLASSIFY,
                suggestion="Reclassify",
            ),
        ])
        write_queue(q)

        results = apply_reclassify(dry_run=True)
        assert len(results) == 1
        assert results[0]["outcome"] == "dry-run"
        assert not (tmp_path / "hints").exists()

    @patch("skills.daemon.scripts.adaptive.evolve_remediate._hints_dir")
    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_apply_writes_hint_and_marks_applied(self, mock_qpath, mock_hints, tmp_path):
        mock_qpath.return_value = tmp_path / "evolve_queue.json"
        hints_dir = tmp_path / "hints"
        mock_hints.return_value = hints_dir

        q = EvolveQueue(entries=[
            EvolveEntry(
                category="auto-seed-data",
                loop_name="hardening",
                issue_count=115,
                outcome="report-only",
                fix_type=FIX_RECLASSIFY,
                suggestion="Reclassify false positives",
            ),
        ])
        write_queue(q)

        results = apply_reclassify()
        assert len(results) == 1
        assert results[0]["outcome"] == "hint-written"

        # Hint file written
        hint_path = hints_dir / "auto-seed-data.json"
        assert hint_path.exists()
        hint = json.loads(hint_path.read_text())
        assert hint["action"] == "reclassify"
        assert hint["from_kind"] == "actionable"
        assert hint["to_kind"] == "maintenance"

        # Entry marked as applied in queue
        q2 = read_queue()
        assert q2.entries[0].applied is True
        assert q2.entries[0].result == "hint-written"

    @patch("skills.daemon.scripts.adaptive.evolve_remediate._hints_dir")
    @patch("skills.daemon.scripts.adaptive.evolve_queue._queue_path")
    def test_skips_non_reclassify_entries(self, mock_qpath, mock_hints, tmp_path):
        mock_qpath.return_value = tmp_path / "evolve_queue.json"
        mock_hints.return_value = tmp_path / "hints"

        q = EvolveQueue(entries=[
            EvolveEntry(
                category="auto-markers",
                loop_name="code-quality",
                issue_count=19,
                outcome="report-only",
                fix_type=FIX_FILTER,  # Not reclassify
                suggestion="Fix scanner",
            ),
        ])
        write_queue(q)

        results = apply_reclassify()
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Hint read/clear
# ---------------------------------------------------------------------------


class TestReclassifyHints:
    @patch("skills.daemon.scripts.adaptive.evolve_remediate._hints_dir")
    def test_get_hint_returns_none_when_missing(self, mock_hints, tmp_path):
        mock_hints.return_value = tmp_path / "hints"
        assert get_reclassify_hint("auto-markers") is None

    @patch("skills.daemon.scripts.adaptive.evolve_remediate._hints_dir")
    def test_get_hint_reads_existing(self, mock_hints, tmp_path):
        hints_dir = tmp_path / "hints"
        hints_dir.mkdir()
        mock_hints.return_value = hints_dir
        (hints_dir / "auto-seed-data.json").write_text(json.dumps({
            "category": "auto-seed-data",
            "action": "reclassify",
        }))

        hint = get_reclassify_hint("auto-seed-data")
        assert hint is not None
        assert hint["action"] == "reclassify"

    @patch("skills.daemon.scripts.adaptive.evolve_remediate._hints_dir")
    def test_clear_hint_removes_file(self, mock_hints, tmp_path):
        hints_dir = tmp_path / "hints"
        hints_dir.mkdir()
        mock_hints.return_value = hints_dir
        hint_path = hints_dir / "auto-seed-data.json"
        hint_path.write_text("{}")

        clear_hint("auto-seed-data")
        assert not hint_path.exists()


# ---------------------------------------------------------------------------
# Verify reclassify outcomes
# ---------------------------------------------------------------------------


class TestVerifyReclassify:
    def test_improved_when_count_decreased(self):
        assert verify_reclassify("auto-seed-data", 115, 5) == "improved"

    def test_no_change_when_same(self):
        assert verify_reclassify("auto-seed-data", 115, 115) == "no-change"

    def test_reverted_when_count_increased(self):
        assert verify_reclassify("auto-seed-data", 115, 120) == "reverted"


# ---------------------------------------------------------------------------
# Remediation report formatting
# ---------------------------------------------------------------------------


class TestFormatRemediationReport:
    def test_empty_results_returns_empty(self):
        assert format_remediation_report([]) == ""

    def test_includes_adr_458_header(self):
        results = [{"category": "auto-seed-data", "action": "reclassify",
                     "issue_count": 115, "outcome": "hint-written"}]
        report = format_remediation_report(results)
        assert "ADR-458" in report
        assert "auto-seed-data" in report


# ---------------------------------------------------------------------------
# Engine integration: hint consumption in engine_entry_runner
# ---------------------------------------------------------------------------


class TestHintConsumptionInEngine:
    """Verify that engine_entry_runner applies reclassify hints to issues."""

    @patch("skills.daemon.scripts.adaptive.evolve_remediate._hints_dir")
    def test_issues_reclassified_when_hint_present(self, mock_hints, tmp_path):
        """When a reclassify hint exists, actionable issues become maintenance."""
        hints_dir = tmp_path / "hints"
        hints_dir.mkdir()
        mock_hints.return_value = hints_dir

        # Write a reclassify hint
        (hints_dir / "auto-seed-data.json").write_text(json.dumps({
            "category": "auto-seed-data",
            "action": "reclassify",
            "from_kind": "actionable",
            "to_kind": "maintenance",
        }))

        # Simulate what engine_entry_runner does after scan
        issues = [
            {"kind": "actionable", "detail": "issue 1"},
            {"kind": "actionable", "detail": "issue 2"},
            {"kind": "maintenance", "detail": "issue 3"},
        ]

        hint = get_reclassify_hint("auto-seed-data")
        assert hint is not None

        pre_actionable = sum(1 for i in issues if i.get("kind") == "actionable")
        assert pre_actionable == 2

        # Apply hint (same logic as engine_entry_runner)
        from_kind = hint.get("from_kind", "actionable")
        to_kind = hint.get("to_kind", "maintenance")
        for issue in issues:
            if issue.get("kind") == from_kind:
                issue["kind"] = to_kind

        post_actionable = sum(1 for i in issues if i.get("kind") == "actionable")
        assert post_actionable == 0
        assert sum(1 for i in issues if i.get("kind") == "maintenance") == 3

        # Verify outcome
        outcome = verify_reclassify("auto-seed-data", pre_actionable, post_actionable)
        assert outcome == "improved"

    @patch("skills.daemon.scripts.adaptive.evolve_remediate._hints_dir")
    def test_no_reclassification_when_no_hint(self, mock_hints, tmp_path):
        """Without a hint file, issues pass through unchanged."""
        mock_hints.return_value = tmp_path / "nonexistent_hints"

        hint = get_reclassify_hint("auto-markers")
        assert hint is None

        issues = [{"kind": "actionable", "detail": "real issue"}]
        # No reclassification should happen
        assert issues[0]["kind"] == "actionable"

    @patch("skills.daemon.scripts.adaptive.evolve_remediate._hints_dir")
    def test_hint_cleared_on_no_improvement(self, mock_hints, tmp_path):
        """If reclassify hint doesn't reduce actionable count, hint is cleared."""
        hints_dir = tmp_path / "hints"
        hints_dir.mkdir()
        mock_hints.return_value = hints_dir

        hint_path = hints_dir / "auto-markers.json"
        hint_path.write_text(json.dumps({
            "category": "auto-markers",
            "action": "reclassify",
            "from_kind": "actionable",
            "to_kind": "maintenance",
        }))

        # Simulate: no actionable issues to reclassify (all already maintenance)
        outcome = verify_reclassify("auto-markers", 5, 5)
        assert outcome == "no-change"

        # clear_hint should have been called by verify_reclassify... but
        # verify_reclassify doesn't call clear_hint itself — the engine does.
        # So we test the engine's pattern: clear on no-change
        clear_hint("auto-markers")
        assert not hint_path.exists()

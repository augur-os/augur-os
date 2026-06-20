"""Tests for adaptive heal module (ADR-256)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
SRC_DIR = str(PROJECT_ROOT / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pytest

from skills.daemon.scripts.adaptive.heal import (
    HealFinding,
    HealFixResult,
    InvestigationResult,
    format_heal_fix_report,
    format_heal_report,
    heal_detect,
    heal_fix,
    investigate_finding,
)
from skills.daemon.scripts.adaptive.discovery import AutoCommandEntry
from skills.daemon.scripts.adaptive.trust_ledger import TrustLedger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(loop_name="test-loop", budget=10, categories=None):
    cats = categories or {"cat1": {"enabled": True, "trust": 0.0, "tier": 0}}
    return {
        "engine": {"enabled": True},
        "loops": {loop_name: {"budget": budget, "categories": cats}},
    }


def _make_ledger(tmp_path, config):
    return TrustLedger(config, state_dir=tmp_path)


def _make_entry(name, loop_name="test-loop", scan_result=None):
    module = MagicMock()
    if scan_result is not None:
        module.scan.return_value = scan_result
    else:
        module.scan.return_value = MagicMock(issues=[])
    return AutoCommandEntry(
        name=name, module=module, loop_name=loop_name, tier=0,
    )


# ---------------------------------------------------------------------------
# Detection: failed categories
# ---------------------------------------------------------------------------

class TestDetectFailedCategories:
    def test_detects_consecutive_failures(self, tmp_path):
        config = _make_config()
        ledger = _make_ledger(tmp_path, config)
        cs = ledger.get_loop_state("test-loop").categories["cat1"]
        cs.consecutive_failures = 2
        cs.failure_count = 2
        ledger.save()

        findings = heal_detect(ledger, journal_entries=[])
        failed = [f for f in findings if f.kind == "failed"]
        assert len(failed) == 1
        assert failed[0].loop == "test-loop"
        assert failed[0].category == "cat1"
        assert failed[0].severity == "critical"

    def test_ignores_zero_failures(self, tmp_path):
        config = _make_config()
        ledger = _make_ledger(tmp_path, config)

        findings = heal_detect(ledger, journal_entries=[])
        failed = [f for f in findings if f.kind == "failed"]
        assert len(failed) == 0

    def test_includes_last_error_from_journal(self, tmp_path):
        config = _make_config()
        ledger = _make_ledger(tmp_path, config)
        cs = ledger.get_loop_state("test-loop").categories["cat1"]
        cs.consecutive_failures = 1
        ledger.save()

        entries = [
            {"loop": "test-loop", "category": "cat1", "result": "failure",
             "error": "FileNotFoundError: " + "state" + "/missing"},
        ]
        findings = heal_detect(ledger, journal_entries=entries)
        assert findings[0].last_error == "FileNotFoundError: " + "state" + "/missing"


# ---------------------------------------------------------------------------
# Detection: structurally idle
# ---------------------------------------------------------------------------

class TestDetectStructurallyIdle:
    def test_detects_idle_loop_after_min_cycles(self, tmp_path):
        config = _make_config(categories={
            "cat1": {"enabled": True, "trust": 0.0, "tier": 0},
            "cat2": {"enabled": True, "trust": 0.0, "tier": 1},
        })
        ledger = _make_ledger(tmp_path, config)
        ls = ledger.get_loop_state("test-loop")
        ls.cycle_count = 7

        findings = heal_detect(ledger, journal_entries=[])
        idle = [f for f in findings if f.kind == "structurally_idle"]
        assert len(idle) == 1
        assert idle[0].severity == "warning"
        assert "7 cycles" in idle[0].message

    def test_ignores_loop_below_min_cycles(self, tmp_path):
        config = _make_config()
        ledger = _make_ledger(tmp_path, config)
        ls = ledger.get_loop_state("test-loop")
        ls.cycle_count = 2

        findings = heal_detect(ledger, journal_entries=[])
        idle = [f for f in findings if f.kind == "structurally_idle"]
        assert len(idle) == 0

    def test_not_idle_if_any_category_has_activity(self, tmp_path):
        config = _make_config(categories={
            "cat1": {"enabled": True, "trust": 0.0, "tier": 0},
            "cat2": {"enabled": True, "trust": 0.1, "tier": 1},
        })
        ledger = _make_ledger(tmp_path, config)
        ls = ledger.get_loop_state("test-loop")
        ls.cycle_count = 10
        ls.categories["cat2"].success_count = 1

        findings = heal_detect(ledger, journal_entries=[])
        idle = [f for f in findings if f.kind == "structurally_idle"]
        assert len(idle) == 0

    def test_not_idle_if_no_categories(self, tmp_path):
        """Empty categories dict must not trigger idle detection.

        When the ledger is built from config without register_auto_commands(),
        loops have 0 categories. Python's all() on an empty iterable returns
        True, which previously caused false-positive idle findings for every loop.
        """
        # Build config without categories key (mirrors real adaptive_loops.yaml
        # where loops only define budget/budget_growth_rate)
        config = {
            "engine": {"enabled": True},
            "loops": {"test-loop": {"budget": 10}},
        }
        ledger = _make_ledger(tmp_path, config)
        ls = ledger.get_loop_state("test-loop")
        ls.cycle_count = 100

        findings = heal_detect(ledger, journal_entries=[])
        idle = [f for f in findings if f.kind == "structurally_idle"]
        assert len(idle) == 0


# ---------------------------------------------------------------------------
# Detection: trust-stuck
# ---------------------------------------------------------------------------

class TestDetectTrustStuck:
    def test_detects_stuck_category_info_severity(self, tmp_path):
        config = _make_config()
        ledger = _make_ledger(tmp_path, config)
        ls = ledger.get_loop_state("test-loop")
        ls.cycle_count = 6

        findings = heal_detect(ledger, journal_entries=[])
        stuck = [f for f in findings if f.kind == "trust_stuck"]
        assert len(stuck) == 1
        assert stuck[0].severity == "info"

    def test_escalates_to_warning_at_threshold(self, tmp_path):
        config = _make_config()
        ledger = _make_ledger(tmp_path, config)
        ls = ledger.get_loop_state("test-loop")
        ls.cycle_count = 10

        findings = heal_detect(ledger, journal_entries=[])
        stuck = [f for f in findings if f.kind == "trust_stuck"]
        assert len(stuck) == 1
        assert stuck[0].severity == "warning"

    def test_not_stuck_if_has_successes(self, tmp_path):
        config = _make_config()
        ledger = _make_ledger(tmp_path, config)
        ls = ledger.get_loop_state("test-loop")
        ls.cycle_count = 10
        ls.categories["cat1"].success_count = 1
        ls.categories["cat1"].trust = 0.1

        findings = heal_detect(ledger, journal_entries=[])
        stuck = [f for f in findings if f.kind == "trust_stuck"]
        assert len(stuck) == 0

    def test_skips_failed_categories(self, tmp_path):
        """Failed categories are caught by detect_failed, not trust_stuck."""
        config = _make_config()
        ledger = _make_ledger(tmp_path, config)
        ls = ledger.get_loop_state("test-loop")
        ls.cycle_count = 10
        ls.categories["cat1"].consecutive_failures = 2

        findings = heal_detect(ledger, journal_entries=[])
        stuck = [f for f in findings if f.kind == "trust_stuck"]
        assert len(stuck) == 0


# ---------------------------------------------------------------------------
# Investigation
# ---------------------------------------------------------------------------

class TestInvestigateFinding:
    def test_failed_with_known_error_pattern(self, tmp_path):
        finding = HealFinding(
            kind="failed", severity="critical",
            loop="test-loop", category="cat1",
            message="1 failure", last_error="FileNotFoundError: " + "state" + "/foo/bar",
        )
        entry = _make_entry("cat1")
        result = investigate_finding(
            finding, entry=entry, project_root=tmp_path, journal_entries=[],
        )
        assert result.root_cause is not None
        assert result.pattern == "missing_path"
        assert ("state" + "/foo/bar") in result.root_cause

    def test_idle_investigation(self, tmp_path):
        finding = HealFinding(
            kind="structurally_idle", severity="warning",
            loop="test-loop", category=None,
            message="7 cycles idle",
            context={"cycle_count": 7},
        )
        result = investigate_finding(
            finding, entry=None, project_root=tmp_path, journal_entries=[],
        )
        assert result.root_cause is not None
        assert result.pattern == "empty_data_dir"

    def test_unidentifiable_error(self, tmp_path):
        finding = HealFinding(
            kind="failed", severity="critical",
            loop="test-loop", category="cat1",
            message="1 failure", last_error="Something very unusual happened",
        )
        entry = _make_entry("cat1")
        result = investigate_finding(
            finding, entry=entry, project_root=tmp_path, journal_entries=[],
        )
        assert result.pattern == "unknown"
        assert result.fixable is False

    def test_module_error_not_fixable(self, tmp_path):
        finding = HealFinding(
            kind="failed", severity="critical",
            loop="test-loop", category="cat1",
            message="1 failure", last_error="ModuleNotFoundError: No module named 'foo'",
        )
        result = investigate_finding(
            finding, entry=None, project_root=tmp_path, journal_entries=[],
        )
        assert result.pattern == "module_error"
        assert result.fixable is False

    def test_trust_stuck_dry_scan_empty(self, tmp_path):
        finding = HealFinding(
            kind="trust_stuck", severity="info",
            loop="test-loop", category="cat1",
            message="stuck",
        )
        entry = _make_entry("cat1")
        entry.module.scan.return_value = MagicMock(issues=[])
        result = investigate_finding(
            finding, entry=entry, project_root=tmp_path, journal_entries=[],
        )
        assert result.pattern == "scan_empty"
        assert result.fixable is False

    def test_trust_stuck_dry_scan_has_issues(self, tmp_path):
        finding = HealFinding(
            kind="trust_stuck", severity="info",
            loop="test-loop", category="cat1",
            message="stuck",
        )
        entry = _make_entry("cat1")
        entry.module.scan.return_value = MagicMock(issues=[{"id": "1"}])
        result = investigate_finding(
            finding, entry=entry, project_root=tmp_path, journal_entries=[],
        )
        assert result.pattern == "fix_blocked"
        assert result.fixable is True


# ---------------------------------------------------------------------------
# Fix pipeline
# ---------------------------------------------------------------------------

class TestHealFix:
    def test_fixes_missing_runtime_path(self, tmp_path):
        config = _make_config()
        ledger = _make_ledger(tmp_path, config)
        cs = ledger.get_loop_state("test-loop").categories["cat1"]
        cs.consecutive_failures = 1
        cs.failure_count = 1
        ledger.save()

        finding = HealFinding(
            kind="failed", severity="critical",
            loop="test-loop", category="cat1",
            message="1 failure",
            last_error=f"FileNotFoundError: {tmp_path / ('state' + '/missing/dir')}",
        )
        entry = _make_entry("cat1")
        entry.module.scan.return_value = MagicMock(issues=[{"id": "1"}])
        entry.module.fix.return_value = MagicMock(success=True, changes=[], actions=[], summary="ok")

        results = heal_fix(
            findings=[finding], ledger=ledger, registry={"cat1": entry},
            project_root=tmp_path, journal_entries=[], force=False,
        )
        assert len(results) == 1
        assert results[0].outcome == "fixed"
        # Verify failure counters were reset
        cs_after = ledger.get_loop_state("test-loop").categories["cat1"]
        assert cs_after.consecutive_failures == 0

    def test_skips_disabled_category_without_force(self, tmp_path):
        config = _make_config()
        ledger = _make_ledger(tmp_path, config)
        cs = ledger.get_loop_state("test-loop").categories["cat1"]
        cs.consecutive_failures = 1
        cs.disable_count = 1
        ledger.save()

        finding = HealFinding(
            kind="failed", severity="critical",
            loop="test-loop", category="cat1",
            message="1 failure", last_error="some error",
        )

        results = heal_fix(
            findings=[finding], ledger=ledger, registry={},
            project_root=tmp_path, journal_entries=[], force=False,
        )
        assert len(results) == 1
        assert results[0].outcome == "skipped"

    def test_force_promotes_disabled_category(self, tmp_path):
        config = _make_config()
        ledger = _make_ledger(tmp_path, config)
        cs = ledger.get_loop_state("test-loop").categories["cat1"]
        cs.consecutive_failures = 1
        cs.disable_count = 1
        ledger.save()

        finding = HealFinding(
            kind="failed", severity="critical",
            loop="test-loop", category="cat1",
            message="1 failure",
            last_error=f"FileNotFoundError: {tmp_path / ('state' + '/x')}",
        )
        entry = _make_entry("cat1")
        entry.module.scan.return_value = MagicMock(issues=[])

        results = heal_fix(
            findings=[finding], ledger=ledger, registry={"cat1": entry},
            project_root=tmp_path, journal_entries=[], force=True,
        )
        assert len(results) == 1
        assert results[0].outcome == "fixed"
        # Verify promote was called (resets disable_count)
        cs_after = ledger.get_loop_state("test-loop").categories["cat1"]
        assert cs_after.disable_count == 0

    def test_unresolved_when_verify_fails(self, tmp_path):
        config = _make_config()
        ledger = _make_ledger(tmp_path, config)
        cs = ledger.get_loop_state("test-loop").categories["cat1"]
        cs.consecutive_failures = 1
        ledger.save()

        finding = HealFinding(
            kind="failed", severity="critical",
            loop="test-loop", category="cat1",
            message="1 failure",
            last_error=f"FileNotFoundError: {tmp_path / ('state' + '/y')}",
        )
        entry = _make_entry("cat1")
        entry.module.scan.side_effect = FileNotFoundError("still broken")

        results = heal_fix(
            findings=[finding], ledger=ledger, registry={"cat1": entry},
            project_root=tmp_path, journal_entries=[], force=False,
        )
        assert len(results) == 1
        assert results[0].outcome == "unresolved"

    def test_unresolved_for_unfixable_pattern(self, tmp_path):
        config = _make_config()
        ledger = _make_ledger(tmp_path, config)
        cs = ledger.get_loop_state("test-loop").categories["cat1"]
        cs.consecutive_failures = 1
        ledger.save()

        finding = HealFinding(
            kind="failed", severity="critical",
            loop="test-loop", category="cat1",
            message="1 failure",
            last_error="ModuleNotFoundError: No module named 'missing'",
        )

        results = heal_fix(
            findings=[finding], ledger=ledger, registry={},
            project_root=tmp_path, journal_entries=[], force=False,
        )
        assert len(results) == 1
        assert results[0].outcome == "unresolved"


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

class TestFormatHealReport:
    def test_formats_findings_by_severity(self):
        findings = [
            HealFinding(
                kind="failed", severity="critical",
                loop="code-quality", category="auto-lint",
                message="1 consecutive failure(s) (tier 1, disable_count=0)",
                last_error="ESLint config not found",
            ),
            HealFinding(
                kind="structurally_idle", severity="warning",
                loop="command-evolution", category=None,
                message="7 cycles, all categories at zero",
            ),
            HealFinding(
                kind="trust_stuck", severity="info",
                loop="code-quality", category="auto-markers",
                message="trust=0.00 after 9 cycles",
            ),
        ]
        report = format_heal_report(findings)
        assert "CRITICAL: 1 failed" in report
        assert "auto-lint" in report
        assert "WARNING: 1 structurally idle" in report
        assert "command-evolution" in report
        assert "1 trust-stuck" in report

    def test_empty_findings(self):
        report = format_heal_report([])
        assert "healthy" in report.lower()


class TestFormatHealFixReport:
    def test_formats_mixed_outcomes(self):
        results = [
            HealFixResult(
                finding=HealFinding(kind="failed", severity="critical",
                    loop="code-quality", category="auto-lint", message="1 failure"),
                outcome="fixed",
                fix_description="Created missing directory",
                verify_result="verified",
            ),
            HealFixResult(
                finding=HealFinding(kind="failed", severity="critical",
                    loop="testing", category="auto-test-api", message="1 failure"),
                outcome="skipped",
                fix_description="disable_count=2, use --force",
            ),
            HealFixResult(
                finding=HealFinding(kind="failed", severity="critical",
                    loop="testing", category="auto-test-pages", message="1 failure"),
                outcome="unresolved",
                fix_description="Root cause: timeout",
            ),
        ]
        report = format_heal_fix_report(results)
        assert "FIXED: 1" in report
        assert "SKIPPED: 1" in report
        assert "UNRESOLVED: 1" in report
        assert "auto-lint" in report
        assert "auto-test-api" in report

    def test_empty_results(self):
        report = format_heal_fix_report([])
        assert "No findings" in report

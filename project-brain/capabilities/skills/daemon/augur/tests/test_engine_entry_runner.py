"""Auto-generated importability test for engine_entry_runner."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.lib.ops_protocol import FixResult, OpsExecutionDecision, ScanResult, declare_ops_capabilities

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_engine_entry_runner_importable():
    """Verify that engine_entry_runner can be imported without errors."""
    mod = importlib.import_module("skills.daemon.scripts.adaptive.engine_entry_runner")
    assert mod is not None


def test_build_platform_category_report_marks_skipped_outcome():
    mod = importlib.import_module("skills.daemon.scripts.adaptive.engine_entry_runner")

    report = mod.build_platform_category_report(
        entry_name="auto-test",
        trust_before=0.2,
        difficulty=1,
        decision=OpsExecutionDecision(
            run_scan=False,
            allow_fix=False,
            outcome="skipped_unsupported",
            fix_mode="unsupported",
            skip_reason="launchd-only check",
        ),
    )

    assert report.name == "auto-test"
    assert report.status == "skipped"
    assert report.outcome == "skipped_unsupported"
    assert report.action_summary == "launchd-only check"


def test_run_entry_scan_fix_skips_unsupported_platform_entries():
    mod = importlib.import_module("skills.daemon.scripts.adaptive.engine_entry_runner")

    class _Ledger:
        def check_allowed(self, loop_name, entry_name):
            return True

        def get_difficulties(self, loop_name):
            return {"auto-test": 1}

    engine = SimpleNamespace(
        ledger=_Ledger(),
        _config={"loops": {"hardening": {}}},
        _project_root=PROJECT_ROOT,
        _snapshot_fingerprint=lambda *args, **kwargs: "snap",
        _should_short_circuit_classify=lambda *args, **kwargs: False,
        _two_phase_enabled=lambda *args, **kwargs: False,
    )
    loop_state = SimpleNamespace(categories={}, cycle_count=1)
    entry = SimpleNamespace(
        name="auto-test",
        trigger="nightly",
        config={},
        capabilities=declare_ops_capabilities(
            platforms=("macos",),
            windows_fix_mode="unsupported",
            skip_reason="launchd-only check",
        ),
    )

    cat_reports: list = []
    original_platform = sys.platform
    sys.platform = "win32"
    try:
        continued = mod.run_entry_scan_fix(
            engine=engine,
            loop_name="hardening",
            loop_state=loop_state,
            entry=entry,
            trigger_filter=None,
            shared_snapshot={},
            results=[],
            cat_reports=cat_reports,
            broken_categories=set(),
            degraded_categories=set(),
            invalidated_categories=set(),
            dep_invalidations={},
            cycle_state={"any_issues_found": False},
            allow_invalidations=False,
        )
    finally:
        sys.platform = original_platform

    assert continued is True
    assert len(cat_reports) == 1
    assert cat_reports[0].status == "skipped"
    assert cat_reports[0].outcome == "skipped_unsupported"


def test_run_entry_scan_fix_runs_fix_when_clean_scan_requests_it(monkeypatch):
    mod = importlib.import_module("skills.daemon.scripts.adaptive.engine_entry_runner")

    class _Ledger:
        def check_allowed(self, loop_name, entry_name):
            return True

        def get_difficulties(self, loop_name):
            return {"auto-agent-digest": 3}

    engine = SimpleNamespace(
        ledger=_Ledger(),
        _config={"loops": {"knowledge-enrichment": {}}},
        _project_root=PROJECT_ROOT,
        _snapshot_fingerprint=lambda *args, **kwargs: "snap",
        _should_short_circuit_classify=lambda *args, **kwargs: False,
        _two_phase_enabled=lambda *args, **kwargs: False,
        _normalize_issue=lambda entry_name, issue: issue,
        _count_issue_kinds=lambda issues: {},
        _issue_fingerprint_sets=lambda issues: (set(), set()),
        _yield_class=lambda *args, **kwargs: ("clean", 0, 0, 0),
    )
    loop_state = SimpleNamespace(categories={}, cycle_count=1)
    entry = SimpleNamespace(
        name="auto-agent-digest",
        trigger="nightly",
        config={},
        module=SimpleNamespace(
            scan=lambda ctx: ScanResult(
                issues=[],
                summary="scan completed",
                items_scanned=0,
                run_fix_on_clean=True,
            ),
            fix=lambda ctx, issues: FixResult(
                success=True,
                changes=["wrote digest-hot.md"],
                summary="Compiled hot + warm digest.",
                fix_type="sync",
            ),
        ),
        capabilities=declare_ops_capabilities(),
    )

    run_fix_phase = MagicMock(return_value=True)
    monkeypatch.setattr(mod, "run_fix_phase", run_fix_phase)

    continued = mod.run_entry_scan_fix(
        engine=engine,
        loop_name="knowledge-enrichment",
        loop_state=loop_state,
        entry=entry,
        trigger_filter=None,
        shared_snapshot={},
        results=[],
        cat_reports=[],
        broken_categories=set(),
        degraded_categories=set(),
        invalidated_categories=set(),
        dep_invalidations={},
        cycle_state={"any_issues_found": False},
        allow_invalidations=False,
        no_coverage_categories=set(),
    )

    assert continued is True
    run_fix_phase.assert_called_once()
    assert run_fix_phase.call_args.kwargs["issues"] == []

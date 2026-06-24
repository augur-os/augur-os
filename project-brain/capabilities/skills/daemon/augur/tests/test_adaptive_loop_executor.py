# TODO_CLEANUP: This file is 1447 lines — consider splitting into smaller modules
"""Tests for pending semantics in adaptive_loop_executor."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

DAEMON_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
SRC_DIR = str(PROJECT_ROOT / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from skills.daemon.scripts.adaptive.engine import AdaptiveLoopEngine
import adaptive_loop_executor
from skills.daemon.scripts.adaptive.reporting import CategoryReport, CycleReport
from skills.daemon.scripts.adaptive.cycle_helpers import save_cycle_report
from skills.daemon.scripts.adaptive.loop_reporter import generate_executive_report
from skills.daemon.scripts.routine_orchestrator.ledger_view import JournalRecord


class _Module:
    def __init__(self, issues):
        self.name = "test-mod"
        self._issues = issues
        self.last_ctx = None

    def scan(self, ctx):
        self.last_ctx = ctx
        from dataclasses import dataclass, field as dc_field

        @dataclass
        class SR:
            issues: list = dc_field(default_factory=list)
            summary: str = ""
            severity: str = "info"
            health: str = "verified"

        return SR(issues=self._issues, summary=f"{len(self._issues)} issues")

    def fix(self, ctx, issues):
        raise AssertionError("pending scan should not call fix()")


def _make_entry(name, loop_name, module):
    from dataclasses import dataclass, field as dc_field

    @dataclass
    class FakeEntry:
        name: str
        module: object
        loop_name: str
        tier: int = 0
        trigger: str = "nightly"
        initial_trust: float = 0.0
        config: dict = dc_field(default_factory=dict)
        plugin_root: Path = dc_field(default_factory=lambda: Path.cwd())

    return FakeEntry(name=name, module=module, loop_name=loop_name)


def test_scan_pending_counts_only_actionable(tmp_path):
    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {
            "test-loop": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {
                    "cat-actionable": {"enabled": True, "trust": 0.5, "tier": 0},
                    "cat-maintenance": {"enabled": True, "trust": 0.5, "tier": 0},
                },
            },
        },
    }
    engine = AdaptiveLoopEngine(config, runtime_dir=tmp_path, project_root=tmp_path)
    registry = {
        "cat-actionable": _make_entry(
            "cat-actionable",
            "test-loop",
            _Module([{"detail": "broken route", "kind": "actionable"}]),
        ),
        "cat-maintenance": _make_entry(
            "cat-maintenance",
            "test-loop",
            _Module([{"detail": "stale index", "kind": "maintenance"}]),
        ),
    }
    engine.register_auto_commands(registry)

    pending, total = adaptive_loop_executor._scan_pending_issues(
        engine=engine,
        config=config,
        project_root=tmp_path,
    )

    assert total == 1
    actionable = next(row for row in pending if row["command"] == "cat-actionable")
    maintenance = next(row for row in pending if row["command"] == "cat-maintenance")
    assert actionable["count"] == 1
    assert actionable["scan_duration_ms"] >= 0
    assert maintenance["count"] == 0
    assert maintenance["maintenance_count"] == 1
    assert maintenance["scan_duration_ms"] >= 0


def test_cycle_report_format_does_not_label_maintenance_report_only_as_manual():
    report = CycleReport(
        loop_name="testing",
        categories=[
            CategoryReport(
                name="auto-e2e-pipeline",
                trust_before=0.0,
                trust_after=0.0,
                difficulty_before=0,
                difficulty_after=0,
                status="ok",
                outcome="report-only",
                issue_count=1,
                maintenance_count=1,
                manual_count=0,
                action_summary="1 evolution gap(s) reported",
            ),
            CategoryReport(
                name="auto-test-build",
                trust_before=0.4,
                trust_after=0.5,
                difficulty_before=1,
                difficulty_after=1,
                status="ok",
                outcome="clean",
            ),
        ],
    )

    header = report.format().splitlines()[0]

    assert "1 maintenance" in header
    assert "manual" not in header


def test_save_cycle_report_counts_only_manual_report_only_as_manual_followup(tmp_path):
    report = CycleReport(
        loop_name="testing",
        categories=[
            CategoryReport(
                name="auto-e2e-pipeline",
                trust_before=0.0,
                trust_after=0.0,
                difficulty_before=0,
                difficulty_after=0,
                status="ok",
                outcome="report-only",
                issue_count=1,
                maintenance_count=1,
                manual_count=0,
                action_summary="1 evolution gap(s) reported",
            ),
            CategoryReport(
                name="manual-scanner",
                trust_before=0.0,
                trust_after=0.0,
                difficulty_before=0,
                difficulty_after=0,
                status="ok",
                outcome="report-only",
                issue_count=1,
                manual_count=1,
                action_summary="manual review needed",
            ),
        ],
    )
    loop_state = SimpleNamespace(categories={}, cycle_count=1, budget_remaining=1)

    save_cycle_report(tmp_path, report, loop_state)

    data = json.loads((tmp_path / "reports" / "testing-latest.json").read_text())
    assert data["cycle_summary"]["maintenance_issues"] == 1
    assert data["cycle_summary"]["manual_issues"] == 1
    assert data["cycle_summary"]["manual_followup"] == 1


def test_run_all_by_trigger_skips_codex_owned_entries(tmp_path):
    from adaptive.discovery import AutoCommandEntry

    class _SchedulerOwnedModule:
        name = "auto-nightly-testing"

        @staticmethod
        def scan(ctx):
            raise AssertionError("codex-owned nightly entry should not execute")

        @staticmethod
        def fix(ctx, issues):
            return None

    engine = AdaptiveLoopEngine(
        {
            "engine": {"enabled": True},
            "loops": {
                "testing": {
                    "enabled": True,
                    "trigger": "nightly",
                    "budget": 2,
                    "budget_growth_rate": 1,
                    "categories": {},
                }
            },
        },
        runtime_dir=tmp_path,
        project_root=tmp_path,
    )
    engine.register_auto_commands(
        {
            "auto-nightly-testing": AutoCommandEntry(
                name="auto-nightly-testing",
                module=_SchedulerOwnedModule,
                loop_name="testing",
                trigger="nightly",
                scheduler="codex",
            )
        }
    )

    result = engine.run_all_by_trigger("nightly")
    assert result == {}


def test_scan_pending_builds_shared_snapshot_once(tmp_path):
    config = {
        "engine": {"enabled": True, "verify_command": "", "shared_snapshot": True},
        "loops": {
            "test-loop": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {
                    "cat-actionable": {"enabled": True, "trust": 0.5, "tier": 0},
                },
            },
        },
    }
    engine = AdaptiveLoopEngine(config, runtime_dir=tmp_path, project_root=tmp_path)
    module = _Module([{"detail": "broken route", "kind": "actionable"}])
    registry = {
        "cat-actionable": _make_entry(
            "cat-actionable",
            "test-loop",
            module,
        ),
    }
    engine.register_auto_commands(registry)

    snapshot = {"version": 1, "skill_count": 2, "api_route_count": 1}
    with patch(
        "adaptive.loop_reporter.build_shared_snapshot", return_value=snapshot
    ) as mock_snapshot:
        pending, total = adaptive_loop_executor._scan_pending_issues(
            engine=engine,
            config=config,
            project_root=tmp_path,
        )

    assert total == 1
    assert pending[0]["count"] == 1
    assert mock_snapshot.call_count == 1
    assert module.last_ctx is not None
    assert module.last_ctx.shared_snapshot is snapshot


def test_write_cli_metrics_persists_report(tmp_path):
    output = adaptive_loop_executor._write_cli_metrics(
        tmp_path,
        "pending",
        {
            "mode": "pending",
            "total_duration_ms": 42,
            "executor_overhead_ms": 5,
        },
    )

    assert output == tmp_path / "adaptive" / "reports" / "executor-pending-latest.json"
    data = json.loads(output.read_text())
    assert data["mode"] == "pending"
    assert data["total_duration_ms"] == 42
    assert data["executor_overhead_ms"] == 5
    assert "generated_at" in data


def test_write_cli_metrics_uses_per_loop_run_filename(tmp_path):
    output = adaptive_loop_executor._write_cli_metrics(
        tmp_path,
        "run",
        {
            "mode": "run",
            "target_loop": "command-evolution",
            "total_duration_ms": 42,
        },
    )

    assert output == (
        tmp_path / "adaptive" / "reports" / "executor-run-command-evolution-latest.json"
    )
    data = json.loads(output.read_text())
    assert data["mode"] == "run"
    assert data["target_loop"] == "command-evolution"


def test_wiki_compile_handoff_formats_for_knowledge_enrichment_findings():
    report = CycleReport(
        loop_name="knowledge-enrichment",
        categories=[
            CategoryReport(
                name="auto-wiki-maintenance",
                trust_before=0.0,
                trust_after=0.0,
                difficulty_before=2,
                difficulty_after=2,
                status="degraded",
                outcome="report-only",
                issue_count=3,
                actionable_count=3,
                action_summary="3 wiki maintenance issue(s) across 25 pages",
            )
        ],
    )

    handoff = adaptive_loop_executor._format_wiki_compile_handoff(report)

    assert handoff is not None
    assert "/auto-wiki-maintenance --compile --cycles 5 --limit 25 --evolve" in handoff
    assert "/auto-wiki-maintenance --reset --cycles 5 --limit 25 --evolve" in handoff


def test_wiki_compile_handoff_skips_clean_knowledge_enrichment_report():
    report = CycleReport(
        loop_name="knowledge-enrichment",
        categories=[
            CategoryReport(
                name="auto-wiki-maintenance",
                trust_before=0.0,
                trust_after=0.0,
                difficulty_before=2,
                difficulty_after=2,
                status="ok",
                outcome="clean",
                action_summary="0 wiki maintenance issue(s) across 25 pages",
            )
        ],
    )

    assert adaptive_loop_executor._format_wiki_compile_handoff(report) is None


def test_resolve_execution_project_root_prefers_cli_worktree(tmp_path):
    worktree = tmp_path / "worktree"
    inherited_root = tmp_path / "main"
    worktree.mkdir()
    inherited_root.mkdir()
    (worktree / ".git").write_text("gitdir: /tmp/dev-loops\n", encoding="utf-8")
    (worktree / "project.yaml").write_text("name: Augur\n", encoding="utf-8")

    with patch.dict(os.environ, {"AUGUR_ROOT": str(inherited_root)}, clear=False):
        adaptive_loop_executor.invalidate_project_cache()
        resolved = adaptive_loop_executor._resolve_execution_project_root(
            MagicMock(loop=False),
            cwd=worktree,
        )
        assert Path(os.environ["AUGUR_ROOT"]) == worktree

    assert resolved == worktree


def test_run_all_requires_linked_worktree(tmp_path):
    main_checkout = tmp_path / "main"
    main_checkout.mkdir()
    (main_checkout / ".git").mkdir()

    with pytest.raises(SystemExit, match="requires an isolated git worktree"):
        adaptive_loop_executor._enforce_run_all_worktree(main_checkout)


def test_run_all_allows_linked_worktree(tmp_path):
    linked_worktree = tmp_path / "routines-2026-04-30"
    linked_worktree.mkdir()
    (linked_worktree / ".git").write_text(
        "gitdir: /tmp/main/.git/worktrees/dev-loops\n",
        encoding="utf-8",
    )

    adaptive_loop_executor._enforce_run_all_worktree(linked_worktree)


def test_normalize_cli_args_supports_report_mode():
    assert adaptive_loop_executor._normalize_cli_args(["report", "--days", "3"]) == [
        "--report",
        "--days",
        "3",
    ]


def test_normalize_cli_args_supports_heal_mode():
    assert adaptive_loop_executor._normalize_cli_args(["heal", "--fix", "--force"]) == [
        "--heal",
        "--fix",
        "--force",
    ]


def test_run_evolve_phase_no_reports_is_noop(tmp_path):
    engine = AdaptiveLoopEngine(
        {"engine": {"enabled": True, "verify_command": ""}, "loops": {}},
        runtime_dir=tmp_path,
        project_root=tmp_path,
    )

    duration = adaptive_loop_executor._run_evolve_phase(
        engine=engine,
        project_root=tmp_path,
        run_start_iso="2026-03-22T00:00:00+00:00",
        reports=[],
    )

    assert duration == 0


def test_generate_executive_report_includes_follow_up_items(tmp_path):
    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {
            "hardening": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {
                    "auto-adr-lifecycle": {"enabled": True, "trust": 0.2, "tier": 0},
                },
            },
        },
    }
    engine = AdaptiveLoopEngine(config, runtime_dir=tmp_path, project_root=tmp_path)
    reports_dir = tmp_path / "adaptive" / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "hardening-latest.json").write_text(
        json.dumps(
            {
                "categories": [
                    {
                        "name": "auto-adr-lifecycle",
                        "outcome": "report-only",
                        "issue_count": 4,
                        "manual_count": 0,
                        "action_summary": "Structural fixes deferred at d0",
                    }
                ],
                "next_actions": ["Fix 4 issue(s) in auto-adr-lifecycle (manual)"],
            }
        )
    )
    engine.journal_writer.log(
        loop="hardening",
        action="fix-deferred",
        category="auto-adr-lifecycle",
        result="deferred",
        error="Structural fixes deferred at d0",
    )
    coverage_report = tmp_path / "docs" / "generated"
    coverage_report.mkdir(parents=True)
    (coverage_report / "coverage-gaps-report.md").write_text(
        "# Test Coverage Gaps Report\n\n## 12 Untested Python Modules (report-only)\n",
        encoding="utf-8",
    )

    output = generate_executive_report(engine, config, days=1)

    assert "## Top Items To Follow Up" in output
    assert "auto-adr-lifecycle" in output
    assert "12 modules still in the coverage gap report" in output


def test_generate_executive_report_calls_out_design_written_items(tmp_path):
    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {
            "observability": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {
                    "ownership-shift": {"enabled": True, "trust": 0.2, "tier": 0},
                },
            },
        },
    }
    engine = AdaptiveLoopEngine(config, runtime_dir=tmp_path, project_root=tmp_path)
    reports_dir = tmp_path / "adaptive" / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "observability-latest.json").write_text(
        json.dumps(
            {
                "categories": [
                    {
                        "name": "ownership-shift",
                        "outcome": "design-written",
                        "issue_count": 2,
                        "action_summary": "Design gate written at project-brain/decisions/adrs/ADR-999.md",
                    }
                ],
                "next_actions": [],
            }
        )
    )

    output = generate_executive_report(engine, config, days=1)

    assert "design-written:1" in output
    assert "design gate written, rerun at higher difficulty" in output


def test_generate_executive_report_hides_superseded_failures(tmp_path):
    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {
            "testing": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {
                    "auto-test-links": {"enabled": True, "trust": 0.2, "tier": 0},
                },
            },
        },
    }
    engine = AdaptiveLoopEngine(config, runtime_dir=tmp_path, project_root=tmp_path)
    reports_dir = tmp_path / "adaptive" / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "testing-latest.json").write_text(
        json.dumps(
            {
                "categories": [
                    {
                        "name": "auto-test-links",
                        "outcome": "clean",
                        "issue_count": 0,
                        "action_summary": "clean scan",
                    }
                ],
                "next_actions": [],
            }
        ),
        encoding="utf-8",
    )
    now = datetime.now(timezone.utc)
    engine.journal_reader = SimpleNamespace(
        read_all=lambda: [
            JournalRecord(
                loop="testing",
                action="scan",
                category="auto-test-links",
                result="failure",
                timestamp=(now - timedelta(minutes=2)).isoformat(),
                error="Scanner script not found",
            ),
            JournalRecord(
                loop="testing",
                action="clean-scan",
                category="auto-test-links",
                result="success",
                timestamp=(now - timedelta(minutes=1)).isoformat(),
            ),
        ]
    )

    output = generate_executive_report(engine, config, days=1)

    assert "Scanner script not found" not in output
    assert "No failures or deferred fixes in the selected window." in output


def test_generate_executive_report_uses_latest_report_to_clear_failures(tmp_path):
    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {
            "knowledge-enrichment": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {
                    "reindex-project": {"enabled": True, "trust": 0.2, "tier": 0},
                },
            },
        },
    }
    engine = AdaptiveLoopEngine(config, runtime_dir=tmp_path, project_root=tmp_path)
    reports_dir = tmp_path / "adaptive" / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "knowledge-enrichment-latest.json").write_text(
        json.dumps(
            {
                "categories": [
                    {
                        "name": "reindex-project",
                        "outcome": "clean",
                        "issue_count": 0,
                        "action_summary": "clean scan",
                    }
                ],
                "next_actions": [],
            }
        ),
        encoding="utf-8",
    )
    now = datetime.now(timezone.utc)
    engine.journal_reader = SimpleNamespace(
        read_all=lambda: [
            JournalRecord(
                loop="knowledge-enrichment",
                action="fix",
                category="reindex-project",
                result="failure",
                timestamp=(now - timedelta(minutes=2)).isoformat(),
                error="No module named 'skills.ingest'",
            ),
        ]
    )

    output = generate_executive_report(engine, config, days=1)

    assert "No module named 'skills.ingest'" not in output
    assert "No failures or deferred fixes in the selected window." in output


def test_generate_executive_report_ignores_unknown_loop_failures(tmp_path):
    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {
            "testing": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {
                    "auto-test-pytest": {"enabled": True, "trust": 0.2, "tier": 0},
                },
            },
        },
    }
    engine = AdaptiveLoopEngine(config, runtime_dir=tmp_path, project_root=tmp_path)
    now = datetime.now(timezone.utc)
    engine.journal_reader = SimpleNamespace(
        read_all=lambda: [
            JournalRecord(
                loop="auto-test-pytest",
                action="run",
                category="engine",
                result="failure",
                timestamp=(now - timedelta(minutes=1)).isoformat(),
                error="ValueError: Unknown loop 'auto-test-pytest'",
            ),
        ]
    )

    output = generate_executive_report(engine, config, days=1)

    assert "Unknown loop 'auto-test-pytest'" not in output
    assert "No failures or deferred fixes in the selected window." in output


def test_rebind_repo_env_for_direct_cli_updates_inherited_root(monkeypatch):
    repo_root = adaptive_loop_executor._current_repo_root()
    monkeypatch.setenv("AUGUR_ROOT", "/Users/example/Projects/Augur")
    monkeypatch.delenv("AUGUR_CORE", raising=False)
    monkeypatch.delenv("AUGUR_REPO", raising=False)

    resolved = adaptive_loop_executor._rebind_repo_env_for_direct_cli(loop_mode=False)

    assert resolved == repo_root
    assert Path(os.environ["AUGUR_ROOT"]).resolve() == repo_root
    assert Path(os.environ["AUGUR_CORE"]).resolve() == repo_root
    assert Path(os.environ["AUGUR_REPO"]).resolve() == repo_root


def test_rebind_repo_env_for_direct_cli_preserves_loop_mode(monkeypatch):
    monkeypatch.setenv("AUGUR_ROOT", "/Users/example/Projects/Augur")

    adaptive_loop_executor._rebind_repo_env_for_direct_cli(loop_mode=True)

    assert os.environ["AUGUR_ROOT"] == "/Users/example/Projects/Augur"


def test_main_report_mode_calls_engine_generate_report(tmp_path, capsys):
    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {},
    }
    engine = MagicMock()
    engine.generate_report.return_value = "# report body"
    with (
        patch.object(adaptive_loop_executor, "load_config", return_value=config),
        patch.object(adaptive_loop_executor, "get_runtime_dir", return_value=tmp_path),
        patch.object(
            adaptive_loop_executor,
            "_resolve_execution_project_root",
            return_value=tmp_path,
        ),
        patch.object(adaptive_loop_executor, "AdaptiveLoopEngine", return_value=engine),
        patch.object(adaptive_loop_executor, "discover_auto_commands", return_value={}),
        patch.object(
            adaptive_loop_executor,
            "write_cli_metrics",
            return_value=tmp_path
            / "adaptive"
            / "reports"
            / "executor-report-latest.json",
        ),
        patch.object(
            sys, "argv", ["adaptive_loop_executor.py", "report", "--days", "3"]
        ),
    ):
        adaptive_loop_executor.main()

    engine.generate_report.assert_called_once_with(days=3)
    assert "# report body" in capsys.readouterr().out


def test_main_heal_fix_mode_runs_heal_pipeline(tmp_path, capsys):
    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {},
    }
    engine = MagicMock()
    finding = MagicMock()
    fix_result = MagicMock()
    registry = {"auto-test": SimpleNamespace(loop_name="testing")}

    with (
        patch.object(adaptive_loop_executor, "load_config", return_value=config),
        patch.object(adaptive_loop_executor, "get_runtime_dir", return_value=tmp_path),
        patch.object(
            adaptive_loop_executor,
            "_resolve_execution_project_root",
            return_value=tmp_path,
        ),
        patch.object(adaptive_loop_executor, "AdaptiveLoopEngine", return_value=engine),
        patch.object(
            adaptive_loop_executor, "discover_auto_commands", return_value=registry
        ),
        patch.object(
            adaptive_loop_executor, "heal_detect", return_value=[finding]
        ) as mock_detect,
        patch.object(
            adaptive_loop_executor, "heal_fix", return_value=[fix_result]
        ) as mock_fix,
        patch.object(
            adaptive_loop_executor,
            "format_heal_fix_report",
            return_value="# heal fix report",
        ),
        patch.object(
            adaptive_loop_executor,
            "write_cli_metrics",
            return_value=tmp_path
            / "adaptive"
            / "reports"
            / "executor-heal-latest.json",
        ),
        patch.object(sys, "argv", ["adaptive_loop_executor.py", "heal", "--fix"]),
    ):
        adaptive_loop_executor.main()

    mock_detect.assert_called_once_with(engine.ledger, engine.journal_reader.read_all())
    mock_fix.assert_called_once_with(
        [finding],
        ledger=engine.ledger,
        registry=registry,
        project_root=tmp_path,
        journal_entries=engine.journal_reader.read_all(),
        force=False,
    )
    assert "# heal fix report" in capsys.readouterr().out


def _make_cli_engine():
    engine = MagicMock()
    engine.loops = {"alpha": object()}
    engine._auto_loop_names = {"beta"}
    engine.ledger._loops = {"alpha": object(), "beta": object()}
    engine.ledger.get_loop_state.return_value = SimpleNamespace(
        categories={"cat-one": object(), "cat-two": object()}
    )
    engine.journal_reader.read_all.return_value = []
    return engine


def _run_public_dev_loops_command(tmp_path, argv, engine):
    with (
        patch.object(
            adaptive_loop_executor,
            "load_config",
            return_value={"engine": {"enabled": True}, "loops": {}},
        ),
        patch.object(adaptive_loop_executor, "get_runtime_dir", return_value=tmp_path),
        patch.object(
            adaptive_loop_executor,
            "_resolve_execution_project_root",
            return_value=tmp_path,
        ),
        patch.object(adaptive_loop_executor, "AdaptiveLoopEngine", return_value=engine),
        patch.object(adaptive_loop_executor, "discover_auto_commands", return_value={}),
        patch.object(sys, "argv", ["adaptive_loop_executor.py", *argv]),
    ):
        adaptive_loop_executor.main()


def test_public_enable_calls_ledger_and_prints_success(tmp_path, capsys):
    engine = _make_cli_engine()

    _run_public_dev_loops_command(tmp_path, ["enable", "alpha"], engine)

    engine.ledger.set_loop_enabled.assert_called_once_with("alpha", True)
    assert "Enabled loop: alpha" in capsys.readouterr().out


def test_public_disable_calls_ledger_and_prints_success(tmp_path, capsys):
    engine = _make_cli_engine()

    _run_public_dev_loops_command(tmp_path, ["disable", "alpha"], engine)

    engine.ledger.set_loop_enabled.assert_called_once_with("alpha", False)
    assert "Disabled loop: alpha" in capsys.readouterr().out


def test_public_configure_requires_positive_budget_and_sets_budget(tmp_path, capsys):
    engine = _make_cli_engine()

    with pytest.raises(SystemExit) as no_budget:
        _run_public_dev_loops_command(tmp_path, ["configure", "alpha"], engine)
    assert str(no_budget.value) == "configure requires --budget"

    with pytest.raises(SystemExit) as bad_budget:
        _run_public_dev_loops_command(
            tmp_path,
            ["configure", "alpha", "--budget", "0"],
            engine,
        )
    assert str(bad_budget.value) == "budget must be a positive integer"

    _run_public_dev_loops_command(
        tmp_path,
        ["configure", "alpha", "--budget", "7"],
        engine,
    )

    engine.ledger.set_budget.assert_called_once_with("alpha", 7)
    assert "Updated alpha budget to 7" in capsys.readouterr().out


def test_public_promote_validates_category_and_promotes(tmp_path, capsys):
    engine = _make_cli_engine()

    _run_public_dev_loops_command(tmp_path, ["promote", "alpha", "cat-one"], engine)

    engine.ledger.promote_category.assert_called_once_with("alpha", "cat-one")
    assert "Promoted cat-one in alpha" in capsys.readouterr().out


def test_public_reset_calls_reset_loop(tmp_path, capsys):
    engine = _make_cli_engine()

    _run_public_dev_loops_command(tmp_path, ["reset", "alpha"], engine)

    engine.ledger.reset_loop.assert_called_once_with("alpha")
    assert "Reset loop state: alpha" in capsys.readouterr().out


def test_public_command_unknown_loop_exits_with_helpful_message(tmp_path):
    engine = _make_cli_engine()

    with pytest.raises(SystemExit) as exc:
        _run_public_dev_loops_command(tmp_path, ["enable", "missing"], engine)

    assert str(exc.value) == "Unknown loop 'missing'. Valid loops: alpha, beta"


def test_public_promote_unknown_category_exits_with_helpful_message(tmp_path):
    engine = _make_cli_engine()

    with pytest.raises(SystemExit) as exc:
        _run_public_dev_loops_command(tmp_path, ["promote", "alpha", "missing"], engine)

    assert str(exc.value) == (
        "Unknown category 'missing' for loop 'alpha'. "
        "Valid categories: cat-one, cat-two"
    )


def test_public_history_prints_json_lines_and_filters_by_loop(tmp_path, capsys):
    from routine_orchestrator.ledger_view import JournalRecord

    engine = _make_cli_engine()
    engine.journal_reader.read_all.return_value = [
        {
            "loop": "alpha",
            "action": "scan",
            "category": "cat-one",
            "result": "success",
            "timestamp": "2026-04-24T09:59:00+00:00",
            "duration_ms": 10,
        },
        JournalRecord(
            loop="alpha",
            action="scan",
            category="cat-one",
            result="success",
            timestamp="2026-04-24T10:00:00+00:00",
            duration_ms=12,
        ),
        JournalRecord(
            loop="alpha",
            action="fix",
            category="cat-one",
            result="success",
            timestamp="2026-04-24T10:02:00+00:00",
            files=["a.py"],
            duration_ms=56,
        ),
        JournalRecord(
            loop="beta",
            action="fix",
            category="cat-two",
            result="failure",
            timestamp="2026-04-24T10:01:00+00:00",
            error="boom",
            duration_ms=34,
        ),
    ]

    _run_public_dev_loops_command(
        tmp_path,
        ["history", "alpha", "--limit", "2"],
        engine,
    )

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines == [
        {
            "loop": "alpha",
            "action": "scan",
            "category": "cat-one",
            "result": "success",
            "timestamp": "2026-04-24T10:00:00+00:00",
            "files": None,
            "commit": None,
            "error": None,
            "duration_ms": 12,
            "created_at": None,
            "job_id": None,
            "kind": None,
            "name": None,
            "state": None,
        },
        {
            "loop": "alpha",
            "action": "fix",
            "category": "cat-one",
            "result": "success",
            "timestamp": "2026-04-24T10:02:00+00:00",
            "files": ["a.py"],
            "commit": None,
            "error": None,
            "duration_ms": 56,
            "created_at": None,
            "job_id": None,
            "kind": None,
            "name": None,
            "state": None,
        },
    ]


def test_public_diagnose_does_not_register_auto_commands(tmp_path, capsys):
    engine = _make_cli_engine()
    engine.ledger.diagnose.return_value = {
        "summary": {"total_issues": 0, "critical": 0, "warning": 0, "info": 0},
        "issues": [],
    }

    _run_public_dev_loops_command(tmp_path, ["diagnose"], engine)

    engine.register_auto_commands.assert_not_called()
    assert "No diagnostic issues found" in capsys.readouterr().out


def test_public_history_does_not_register_auto_commands(tmp_path, capsys):
    engine = _make_cli_engine()

    _run_public_dev_loops_command(tmp_path, ["history", "alpha"], engine)

    engine.register_auto_commands.assert_not_called()
    assert "No history entries found" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    (
        ["registry"],
        ["status"],
        ["report", "--days", "1"],
        ["heal"],
    ),
)
def test_public_read_only_commands_do_not_prune_trust_state(
    tmp_path,
    capsys,
    argv,
):
    from adaptive.discovery import AutoCommandEntry

    state_dir = tmp_path / "adaptive"
    state_dir.mkdir()
    state_file = state_dir / "trust_state.json"
    state_file.write_text(
        json.dumps(
            {
                "loops": {
                    "dynamic-loop": {
                        "budget": 5,
                        "budget_remaining": 5,
                        "categories": {
                            "auto-dynamic": {
                                "enabled": True,
                                "trust": 0.7,
                                "tier": 0,
                            },
                            "ghost-category": {
                                "enabled": True,
                                "trust": 0.4,
                                "tier": 0,
                            },
                        },
                    },
                },
            },
            indent=2,
        )
    )
    before = state_file.read_bytes()
    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {
            "dynamic-loop": {
                "enabled": True,
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {},
            },
        },
    }
    engine = AdaptiveLoopEngine(config, runtime_dir=tmp_path, project_root=tmp_path)
    registry = {
        "auto-dynamic": AutoCommandEntry(
            name="auto-dynamic",
            module=SimpleNamespace(),
            loop_name="dynamic-loop",
            tier=0,
            trigger="nightly",
        )
    }

    with (
        patch.object(adaptive_loop_executor, "load_config", return_value=config),
        patch.object(adaptive_loop_executor, "get_runtime_dir", return_value=tmp_path),
        patch.object(
            adaptive_loop_executor,
            "_resolve_execution_project_root",
            return_value=tmp_path,
        ),
        patch.object(adaptive_loop_executor, "AdaptiveLoopEngine", return_value=engine),
        patch.object(
            adaptive_loop_executor, "discover_auto_commands", return_value=registry
        ),
        patch.object(
            adaptive_loop_executor,
            "write_cli_metrics",
            return_value=tmp_path / "adaptive" / "reports" / "executor-latest.json",
        ),
        patch.object(sys, "argv", ["adaptive_loop_executor.py", *argv]),
    ):
        adaptive_loop_executor.main()

    assert state_file.read_bytes() == before
    assert (
        "ghost-category"
        in json.loads(state_file.read_text())["loops"]["dynamic-loop"]["categories"]
    )
    capsys.readouterr()


def test_public_diagnose_fix_rejects_before_registering_auto_commands(tmp_path):
    engine = _make_cli_engine()

    with pytest.raises(SystemExit) as exc:
        _run_public_dev_loops_command(tmp_path, ["diagnose", "--fix"], engine)

    engine.register_auto_commands.assert_not_called()
    assert str(exc.value) == "--fix is only supported with --heal"


def test_public_history_empty_prints_helpful_message(tmp_path, capsys):
    engine = _make_cli_engine()

    _run_public_dev_loops_command(tmp_path, ["history"], engine)

    assert "No history entries found" in capsys.readouterr().out


def test_public_diagnose_prints_summary_without_mutating(tmp_path, capsys):
    engine = _make_cli_engine()
    entries = [
        {"loop": "alpha", "action": "scan", "category": "cat-one", "result": "success"}
    ]
    engine.journal_reader.read_all.return_value = entries
    engine.ledger.diagnose.return_value = {
        "summary": {"total_issues": 1, "critical": 0, "warning": 1, "info": 0},
        "issues": [
            {
                "severity": "warning",
                "loop": "alpha",
                "category": "cat-one",
                "issue": "Budget exhausted",
                "fix": "/a-loops configure alpha --budget 3",
            }
        ],
    }

    _run_public_dev_loops_command(tmp_path, ["diagnose"], engine)

    engine.ledger.diagnose.assert_called_once_with(entries)
    engine.ledger.set_loop_enabled.assert_not_called()
    engine.ledger.set_budget.assert_not_called()
    engine.ledger.promote_category.assert_not_called()
    engine.ledger.reset_loop.assert_not_called()
    output = capsys.readouterr().out
    assert "Diagnostics summary: total=1 critical=0 warning=1 info=0" in output
    assert "warning alpha cat-one Budget exhausted" in output


def test_public_diagnose_hydrates_persisted_dynamic_categories_read_only(
    tmp_path,
    capsys,
):
    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {
            "dynamic-loop": {
                "enabled": True,
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {},
            },
        },
    }
    state_file = tmp_path / "adaptive" / "trust_state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps(
            {
                "loops": {
                    "dynamic-loop": {
                        "budget": 5,
                        "budget_remaining": 3,
                        "categories": {
                            "auto-dynamic": {
                                "enabled": True,
                                "disable_count": 99,
                                "trust": 0.7,
                                "tier": 1,
                            },
                        },
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    before = state_file.read_bytes()
    engine = AdaptiveLoopEngine(config, runtime_dir=tmp_path, project_root=tmp_path)
    engine.register_auto_commands = MagicMock(wraps=engine.register_auto_commands)

    with (
        patch.object(adaptive_loop_executor, "load_config", return_value=config),
        patch.object(adaptive_loop_executor, "get_runtime_dir", return_value=tmp_path),
        patch.object(
            adaptive_loop_executor,
            "_resolve_execution_project_root",
            return_value=tmp_path,
        ),
        patch.object(adaptive_loop_executor, "AdaptiveLoopEngine", return_value=engine),
        patch.object(
            adaptive_loop_executor,
            "discover_auto_commands",
            side_effect=AssertionError("diagnose must not discover auto commands"),
        ),
        patch.object(sys, "argv", ["adaptive_loop_executor.py", "diagnose"]),
    ):
        adaptive_loop_executor.main()

    engine.register_auto_commands.assert_not_called()
    assert state_file.read_bytes() == before
    output = capsys.readouterr().out
    assert "Zombie enabled" in output
    assert "dynamic-loop auto-dynamic" in output


def test_public_diagnose_with_fix_exits_with_heal_only_error(tmp_path):
    engine = _make_cli_engine()

    with pytest.raises(SystemExit) as exc:
        _run_public_dev_loops_command(tmp_path, ["diagnose", "--fix"], engine)

    assert str(exc.value) == "--fix is only supported with --heal"


def test_public_loop_executor_does_not_advertise_stubbed_commands():
    # The /dev-loops command doc was removed in the routines consolidation
    # (folded into /a-loops); this now guards only the still-living executor
    # source against advertising stubbed/unimplemented commands.
    executor = (DAEMON_ROOT / "scripts" / "adaptive_loop_executor.py").read_text(
        encoding="utf-8"
    )

    assert "Not yet implemented" not in executor
    assert "Reset trust state and history" not in executor
    assert "Reset trust state only" in executor


def test_trust_diagnostics_budget_exhaustion_fix_hint_includes_loop_name():
    from adaptive.trust_diagnostics import diagnose_loops
    from adaptive.trust_state import LoopState

    report = diagnose_loops(
        {
            "alpha": LoopState(
                budget=3,
                budget_remaining=0,
                categories={},
            )
        }
    )

    issue = next(
        item
        for item in report["issues"]
        if item["issue"].startswith("Budget exhausted")
    )
    assert issue["fix"] == (
        "/a-loops configure alpha --budget N or wait for next cycle"
    )


def test_public_reset_clears_dynamic_category_state_after_registration(
    tmp_path,
    capsys,
):
    from adaptive.discovery import AutoCommandEntry
    from adaptive.trust_state import CategoryState

    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {
            "dynamic-loop": {
                "enabled": True,
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {},
            },
        },
    }
    engine = AdaptiveLoopEngine(config, runtime_dir=tmp_path, project_root=tmp_path)
    state = CategoryState(
        enabled=False,
        trust=0.9,
        success_count=7,
        failure_count=6,
        consecutive_successes=5,
        consecutive_failures=4,
        tier=2,
        disabled_at_cycle=11,
        disable_count=3,
        difficulty=4,
        consecutive_clean_scans=9,
        strategy="self-repair",
        commit_trust=0.55,
        total_commits=3,
        total_fixes=8,
        max_committed_difficulty=2,
        pending_commit_verification=True,
        last_commit_trust_credit=0.2,
        last_actionable_fingerprints=["a"],
        last_scanner_defect_fingerprints=["b"],
        issue_decay_streak=2,
        stagnation_streak=3,
        self_repair_count=4,
        self_repair_successes=5,
        issue_cycles=6,
        false_positive_signal_count=7,
        last_snapshot_fingerprint="snapshot",
        force_deep_runs_remaining=2,
        hot_paths=["apps/dashboard"],
        hot_patterns=["type-error"],
        dominant_root_cause="stale-type",
    )
    engine.ledger._loops["dynamic-loop"].categories["auto-dynamic"] = state
    registry = {
        "auto-dynamic": AutoCommandEntry(
            name="auto-dynamic",
            module=SimpleNamespace(),
            loop_name="dynamic-loop",
            tier=2,
            trigger="nightly",
        )
    }

    with (
        patch.object(adaptive_loop_executor, "load_config", return_value=config),
        patch.object(adaptive_loop_executor, "get_runtime_dir", return_value=tmp_path),
        patch.object(
            adaptive_loop_executor,
            "_resolve_execution_project_root",
            return_value=tmp_path,
        ),
        patch.object(adaptive_loop_executor, "AdaptiveLoopEngine", return_value=engine),
        patch.object(
            adaptive_loop_executor, "discover_auto_commands", return_value=registry
        ),
        patch.object(
            sys, "argv", ["adaptive_loop_executor.py", "reset", "dynamic-loop"]
        ),
    ):
        adaptive_loop_executor.main()

    reset_state = engine.ledger.get_loop_state("dynamic-loop").categories[
        "auto-dynamic"
    ]
    assert reset_state.enabled is True
    assert reset_state.trust == 0.0
    assert reset_state.success_count == 0
    assert reset_state.failure_count == 0
    assert reset_state.consecutive_successes == 0
    assert reset_state.consecutive_failures == 0
    assert reset_state.disable_count == 0
    assert reset_state.disabled_at_cycle == -1
    assert reset_state.difficulty == 0
    assert reset_state.consecutive_clean_scans == 0
    assert reset_state.strategy == "scan"
    assert reset_state.pending_commit_verification is False
    assert reset_state.last_commit_trust_credit == 0.0
    assert reset_state.last_actionable_fingerprints == []
    assert reset_state.last_scanner_defect_fingerprints == []
    assert reset_state.issue_decay_streak == 0
    assert reset_state.stagnation_streak == 0
    assert reset_state.self_repair_count == 0
    assert reset_state.self_repair_successes == 0
    assert reset_state.issue_cycles == 0
    assert reset_state.false_positive_signal_count == 0
    assert reset_state.last_snapshot_fingerprint == ""
    assert reset_state.force_deep_runs_remaining == 0
    assert reset_state.hot_paths == []
    assert reset_state.hot_patterns == []
    assert reset_state.dominant_root_cause == ""
    assert reset_state.commit_trust == 0.55
    assert reset_state.total_commits == 3
    assert reset_state.total_fixes == 8
    assert reset_state.max_committed_difficulty == 2
    assert "Reset loop state: dynamic-loop" in capsys.readouterr().out


def test_daemon_loop_mode_only_runs_continuous_work(monkeypatch, tmp_path):
    class FixedDateTime:
        @staticmethod
        def now(tz=None):
            from datetime import datetime

            return datetime(2026, 4, 12, 0, 1, tzinfo=tz)

    engine = MagicMock()
    engine.run_all_by_trigger.side_effect = lambda trigger: {trigger: []}
    engine.drain_post_exec_queue.side_effect = AssertionError(
        "daemon loop mode should not drain the post-exec queue after cutover"
    )

    with (
        patch.object(
            adaptive_loop_executor,
            "load_config",
            return_value={
                "engine": {"enabled": True, "poll_interval_seconds": 1},
                "loops": {},
            },
        ),
        patch.object(adaptive_loop_executor, "get_runtime_dir", return_value=tmp_path),
        patch.object(
            adaptive_loop_executor,
            "_resolve_execution_project_root",
            return_value=tmp_path,
        ),
        patch.object(adaptive_loop_executor, "discover_auto_commands", return_value={}),
        patch.object(adaptive_loop_executor, "AdaptiveLoopEngine", return_value=engine),
        patch.object(adaptive_loop_executor, "datetime", FixedDateTime),
        patch.object(
            adaptive_loop_executor.time,
            "sleep",
            side_effect=KeyboardInterrupt,
        ),
        patch.object(sys, "argv", ["adaptive_loop_executor.py", "--loop"]),
    ):
        with pytest.raises(KeyboardInterrupt):
            adaptive_loop_executor.main()

    assert engine.run_all_by_trigger.call_args_list == [call("continuous")]


def test_run_command_evolution_drain_uses_post_execution_filter(monkeypatch, tmp_path):
    engine = MagicMock()
    engine.loops = {}
    engine._auto_loop_names = {"command-evolution"}
    engine.run_auto_cycle.return_value = MagicMock(
        results=[], format=lambda: "drain report"
    )
    engine.consume_post_exec_queue.return_value = []

    with (
        patch.object(
            adaptive_loop_executor,
            "load_config",
            return_value={"engine": {"enabled": True}, "loops": {}},
        ),
        patch.object(adaptive_loop_executor, "get_runtime_dir", return_value=tmp_path),
        patch.object(
            adaptive_loop_executor,
            "_resolve_execution_project_root",
            return_value=tmp_path,
        ),
        patch.object(adaptive_loop_executor, "discover_auto_commands", return_value={}),
        patch.object(adaptive_loop_executor, "AdaptiveLoopEngine", return_value=engine),
        patch.object(
            adaptive_loop_executor,
            "write_cli_metrics",
            return_value=tmp_path / "adaptive" / "reports" / "executor-run-latest.json",
        ),
        patch.object(
            sys,
            "argv",
            ["adaptive_loop_executor.py", "run", "command-evolution", "--drain"],
        ),
    ):
        adaptive_loop_executor.main()

    engine.run_auto_cycle.assert_called_once_with(
        "command-evolution",
        trigger_filter="post-execution",
    )


def test_run_knowledge_enrichment_drain_uses_post_execution_filter(tmp_path):
    engine = MagicMock()
    engine.loops = {}
    engine._auto_loop_names = {"knowledge-enrichment"}
    engine.run_auto_cycle.return_value = MagicMock(
        results=[], format=lambda: "drain report"
    )
    engine.consume_post_exec_queue.return_value = []

    with (
        patch.object(
            adaptive_loop_executor,
            "load_config",
            return_value={"engine": {"enabled": True}, "loops": {}},
        ),
        patch.object(adaptive_loop_executor, "get_runtime_dir", return_value=tmp_path),
        patch.object(
            adaptive_loop_executor,
            "_resolve_execution_project_root",
            return_value=tmp_path,
        ),
        patch.object(adaptive_loop_executor, "discover_auto_commands", return_value={}),
        patch.object(adaptive_loop_executor, "AdaptiveLoopEngine", return_value=engine),
        patch.object(
            adaptive_loop_executor,
            "write_cli_metrics",
            return_value=tmp_path / "adaptive" / "reports" / "executor-run-latest.json",
        ),
        patch.object(
            sys,
            "argv",
            ["adaptive_loop_executor.py", "run", "knowledge-enrichment", "--drain"],
        ),
    ):
        adaptive_loop_executor.main()

    engine.run_auto_cycle.assert_called_once_with(
        "knowledge-enrichment",
        trigger_filter="post-execution",
    )


def test_post_execution_drain_bypasses_dormant_and_clean_scan_throttle(tmp_path):
    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {
            "command-evolution": {
                "enabled": True,
                "trigger": "post-execution",
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {
                    "auto-command-evolution": {
                        "enabled": True,
                        "trust": 0.8,
                        "tier": 0,
                    },
                },
            },
        },
    }
    engine = AdaptiveLoopEngine(config, runtime_dir=tmp_path, project_root=tmp_path)
    module = _Module([])
    entry = _make_entry("auto-command-evolution", "command-evolution", module)
    entry.trigger = "post-execution"
    engine.register_auto_commands({"auto-command-evolution": entry})

    loop_state = engine.ledger.get_loop_state("command-evolution")
    cat_state = loop_state.categories["auto-command-evolution"]
    cat_state.difficulty = 4
    cat_state.consecutive_clean_scans = 25
    cat_state.strategy = "dormant"
    loop_state.cycle_count = 1

    report = engine.run_auto_cycle(
        "command-evolution",
        trigger_filter="post-execution",
    )

    assert module.last_ctx is not None
    assert [category.name for category in report.categories] == [
        "auto-command-evolution"
    ]


def test_run_knowledge_enrichment_prints_wiki_compile_handoff(tmp_path, capsys):
    report = CycleReport(
        loop_name="knowledge-enrichment",
        categories=[
            CategoryReport(
                name="auto-wiki-maintenance",
                trust_before=0.0,
                trust_after=0.0,
                difficulty_before=2,
                difficulty_after=2,
                status="degraded",
                outcome="report-only",
                issue_count=2,
                actionable_count=2,
                action_summary="2 wiki maintenance issue(s) across 25 pages",
            )
        ],
        results=[],
    )
    engine = MagicMock()
    engine.loops = {}
    engine._auto_loop_names = {"knowledge-enrichment"}
    engine._auto_commands = {"knowledge-enrichment": []}
    engine.run_auto_cycle.return_value = report

    with (
        patch.object(
            adaptive_loop_executor,
            "load_config",
            return_value={"engine": {"enabled": True}, "loops": {}},
        ),
        patch.object(adaptive_loop_executor, "get_runtime_dir", return_value=tmp_path),
        patch.object(
            adaptive_loop_executor,
            "_resolve_execution_project_root",
            return_value=tmp_path,
        ),
        patch.object(adaptive_loop_executor, "discover_auto_commands", return_value={}),
        patch.object(adaptive_loop_executor, "AdaptiveLoopEngine", return_value=engine),
        patch.object(
            adaptive_loop_executor,
            "write_cli_metrics",
            return_value=tmp_path / "adaptive" / "reports" / "executor-run-latest.json",
        ),
        patch.object(
            sys, "argv", ["adaptive_loop_executor.py", "run", "knowledge-enrichment"]
        ),
    ):
        adaptive_loop_executor.main()

    output = capsys.readouterr().out
    assert "Wiki Compile Handoff" in output
    assert "/auto-wiki-maintenance --compile --cycles 5 --limit 25 --evolve" in output


def test_run_self_heal_validate_uses_nightly_filter(tmp_path):
    engine = MagicMock()
    engine.loops = {}
    engine._auto_loop_names = {"self-heal"}
    engine.run_auto_cycle.return_value = MagicMock(
        results=[], format=lambda: "validate report"
    )

    with (
        patch.object(
            adaptive_loop_executor,
            "load_config",
            return_value={"engine": {"enabled": True}, "loops": {}},
        ),
        patch.object(adaptive_loop_executor, "get_runtime_dir", return_value=tmp_path),
        patch.object(
            adaptive_loop_executor,
            "_resolve_execution_project_root",
            return_value=tmp_path,
        ),
        patch.object(adaptive_loop_executor, "discover_auto_commands", return_value={}),
        patch.object(adaptive_loop_executor, "AdaptiveLoopEngine", return_value=engine),
        patch.object(
            adaptive_loop_executor,
            "write_cli_metrics",
            return_value=tmp_path / "adaptive" / "reports" / "executor-run-latest.json",
        ),
        patch.object(
            sys,
            "argv",
            ["adaptive_loop_executor.py", "run", "self-heal", "--validate"],
        ),
    ):
        adaptive_loop_executor.main()

    engine.run_auto_cycle.assert_called_once_with(
        "self-heal",
        trigger_filter="nightly",
    )
    engine.generate_report.assert_called_once_with()
    engine.journal_reader.cleanup.assert_called_once_with(30)


def test_consume_post_exec_queue_clears_queue_and_returns_events(tmp_path):
    from skills.daemon.scripts.adaptive.engine_queue import QueueMixin

    queue_path = tmp_path / "adaptive" / "post_exec_queue.jsonl"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {"command": "alpha", "timestamp": "2026-04-12T00:00:00+00:00"}
                ),
                json.dumps(
                    {"command": "beta", "timestamp": "2026-04-12T00:05:00+00:00"}
                ),
            ]
        ),
        encoding="utf-8",
    )

    engine = QueueMixin()
    engine._config = {
        "engine": {"post_exec_queue": "state/adaptive/post_exec_queue.jsonl"}
    }
    engine._runtime_dir = tmp_path

    events = engine.consume_post_exec_queue()

    assert [event["command"] for event in events] == ["alpha", "beta"]
    assert queue_path.read_text(encoding="utf-8") == ""


def test_consume_post_exec_queue_skips_malformed_lines(tmp_path):
    from skills.daemon.scripts.adaptive.engine_queue import QueueMixin

    queue_path = tmp_path / "adaptive" / "post_exec_queue.jsonl"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {"command": "alpha", "timestamp": "2026-04-12T00:00:00+00:00"}
                ),
                '{"command": ',
                json.dumps(
                    {"command": "beta", "timestamp": "2026-04-12T00:05:00+00:00"}
                ),
            ]
        ),
        encoding="utf-8",
    )

    engine = QueueMixin()
    engine._config = {
        "engine": {"post_exec_queue": "state/adaptive/post_exec_queue.jsonl"}
    }
    engine._runtime_dir = tmp_path

    events = engine.consume_post_exec_queue()

    assert [event["command"] for event in events] == ["alpha", "beta"]
    assert queue_path.read_text(encoding="utf-8") == ""


def test_materialize_post_exec_events_writes_execution_logs(tmp_path):
    from skills.daemon.scripts.adaptive.engine_queue import QueueMixin

    engine = QueueMixin()
    engine._runtime_dir = tmp_path

    engine.materialize_post_exec_events(
        [
            {
                "command": "alpha",
                "timestamp": "2026-04-12T00:00:00+00:00",
                "outcome": "success",
                "duration_ms": 250,
            }
        ]
    )

    log_path = (
        tmp_path
        / "command-evolution"
        / "alpha"
        / "executions"
        / "2026-04-12T00-00-00.json"
    )
    assert log_path.exists()
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["command"] == "alpha"
    assert payload["metrics"]["duration_seconds"] == 0.25


@patch(
    "adaptive.loop_reporter.format_pending_report",
    return_value="  No pending evolve suggestions.",
)
@patch("adaptive.loop_reporter.apply_reclassify", return_value=[])
@patch("adaptive.loop_reporter.persist_suggestions", return_value=[])
@patch("adaptive.loop_reporter.generate_evolve_analysis", return_value="analysis")
@patch("adaptive.loop_reporter.inspect_run")
def test_run_evolve_phase_persists_single_run_reports(
    mock_inspect,
    mock_analysis,
    mock_persist,
    mock_reclassify,
    mock_pending,
    tmp_path,
):
    config = {
        "engine": {"enabled": True, "verify_command": ""},
        "loops": {
            "hardening": {
                "enabled": True,
                "trigger": "nightly",
                "budget": 5,
                "budget_growth_rate": 1,
                "categories": {},
            },
        },
    }
    engine = AdaptiveLoopEngine(config, runtime_dir=tmp_path, project_root=tmp_path)
    inspection = MagicMock()
    inspection.format.return_value = "inspection"
    mock_inspect.return_value = inspection

    report = MagicMock()
    report.loop_name = "hardening"
    engine._auto_commands = {"hardening": []}

    duration = adaptive_loop_executor._run_evolve_phase(
        engine=engine,
        project_root=tmp_path,
        run_start_iso="2026-03-22T00:00:00+00:00",
        reports=[report],
    )

    assert duration >= 0
    mock_inspect.assert_called_once_with(
        tmp_path, "2026-03-22T00:00:00+00:00", [report]
    )
    mock_analysis.assert_called_once()
    mock_persist.assert_called_once_with(
        [report], tmp_path, auto_commands=engine._auto_commands
    )
    mock_reclassify.assert_not_called()

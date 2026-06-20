"""Tests for ops/command_evolution.py — command execution log scanning.

Validates the auto-command-evolution ops command: scanning execution logs
for failure patterns, performance hints, and learnings, then producing
improvement issues for SKILL.md files.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from src.lib.ops_protocol import OpsContext

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "command_evolution.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location("ai_command_evolution", SCRIPT_PATH)
command_evolution = importlib.util.module_from_spec(_spec)
sys.modules["ai_command_evolution"] = command_evolution
assert _spec.loader is not None
_spec.loader.exec_module(command_evolution)


def _make_ctx(tmp_path: Path, **overrides) -> OpsContext:
    defaults = {"project_root": tmp_path, "difficulty": 0, "dry_run": False}
    defaults.update(overrides)
    return OpsContext(**defaults)


# ---------------------------------------------------------------------------
# Module-level sanity
# ---------------------------------------------------------------------------


class TestModuleInterface:
    def test_name_attribute(self):
        assert command_evolution.name == "auto-command-evolution"

    def test_scan_is_callable(self):
        assert callable(command_evolution.scan)

    def test_fix_is_callable(self):
        assert callable(command_evolution.fix)


# ---------------------------------------------------------------------------
# _scan_log
# ---------------------------------------------------------------------------


class TestScanLog:
    def test_success_outcome_produces_no_issues(self):
        data = {"outcome": "success", "phases": [], "errors": [], "learnings": []}
        issues = command_evolution._scan_log("test-cmd", data)
        assert issues == []

    def test_executed_outcome_is_skipped(self):
        """PostToolUse hook logs with outcome='executed' should be ignored."""
        data = {"outcome": "executed"}
        issues = command_evolution._scan_log("test-cmd", data)
        assert issues == []

    def test_failed_phase_produces_timeout_hint(self):
        data = {
            "outcome": "failure",
            "phases": [{"name": "build", "status": "failed"}],
            "errors": [],
            "learnings": [],
        }
        issues = command_evolution._scan_log("test-cmd", data)
        assert len(issues) >= 1
        assert any(i["category"] == "timeout-hints" for i in issues)

    def test_recoverable_error_produces_pre_check(self):
        data = {
            "outcome": "partial_success",
            "phases": [],
            "errors": [{"recoverable": True, "phase": "lint", "message": "eslint crashed"}],
            "learnings": [],
        }
        issues = command_evolution._scan_log("test-cmd", data)
        pre_checks = [i for i in issues if i["action"] == "add-pre-check"]
        assert len(pre_checks) == 1
        assert pre_checks[0]["category"] == "missing-steps"

    def test_slow_assessment_produces_cache_hint(self):
        data = {
            "outcome": "success",
            "phases": [],
            "errors": [],
            "assessment": {"what_was_slow": "webpack rebuild took 45s"},
            "learnings": [],
        }
        issues = command_evolution._scan_log("test-cmd", data)
        cache_hints = [i for i in issues if i["category"] == "cache-keys"]
        assert len(cache_hints) == 1

    def test_learnings_produce_hints(self):
        data = {
            "outcome": "success",
            "phases": [],
            "errors": [],
            "learnings": ["Always check lockfile before npm install"],
        }
        issues = command_evolution._scan_log("test-cmd", data)
        assert len(issues) == 1
        assert issues[0]["action"] == "capture-learning"


# ---------------------------------------------------------------------------
# _scan_self_repair_plan
# ---------------------------------------------------------------------------


class TestScanSelfRepairPlan:
    def test_valid_plan_returns_issue(self, tmp_path: Path):
        plan_path = tmp_path / "plan.json"
        data = {
            "category": "auto-lint",
            "stagnation_streak": 2,
            "module_path": "plugins/dev/scripts/lint.py",
            "recommended_focus": "fix eslint config",
        }
        result = command_evolution._scan_self_repair_plan(plan_path, data)
        assert result is not None
        assert result["command"] == "auto-lint"
        assert result["source"] == "self-repair-plan"

    def test_empty_category_returns_none(self, tmp_path: Path):
        plan_path = tmp_path / "plan.json"
        data = {"category": "", "stagnation_streak": 0}
        result = command_evolution._scan_self_repair_plan(plan_path, data)
        assert result is None


# ---------------------------------------------------------------------------
# Scan (full)
# ---------------------------------------------------------------------------


class TestScan:
    def test_no_evo_dir_returns_empty(self, tmp_path: Path):
        runtime = tmp_path / "runtime"
        with patch("src.config.paths.get_runtime_dir", return_value=runtime):
            ctx = _make_ctx(tmp_path)
            result = command_evolution.scan(ctx)
            assert result.issues == []

    def test_picks_up_execution_log(self, tmp_path: Path):
        runtime = tmp_path / "runtime"
        evo = runtime / "command-evolution" / "test-cmd" / "executions"
        evo.mkdir(parents=True)
        log = evo / "2026-01-01T00-00-00.json"
        log.write_text(json.dumps({
            "outcome": "failure",
            "phases": [{"name": "build", "status": "failed"}],
            "errors": [],
            "learnings": [],
        }), encoding="utf-8")

        with patch("src.config.paths.get_runtime_dir", return_value=runtime):
            ctx = _make_ctx(tmp_path)
            result = command_evolution.scan(ctx)
            assert len(result.issues) >= 1

    def test_picks_up_self_repair_plans(self, tmp_path: Path):
        runtime = tmp_path / "runtime"
        repair_dir = runtime / "adaptive" / "self_repair"
        repair_dir.mkdir(parents=True)
        plan = repair_dir / "auto-lint.json"
        plan.write_text(json.dumps({
            "category": "auto-lint",
            "stagnation_streak": 5,
            "recommended_focus": "fix scanner",
        }), encoding="utf-8")

        with patch("src.config.paths.get_runtime_dir", return_value=runtime):
            ctx = _make_ctx(tmp_path)
            result = command_evolution.scan(ctx)
            assert any(i.get("source") == "self-repair-plan" for i in result.issues)


# ---------------------------------------------------------------------------
# Fix
# ---------------------------------------------------------------------------


class TestFix:
    def test_empty_issues(self, tmp_path: Path):
        ctx = _make_ctx(tmp_path)
        result = command_evolution.fix(ctx, [])
        assert result.success is True

    def test_dry_run(self, tmp_path: Path):
        ctx = _make_ctx(tmp_path, dry_run=True)
        issues = [{"command": "test-cmd", "action": "add-timeout-hint", "improvement": {}}]
        result = command_evolution.fix(ctx, issues)
        assert result.success is True
        assert "Dry run" in result.summary

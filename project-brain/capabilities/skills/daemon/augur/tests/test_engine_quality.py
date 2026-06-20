"""Focused tests for adaptive engine quality classification."""

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


engine_quality = importlib.import_module(
    "skills.daemon.scripts.adaptive.engine_quality"
)


def test_classify_finding_band_marks_scheduler_changes_structural():
    issue = {
        "path": "project-brain/capabilities/skills/daemon/scripts/adaptive_loop_executor.py",
        "detail": "Move scheduled ownership from daemon to codex",
        "loop": "observability",
        "scheduler_change": True,
    }

    assert engine_quality.classify_finding_band(issue) == engine_quality.STRUCTURAL


def test_classify_finding_band_keeps_tool_name_mismatch_mechanical():
    issue = {
        "path": "apps/dashboard/components/foo.tsx",
        "detail": "Tool name typo",
        "tool_name_mismatch": True,
    }

    assert engine_quality.classify_finding_band(issue) == engine_quality.MECHANICAL


def test_classify_finding_band_marks_scan_errors_mechanical():
    issue = {
        "kind": "scan-error",
        "band": "mechanical",
        "finding_band": "mechanical",
        "error_message": "fixture scan failed",
    }

    assert engine_quality.classify_finding_band(issue) == engine_quality.MECHANICAL


def test_classify_fix_outcome_marks_structural_fix_without_design_blocked():
    outcome = engine_quality.classify_fix_outcome(
        success=False,
        changes=[],
        fix_result={"actions": []},
        finding_band=engine_quality.STRUCTURAL,
        design_gate_written=False,
        reverted=False,
        context_insufficient=False,
    )

    assert outcome == "blocked-needs-design"


def test_classify_fix_outcome_marks_context_insufficient_before_other_outcomes():
    outcome = engine_quality.classify_fix_outcome(
        success=True,
        changes=["docs/decisions/ADR-999.md"],
        fix_result={"actions": [{"kind": "note"}]},
        finding_band=engine_quality.STRUCTURAL,
        design_gate_written=True,
        reverted=False,
        context_insufficient=True,
    )

    assert outcome == "context-insufficient"


def test_classify_fix_outcome_marks_structural_success_with_gate_as_design_gated_fixed():
    outcome = engine_quality.classify_fix_outcome(
        success=True,
        changes=["project-brain/capabilities/skills/daemon/scripts/adaptive/engine_quality.py"],
        fix_result={"actions": [{"kind": "edit"}]},
        finding_band=engine_quality.STRUCTURAL,
        design_gate_written=True,
        reverted=False,
        context_insufficient=False,
    )

    assert outcome == "design-gated-fixed"


def test_classify_fix_outcome_marks_structural_gate_without_code_changes_as_design_written():
    outcome = engine_quality.classify_fix_outcome(
        success=True,
        changes=[],
        fix_result={"actions": [{"kind": "note"}]},
        finding_band=engine_quality.STRUCTURAL,
        design_gate_written=True,
        reverted=False,
        context_insufficient=False,
    )

    assert outcome == "design-written"

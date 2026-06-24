"""Tests for the canonical standard-loop model and parser."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_MODULE_PATH = _REPO_ROOT / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "routine_orchestrator" / "loop_model.py"


def _load_loop_model():
    assert _MODULE_PATH.is_file(), "loop_model.py must exist"
    spec = importlib.util.spec_from_file_location("loop_model_under_test", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _full_declaration() -> dict:
    return {
        "id": "knowledge-enrichment",
        "skill": "routine-vault",
        "loop_name": "knowledge-enrichment",
        "automation": {"trigger": "weekly", "runner": "auto", "discover": "scripts/scan.py"},
        "isolation": {"mode": "worktree", "branch": "goal/knowledge"},
        "subagents": {"scan": "scripts/scan.py", "fix": "subagent", "verify": "policy:design-gate"},
        "memory": {"ledger": "ledger", "escalation": "queue", "trust": "adaptive"},
        "connectors": ["mcp:augur-core"],
    }


def test_parse_full_declaration_populates_all_parts():
    m = _load_loop_model()
    loop = m.parse_standard_loop(_full_declaration(), skill_name="routine-vault")
    assert loop.id == "knowledge-enrichment"
    assert loop.skill == "routine-vault"
    assert loop.loop_name == "knowledge-enrichment"
    assert loop.automation.trigger == "weekly"
    assert loop.automation.runner == "auto"
    assert loop.automation.discover == "scripts/scan.py"
    assert loop.isolation.mode == "worktree"
    assert loop.subagents.fix == "subagent"
    assert loop.memory.trust == "adaptive"
    assert loop.connectors == ("mcp:augur-core",)


def test_defaults_applied_when_optional_parts_absent():
    m = _load_loop_model()
    loop = m.parse_standard_loop(
        {"id": "lint", "skill": "routine-vault", "automation": {"trigger": "nightly", "runner": "daemon"}},
        skill_name="routine-vault",
    )
    assert loop.isolation.mode == "in-place"
    assert loop.subagents.fix == "subagent"
    assert loop.memory.trust == "adaptive"
    assert loop.connectors == ()


def test_invalid_runner_raises():
    m = _load_loop_model()
    with pytest.raises(m.LoopValidationError, match="runner"):
        m.parse_standard_loop(
            {"id": "x", "skill": "s", "automation": {"trigger": "nightly", "runner": "cron-daemon"}},
            skill_name="s",
        )


def test_missing_automation_raises():
    m = _load_loop_model()
    with pytest.raises(m.LoopValidationError, match="automation"):
        m.parse_standard_loop({"id": "x", "skill": "s"}, skill_name="s")

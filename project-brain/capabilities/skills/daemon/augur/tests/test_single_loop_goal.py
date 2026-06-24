"""A loop id resolves to a single-loop GoalSpec; catalog ids unchanged."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_DIR = _REPO / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "routine_orchestrator"


def _load_goal_catalog():
    if str(_DIR) not in sys.path:
        sys.path.insert(0, str(_DIR))
    spec = importlib.util.spec_from_file_location("goal_catalog_uut", _DIR / "goal_catalog.py")
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m); return m


def test_catalog_id_returns_curated_bundle():
    gc = _load_goal_catalog()
    spec = gc.resolve_goal_or_loop("harden")
    assert spec.id == "harden"
    assert len(spec.loops) > 1   # curated multi-loop bundle


def test_loop_id_returns_single_loop_spec(monkeypatch):
    gc = _load_goal_catalog()
    # stub the registry lookup so the test does not depend on the live registry
    monkeypatch.setattr(gc, "_known_loop_ids", lambda: {"hardening", "code-quality"})
    spec = gc.resolve_goal_or_loop("hardening")
    assert spec.id == "hardening"
    assert spec.loops == ("hardening",)
    assert "hardening" in spec.title


def test_unknown_id_still_raises(monkeypatch):
    gc = _load_goal_catalog()
    monkeypatch.setattr(gc, "_known_loop_ids", lambda: {"hardening"})
    try:
        gc.resolve_goal_or_loop("totally-bogus")
        assert False, "should raise UnknownGoalError"
    except gc.UnknownGoalError:
        pass

"""Tests for adaptive loop base class."""
from __future__ import annotations

import sys
from pathlib import Path

# ── Setup import path ──────────────────────────────────────────────────────
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from skills.daemon.scripts.adaptive.loops.base_loop import BaseLoop, LoopResult


class ConcreteLoop(BaseLoop):
    """Test implementation of BaseLoop."""

    NAME = "test-loop"
    TRIGGER = "nightly"

    def scan(self, difficulties=None) -> list[dict]:
        return [{"action": "test-action", "category": "cat1", "files": ["a.py"]}]

    def execute_action(self, action: dict) -> LoopResult:
        return LoopResult(
            success=True,
            action=action["action"],
            category=action["category"],
            files=action.get("files", []),
            commit="abc123",
        )


class FailingLoop(BaseLoop):
    NAME = "fail-loop"
    TRIGGER = "nightly"

    def scan(self, difficulties=None) -> list[dict]:
        return [{"action": "bad-action", "category": "cat1"}]

    def execute_action(self, action: dict) -> LoopResult:
        return LoopResult(
            success=False,
            action=action["action"],
            category=action["category"],
            error="Something broke",
        )


class TestBaseLoop:
    def test_concrete_loop_has_name(self):
        loop = ConcreteLoop.__new__(ConcreteLoop)
        assert loop.NAME == "test-loop"

    def test_scan_returns_actions(self):
        loop = ConcreteLoop.__new__(ConcreteLoop)
        actions = loop.scan()
        assert len(actions) == 1
        assert actions[0]["action"] == "test-action"

    def test_execute_returns_result(self):
        loop = ConcreteLoop.__new__(ConcreteLoop)
        result = loop.execute_action({"action": "x", "category": "c"})
        assert result.success is True
        assert result.commit == "abc123"

    def test_loop_result_failure(self):
        loop = FailingLoop.__new__(FailingLoop)
        result = loop.execute_action({"action": "x", "category": "c"})
        assert result.success is False
        assert result.error == "Something broke"

    def test_loop_result_dataclass(self):
        r = LoopResult(success=True, action="a", category="c")
        assert r.files == []
        assert r.commit is None
        assert r.error is None

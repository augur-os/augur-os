"""Tests for code quality adaptive loop — deprecated stub (ADR-200).

Verifies the deprecated CodeQualityLoop returns empty scans and error results,
directing callers to the auto-command modules in devops/scripts/ops/.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from skills.daemon.scripts.adaptive.loops.code_quality import CodeQualityLoop
from skills.daemon.scripts.adaptive.loops.base_loop import LoopResult


@pytest.fixture
def loop(tmp_path):
    return CodeQualityLoop(project_root=tmp_path)


class TestDeprecatedCodeQuality:
    def test_name_and_trigger(self, loop):
        assert loop.NAME == "code-quality"
        assert loop.TRIGGER == "mixed"

    def test_scan_returns_empty(self, loop):
        assert loop.scan() == []

    def test_scan_with_difficulties_returns_empty(self, loop):
        assert loop.scan(difficulties={"format": 2}) == []

    def test_execute_returns_failure(self, loop):
        result = loop.execute_action({
            "action": "lint-autofix",
            "category": "lint-autofix",
        })
        assert result.success is False
        assert "ADR-200" in result.error
        assert result.action == "lint-autofix"
        assert result.category == "lint-autofix"

    def test_execute_unknown_action(self, loop):
        result = loop.execute_action({})
        assert result.success is False
        assert result.action == "unknown"
        assert result.category == "unknown"

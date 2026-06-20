"""Tests for command evolution adaptive loop — deprecated stub (ADR-200).

Verifies the deprecated CommandEvolutionLoop returns empty scans and error
results. The real scan/fix logic is now in skills/ai/scripts/ops/command_evolution.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from skills.daemon.scripts.adaptive.loops.command_evolution import CommandEvolutionLoop, CATEGORY_TYPES
from skills.daemon.scripts.adaptive.loops.base_loop import LoopResult


class TestDeprecatedCommandEvolution:
    def test_name_and_trigger(self):
        loop = CommandEvolutionLoop(project_root=Path("/tmp"), runtime_dir=Path("/tmp"))
        assert loop.NAME == "command-evolution"
        assert loop.TRIGGER == "post-execution"

    def test_scan_returns_empty(self, tmp_path):
        loop = CommandEvolutionLoop(project_root=tmp_path, runtime_dir=tmp_path)
        assert loop.scan() == []

    def test_scan_with_difficulties_returns_empty(self, tmp_path):
        loop = CommandEvolutionLoop(project_root=tmp_path, runtime_dir=tmp_path)
        assert loop.scan(difficulties={"timeout-hints": 1}) == []

    def test_execute_returns_failure(self, tmp_path):
        loop = CommandEvolutionLoop(project_root=tmp_path, runtime_dir=tmp_path)
        result = loop.execute_action({
            "action": "add-timeout-hint",
            "category": "timeout-hints",
            "command": "implement-adr",
        })
        assert result.success is False
        assert "ADR-200" in result.error
        assert result.action == "add-timeout-hint"
        assert result.category == "timeout-hints"

    def test_category_types_exported(self):
        assert "timeout-hints" in CATEGORY_TYPES
        assert "add_timeout" in CATEGORY_TYPES["timeout-hints"]

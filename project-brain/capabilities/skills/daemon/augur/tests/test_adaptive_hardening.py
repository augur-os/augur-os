"""Tests for hardening adaptive loop — deprecated stub (ADR-200).

Verifies the deprecated HardeningLoop returns empty scans and error results.
The real scan/fix logic is now in scripts/ops/ modules.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from skills.daemon.scripts.adaptive.loops.hardening import HardeningLoop
from skills.daemon.scripts.adaptive.loops.base_loop import LoopResult


class TestDeprecatedHardening:
    def test_name_and_trigger(self):
        loop = HardeningLoop(project_root=Path("/tmp"))
        assert loop.NAME == "hardening"
        assert loop.TRIGGER == "nightly"

    def test_scan_returns_empty(self, tmp_path):
        loop = HardeningLoop(project_root=tmp_path)
        assert loop.scan() == []

    def test_scan_with_difficulties_returns_empty(self, tmp_path):
        loop = HardeningLoop(project_root=tmp_path)
        assert loop.scan(difficulties={"build-health": 1}) == []

    def test_execute_returns_failure_with_category(self, tmp_path):
        loop = HardeningLoop(project_root=tmp_path)
        result = loop.execute_action({
            "action": "yaml-lint-error",
            "category": "augur-yaml-lint",
        })
        assert result.success is False
        assert "ADR-200" in result.error
        assert "augur-yaml-lint" in result.error
        assert result.action == "yaml-lint-error"
        assert result.category == "augur-yaml-lint"

    def test_execute_unknown_action(self, tmp_path):
        loop = HardeningLoop(project_root=tmp_path)
        result = loop.execute_action({})
        assert result.success is False
        assert result.action == "unknown"

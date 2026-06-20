"""Tests for self-heal loop wrapper — deprecated stub (ADR-200).

Verifies the deprecated SelfHealLoop returns empty scans and error results.
The real scan/fix logic is now in scripts/ops/self_heal.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from skills.daemon.scripts.adaptive.loops.self_heal import SelfHealLoop, SEVERITY_CATEGORY_MAP
from skills.daemon.scripts.adaptive.loops.base_loop import LoopResult


class TestDeprecatedSelfHeal:
    def test_name_and_trigger(self):
        loop = SelfHealLoop(project_root=Path("/tmp"))
        assert loop.NAME == "self-heal"
        assert loop.TRIGGER == "continuous"

    def test_scan_returns_empty(self):
        loop = SelfHealLoop(project_root=Path("/tmp"))
        assert loop.scan() == []

    def test_scan_with_difficulties_returns_empty(self):
        loop = SelfHealLoop(project_root=Path("/tmp"))
        assert loop.scan(difficulties={"import-fixes": 1}) == []

    def test_execute_returns_failure(self):
        loop = SelfHealLoop(project_root=Path("/tmp"))
        result = loop.execute_action({
            "action": "fix-import",
            "category": "import-fixes",
        })
        assert result.success is False
        assert "ADR-200" in result.error
        assert result.action == "fix-import"
        assert result.category == "import-fixes"

    def test_severity_to_category_still_works(self):
        loop = SelfHealLoop(project_root=Path("/tmp"))
        assert loop._severity_to_category("critical") == "import-fixes"
        assert loop._severity_to_category("high") == "config-fixes"
        assert loop._severity_to_category("medium") == "logic-fixes"
        assert loop._severity_to_category("low") == "logic-fixes"
        assert loop._severity_to_category("unknown") == "logic-fixes"

    def test_severity_category_map_exported(self):
        assert SEVERITY_CATEGORY_MAP["critical"] == "import-fixes"
        assert SEVERITY_CATEGORY_MAP["high"] == "config-fixes"

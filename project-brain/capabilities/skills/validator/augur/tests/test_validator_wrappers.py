"""Smoke and wiring tests for the validator UI wrappers (ui_qa.py, capture_ui.py)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
PROJECT_ROOT = Path(__file__).resolve().parents[6]


def _help_smoke(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(PROJECT_ROOT),
    )


class TestHelpSmoke:
    def test_ui_qa_help_exits_zero(self):
        proc = _help_smoke("ui_qa.py")
        assert proc.returncode == 0, proc.stderr
        assert "--url" in proc.stdout

    def test_capture_ui_help_exits_zero(self):
        proc = _help_smoke("capture_ui.py")
        assert proc.returncode == 0, proc.stderr
        assert "--url" in proc.stdout


class TestWiring:
    def test_shared_dashboard_engines_exist(self):
        """The wrappers shell out to the shared dashboard engines — they must exist."""
        engines = PROJECT_ROOT / "apps" / "dashboard" / "scripts" / "skill-scripts"
        assert (engines / "ui_qa.py").is_file()
        assert (engines / "capture_ui.py").is_file()

    def test_default_ui_qa_config_parses(self):
        config_path = SKILL_ROOT / "augur" / "config" / "ui-qa-validator.yaml"
        assert config_path.is_file()
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert isinstance(config, dict)
        assert "selectors" in config and "thresholds" in config

    def test_bootstrap_finds_project_root(self):
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        from bootstrap_paths import find_project_root

        root = find_project_root(SCRIPTS_DIR / "ui_qa.py")
        assert (root / "pyproject.toml").is_file()
        assert root == PROJECT_ROOT

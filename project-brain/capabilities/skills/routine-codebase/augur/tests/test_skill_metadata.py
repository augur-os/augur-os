"""Metadata regression tests for routine-codebase SKILL.md."""
from __future__ import annotations

from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter


def test_scan_fix_commands_preserve_expected_loop_categories():
    skill_md = Path(__file__).resolve().parents[2] / "SKILL.md"
    frontmatter, _ = parse_frontmatter(skill_md)
    commands = frontmatter["x-augur-commands"]

    scan_fix_commands = [cmd for cmd in commands if cmd.get("protocol") == "scan-fix"]
    expected_loops = {
        "auto-e2e-actions": "testing",
        "auto-e2e-pipeline": "testing",
        "auto-format": "code-quality",
        "auto-lint": "code-quality",
        "auto-test-api": "testing",
        "auto-test-build": "testing",
        "auto-test-dashboard": "testing",
        "auto-test-links": "testing",
        "auto-test-mcp": "testing",
        "auto-test-mcp-commands": "testing",
        "auto-test-onboarding-probes": "testing",
        "auto-test-pages": "testing",
        "auto-test-pytest": "testing",
        "auto-test-webmcp": "testing",
        "auto-ui-quality": "ui-quality",
        "auto-yaml-lint": "hardening",
    }

    assert {cmd["id"] for cmd in scan_fix_commands} == set(expected_loops)
    for command in scan_fix_commands:
        assert command.get("loop", {}).get("name") == expected_loops[command["id"]]

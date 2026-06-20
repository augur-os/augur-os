"""Tests for agent capability dashboard route metadata."""
from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "mcp" / "__init__.py"
SPEC = importlib.util.spec_from_file_location("ai_mcp_module", MODULE_PATH)
assert SPEC and SPEC.loader
ai_mcp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ai_mcp)


def test_build_skill_dashboard_path_uses_hub_frontmatter():
    path = ai_mcp._build_skill_dashboard_path(
        "ai",
        {"x-augur-hub": "workspace"},
        True,
    )

    assert path == "/workspace/ai"


def test_build_skill_dashboard_path_returns_none_without_dashboard():
    path = ai_mcp._build_skill_dashboard_path(
        "ai",
        {"x-augur-hub": "workspace"},
        False,
    )

    assert path is None


def test_build_skill_dashboard_path_returns_none_without_hub():
    path = ai_mcp._build_skill_dashboard_path("ai", {}, True)

    assert path is None

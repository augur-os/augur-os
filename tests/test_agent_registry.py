"""Regression tests for the agent registry tool."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_agent_registry_importable():
    """Verify that agent_registry can be imported without errors."""
    import src.mcp.augur_framework.tools.hubs.agent_registry

    assert src.mcp.augur_framework.tools.hubs.agent_registry is not None


def test_read_registry_uses_canonical_plugins_registry(monkeypatch, tmp_path):
    """The MCP tool should read the canonical plugins/agents registry."""
    from src.mcp.augur_framework.tools.hubs import agent_registry

    plugins_agents = tmp_path / "plugins" / "agents"
    claude_agents = tmp_path / ".claude" / "agents"
    plugins_agents.mkdir(parents=True)
    claude_agents.mkdir(parents=True)

    (plugins_agents / "registry.json").write_text(
        json.dumps({"schema": "2.0", "agents": {"canonical": {"role": "advisor"}}}),
        encoding="utf-8",
    )
    (claude_agents / "registry.json").write_text(
        json.dumps({"schema": "2.0", "agents": {"generated": {"role": "executor"}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr("src.config.paths.get_project_root", lambda: tmp_path)

    result = agent_registry._read_registry()

    assert "canonical" in result["agents"]
    assert "generated" not in result["agents"]

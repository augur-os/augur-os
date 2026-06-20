from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sync_agents.adapters.codex import CodexAdapter  # noqa: E402


def _project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs" / "agent-topics" / "agent-rules.md").exists():
            return parent
    raise AssertionError("Could not find project root")


def test_agent_topic_sources_avoid_legacy_and_single_client_bootstrap_instructions() -> None:
    forbidden = {
        "[mcp_servers.augur]": "legacy monolith Codex MCP key",
        '"augur":': "legacy monolith JSON MCP key",
        "augur_mcp": "legacy monolith MCP module name",
        "mcp_augur_": "client-specific generated MCP tool prefix",
        "src/dashboard": "legacy dashboard path",
        "npm run dev": "manual dashboard server startup",
        "Chrome MCP": "Claude-specific browser integration name",
        "mcp__Claude_in_Chrome": "Claude-specific MCP tool name",
        "Claude must OBSERVE": "single-client debugging wording",
        "Co-Authored-By: Claude": "single-client commit template",
        "without restarting Claude Code": "single-client hot-reload wording",
        "## Codex Integration": "single-client section in shared agent rules",
    }
    hits: list[str] = []
    for path in sorted((_project_root() / "docs" / "agent-topics").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for needle, reason in forbidden.items():
            if needle in text:
                hits.append(f"{path.relative_to(_project_root())}: {needle!r} ({reason})")

    assert hits == []


def test_codex_global_bootstrap_points_to_plugin_cache_after_migration(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    codex_home = tmp_path / "home" / ".codex"
    project_root.mkdir()

    with patch("sync_agents.adapters.codex.PROJECT_ROOT", project_root), patch(
        "sync_agents.adapters.codex.CODEX_HOME",
        codex_home,
    ):
        CodexAdapter().sync_rules("# Rules\n")

    text = (codex_home / "instructions.md").read_text(encoding="utf-8")
    assert "[mcp_servers.augur]" not in text
    assert "augur_mcp" not in text
    assert "skills-latest/.mcp.json" in text
    assert "[marketplaces.augur-local]" in text
    assert '[plugins."augur@augur-local"]' in text

from __future__ import annotations

import yaml

from src.config.paths import get_skill_root
from src.mcp.augur_shared.client_surface import PLUGIN_TOOL_SOURCES


def test_list_commands_tool_is_owned_by_ai() -> None:
    assert PLUGIN_TOOL_SOURCES["list-commands"] == "ai"


def test_ai_skill_declares_list_commands_tool() -> None:
    skill_md = get_skill_root("ai") / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    _, frontmatter, _ = content.split("---", 2)
    data = yaml.safe_load(frontmatter)
    assert "list-commands" in data["x-augur-mcp-tools"]


def test_ai_owns_sync_agents_command() -> None:
    assert (get_skill_root("ai") / "commands/sync-agents.md").exists()


def test_ai_owns_ops_learn_command() -> None:
    assert (get_skill_root("ai") / "commands/ops-learn.md").exists()


def test_ai_owns_auto_doc_freshness_command() -> None:
    assert (get_skill_root("ai") / "commands/auto-doc-freshness.md").exists()


def test_daemon_owns_auto_skill_md_command() -> None:
    assert (get_skill_root("daemon") / "commands/auto-skill-md.md").exists()


def test_daemon_owns_auto_skill_refs_command() -> None:
    assert (get_skill_root("daemon") / "commands/auto-skill-refs.md").exists()

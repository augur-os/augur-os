"""Tests for slash-command discovery."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter
from src.plugins.command_discovery import clear_cache, discover_commands


def test_command_discovery_importable():
    """Verify that command_discovery can be imported without errors."""
    import src.plugins.command_discovery
    assert src.plugins.command_discovery is not None


def test_discover_commands_reads_declared_dev_build(tmp_path: Path) -> None:
    """Slash commands come from x-augur-commands declarations, not skill IDs."""
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "platform-admin"
    command_dir = skill_dir / "commands"
    command_dir.mkdir(parents=True)
    write_frontmatter(
        skill_dir / "SKILL.md",
        {
            "name": "platform-admin",
            "description": "Platform administration",
            "x-augur-hub": "dev",
            "x-augur-group": "augur_admin",
            "x-augur-commands": [
                {
                    "id": "dev-build",
                    "type": "workflow",
                    "visibility": "dev",
                    "description": "Clean caches, rebuild UI, and validate pages",
                }
            ],
        },
        "# Platform Admin\n",
    )
    write_frontmatter(
        command_dir / "dev-build.md",
        {
            "description": "Clean caches, rebuild the dashboard UI, and validate pages.",
            "visibility": "dev",
        },
        "# /dev-build\n",
    )

    clear_cache()
    commands = discover_commands(plugins_dir=skills_dir)

    assert [command.id for command in commands] == ["dev-build"]
    assert commands[0].visibility == "dev"
    assert commands[0].description == "Clean caches, rebuild UI, and validate pages"
    assert commands[0].group == "augur_admin"
    assert commands[0].path == command_dir / "dev-build.md"


def test_discover_commands_visibility_filter_uses_command_visibility(tmp_path: Path) -> None:
    """Visibility filters apply to declared command visibility values."""
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "platform-admin"
    command_dir = skill_dir / "commands"
    command_dir.mkdir(parents=True)
    write_frontmatter(
        skill_dir / "SKILL.md",
        {
            "name": "platform-admin",
            "description": "Platform administration",
            "x-augur-commands": [
                {"id": "dev-build", "visibility": "dev", "description": "Build"},
                {"id": "remote-access", "visibility": "ops", "description": "Remote access"},
            ],
        },
        "# Platform Admin\n",
    )
    (command_dir / "dev-build.md").write_text("---\nvisibility: dev\n---\n# /dev-build\n", encoding="utf-8")
    (command_dir / "remote-access.md").write_text(
        "---\nvisibility: ops\n---\n# /remote-access\n",
        encoding="utf-8",
    )

    clear_cache()
    commands = discover_commands(plugins_dir=skills_dir, visibility_filter={"dev"})

    assert [command.id for command in commands] == ["dev-build"]


def test_mcp_commands_payload_exposes_project_router_not_subcommands() -> None:
    """The list-commands MCP payload exposes /project, not project-coupled commands."""
    from skills.ai.scripts.mcp import _render_commands_payload

    clear_cache()
    payload = _render_commands_payload()

    command_ids = {
        command["id"]
        for section in payload["slash_commands"]
        for command in section["commands"]
    }
    assert "project" in command_ids
    assert "adr" not in command_ids
    assert "dev" not in command_ids
    assert "sweep" not in command_ids
    assert "dev-build" not in command_ids
    assert "dev-debug" not in command_ids
    assert "dev-merge" not in command_ids


def test_mcp_commands_payload_exposes_no_hidden_command_sections() -> None:
    """The command payload is a primary-command catalog, not an internal shortcut dump."""
    from skills.ai.scripts.mcp import _render_commands_payload

    clear_cache()
    payload = _render_commands_payload()

    command_ids = {
        command["id"]
        for section in payload["slash_commands"]
        for command in section["commands"]
    }
    assert command_ids == {"ask", "discover", "keep", "project", "routines", "skillify"}
    assert payload["total_commands"] == len(command_ids)
    assert payload["total_slash_commands"] == len(command_ids)
    assert "auto_commands" not in payload


def test_mcp_commands_payload_does_not_label_non_command_skills_as_total(monkeypatch) -> None:
    """The payload should expose both total visible skills and non-command skills."""
    from skills.ai.scripts.mcp import _render_commands_payload
    from src.plugins import command_discovery, skill_discovery

    monkeypatch.setattr(
        command_discovery,
        "discover_commands",
        lambda: [
            SimpleNamespace(
                id="ask",
                description="Ask",
                visibility="core",
                alias=None,
                group=None,
                bundle=None,
                loop=None,
            )
        ],
    )
    monkeypatch.setattr(
        skill_discovery,
        "list_skills",
        lambda: [
            SimpleNamespace(id="ask", description="Ask", visibility=None, layer="project"),
            SimpleNamespace(id="knowledge", description="Knowledge", visibility=None, layer="project"),
        ],
    )

    payload = _render_commands_payload()

    assert payload["total_visible_skills"] == 2
    assert payload["total_skills"] == 2
    assert payload["non_command_skills"] == 1
    assert [skill["id"] for skill in payload["skills"]] == ["knowledge"]


def test_project_router_exports_but_project_subcommands_do_not() -> None:
    """Project-only command bodies are dispatched through /project, not exported directly."""
    root = PROJECT_ROOT / "project-brain" / "capabilities" / "skills"

    project_fm, _ = parse_frontmatter(root / "augur-core" / "commands" / "project.md")
    assert project_fm["x-augur-export-command"] is True

    for rel in (
        ("augur-core", "commands", "adr.md"),
        ("platform-admin", "commands", "dev.md"),
        ("routine-vault", "commands", "sweep.md"),
    ):
        frontmatter, _ = parse_frontmatter(root.joinpath(*rel))
        assert frontmatter.get("x-augur-export-command") is False
        assert frontmatter.get("x-augur-parent-command") == "project"

"""Tests for sync_agents agent parsing and master selection."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

# Ensure sync_agents package is importable
scripts_dir = Path(__file__).resolve().parents[2]
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from sync_agents.agent_parser import (  # noqa: E402
    AgentFile,
    collect_masters,
    scan_agent_dirs,
    scan_plugin_agents,
)


def test_scan_agent_dirs_ignores_readme_markdown(tmp_path: Path):
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "README.md").write_text("# Agents\n", encoding="utf-8")
    (agents_dir / "reviewer.md").write_text(
        "---\nname: reviewer\ndescription: test\n---\n# Reviewer\n",
        encoding="utf-8",
    )

    agents = scan_agent_dirs(tmp_path, clients=["claude-code"])

    assert [agent.name for agent in agents] == ["reviewer"]


def test_collect_masters_prefers_higher_source_priority(tmp_path: Path):
    older = tmp_path / "older.md"
    older.write_text("---\nname: code-reviewer\n---\nbody\n", encoding="utf-8")
    newer = tmp_path / "newer.md"
    newer.write_text("---\nname: code-reviewer\n---\nbody\n", encoding="utf-8")

    preferred = AgentFile(
        name="code-reviewer",
        path=older,
        frontmatter={"name": "code-reviewer"},
        body="body",
        client_dir="plugin:superpowers",
        source_priority=200.0,
    )
    lower_priority = AgentFile(
        name="code-reviewer",
        path=newer,
        frontmatter={"name": "code-reviewer"},
        body="body",
        client_dir="plugin:feature-dev",
        source_priority=100.0,
    )

    masters = collect_masters([lower_priority, preferred])

    assert masters["code-reviewer"].client_dir == "plugin:superpowers"


def test_scan_plugin_agents_ignores_readme_and_uses_install_priority(tmp_path: Path):
    home = tmp_path / "home"
    install_path = home / ".claude" / "plugins" / "cache" / "example" / "1.0.0"
    agents_dir = install_path / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "README.md").write_text("# Plugin Agents\n", encoding="utf-8")
    (agents_dir / "helper.md").write_text(
        "---\nname: helper\ndescription: plugin helper\n---\n# Helper\n",
        encoding="utf-8",
    )

    manifest_path = home / ".claude" / "plugins" / "installed_plugins.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "plugins": {
                    "example@claude-plugins-official": [
                        {
                            "installPath": str(install_path),
                            "lastUpdated": "2026-04-08T12:00:00Z",
                            "installedAt": "2026-04-08T11:00:00Z",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    with patch("sync_agents.agent_parser.Path.home", return_value=home):
        agents = scan_plugin_agents()

    assert [agent.name for agent in agents] == ["helper"]
    assert agents[0].client_dir == "plugin:example"
    assert agents[0].source_priority > 0

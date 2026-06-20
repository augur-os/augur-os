"""Auto-generated importability test for mcp_diagnostics."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_mcp_diagnostics_importable():
    """Verify that mcp_diagnostics can be imported without errors."""
    import src.mcp.augur_framework.tools.infrastructure.mcp_diagnostics

    assert src.mcp.augur_framework.tools.infrastructure.mcp_diagnostics is not None


def test_diagnostics_flags_global_mcp_worktree_path(monkeypatch, tmp_path):
    from src.mcp.augur_framework.tools.infrastructure import mcp_diagnostics

    main_root = tmp_path / "Augur"
    worktree_root = tmp_path / ".worktrees" / "feature"
    gitdir = main_root / ".git" / "worktrees" / "feature"
    gitdir.mkdir(parents=True)
    main_root.mkdir(exist_ok=True)
    worktree_root.mkdir(parents=True)
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")

    config_dir = tmp_path / "config"
    catalog_path = config_dir / "agents" / "ide_mcp_configs.yaml"
    cursor_config = tmp_path / "cursor.mcp.json"
    catalog_path.parent.mkdir(parents=True)
    cursor_config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "augur-core": {
                        "command": str(worktree_root / ".venv" / "bin" / "python3"),
                        "cwd": str(worktree_root),
                        "env": {"AUGUR_ROOT": str(worktree_root)},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    catalog_path.write_text(
        yaml.safe_dump(
            {
                "ides": {
                    "cursor": {
                        "enabled": True,
                        "display_name": "Cursor",
                        "config_path": {"all": str(cursor_config)},
                    }
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mcp_diagnostics, "get_config_dir", lambda: config_dir)

    diagnostics = mcp_diagnostics.build_mcp_diagnostics_summary(
        include_configs=True,
        include_processes=False,
        project_root=main_root,
    )

    assert diagnostics["staleMcpConfig"] is True
    assert diagnostics["configIssues"][0]["kind"] == "linked_worktree"
    assert diagnostics["configIssues"][0]["referencedPath"] == str(worktree_root)


def test_diagnostics_process_matches_only_real_augur_mcp_processes(monkeypatch, tmp_path):
    from src.mcp.augur_framework.tools.infrastructure import mcp_diagnostics

    class Completed:
        stdout = "\n".join(
            [
                ' 101 /Applications/Codex/SkyComputerUseClient turn-ended {"text":"Augur MCP summary"}',
                " 202 /Users/me/Augur/.venv/bin/python3 -m augur_framework --client-id dashboard",
                " 303 /Users/me/Augur/.venv/bin/python3 -m augur_core --client-id codex",
            ]
        )

    monkeypatch.setattr(mcp_diagnostics, "subprocess_run", lambda *args, **kwargs: Completed())

    diagnostics = mcp_diagnostics.build_mcp_diagnostics_summary(
        include_configs=False,
        include_processes=True,
        project_root=tmp_path,
    )

    commands = [process["command"] for process in diagnostics["runtime"]["processMatches"]]
    assert len(commands) == 2
    assert any("augur_framework" in command for command in commands)
    assert any("augur_core" in command for command in commands)
    assert all("SkyComputerUseClient" not in command for command in commands)

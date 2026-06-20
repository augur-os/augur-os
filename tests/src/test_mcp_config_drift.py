from __future__ import annotations

import json
from pathlib import Path

import yaml


def _write_catalog(catalog_path: Path, entries: dict) -> None:
    catalog_path.write_text(yaml.safe_dump({"ides": entries}, sort_keys=False), encoding="utf-8")


def _linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main_root = tmp_path / "Augur"
    worktree_root = tmp_path / ".worktrees" / "feature"
    gitdir = main_root / ".git" / "worktrees" / "feature"
    gitdir.mkdir(parents=True)
    main_root.mkdir(exist_ok=True)
    worktree_root.mkdir(parents=True)
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (worktree_root / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    return main_root, worktree_root


def test_global_mcp_config_flags_existing_linked_worktree_root(tmp_path):
    from src.config.mcp_config_drift import scan_global_mcp_config_references

    main_root, worktree_root = _linked_worktree(tmp_path)
    catalog_path = tmp_path / "ide_mcp_configs.yaml"
    config_path = tmp_path / "cursor.mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "augur-core": {
                        "command": str(worktree_root / ".venv" / "bin" / "python3"),
                        "args": ["-m", "augur_core"],
                        "cwd": str(worktree_root),
                        "env": {
                            "AUGUR_ROOT": str(worktree_root),
                            "PYTHONPATH": f"{worktree_root}:{worktree_root / 'src' / 'mcp'}",
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    _write_catalog(
        catalog_path,
        {
            "cursor": {
                "enabled": True,
                "display_name": "Cursor",
                "config_path": {"all": str(config_path)},
                "config_format": "json",
                "config_structure": "flat",
                "server_key": "mcpServers",
            }
        },
    )

    issues = scan_global_mcp_config_references(
        project_root=main_root,
        config_catalog_path=catalog_path,
    )

    assert [issue.kind for issue in issues] == ["linked_worktree"]
    assert issues[0].client_key == "cursor"
    assert issues[0].referenced_path == worktree_root


def test_global_mcp_config_flags_deleted_checkout_path(tmp_path):
    from src.config.mcp_config_drift import scan_global_mcp_config_references

    main_root = tmp_path / "Augur"
    main_root.mkdir()
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    missing_root = tmp_path / ".worktrees" / "deleted"
    catalog_path = tmp_path / "ide_mcp_configs.yaml"
    config_path = tmp_path / "claude_desktop_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "augur-core": {
                        "command": "python3",
                        "args": ["-m", "augur_core"],
                        "cwd": str(missing_root),
                        "env": {"AUGUR_ROOT": str(missing_root)},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    _write_catalog(
        catalog_path,
        {
            "claude_desktop": {
                "enabled": True,
                "display_name": "Claude Desktop",
                "config_path": {"all": str(config_path)},
                "config_format": "json",
                "config_structure": "flat",
                "server_key": "mcpServers",
            }
        },
    )

    issues = scan_global_mcp_config_references(
        project_root=main_root,
        config_catalog_path=catalog_path,
    )

    assert [issue.kind for issue in issues] == ["missing_path"]
    assert issues[0].referenced_path == missing_root


def test_repo_local_mcp_config_is_not_flagged_for_worktree_root(tmp_path):
    from src.config.mcp_config_drift import scan_global_mcp_config_references

    main_root, worktree_root = _linked_worktree(tmp_path)
    local_config = main_root / ".vscode" / "mcp.json"
    local_config.parent.mkdir()
    local_config.write_text(
        json.dumps(
            {
                "servers": {
                    "augur-core": {
                        "command": "python3",
                        "args": ["-m", "augur_core"],
                        "cwd": str(worktree_root),
                        "env": {"AUGUR_ROOT": str(worktree_root)},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    catalog_path = tmp_path / "ide_mcp_configs.yaml"
    _write_catalog(
        catalog_path,
        {
            "vscode_copilot": {
                "enabled": True,
                "display_name": "VS Code Copilot",
                "config_path": {"all": "{repo_root}/.vscode/mcp.json"},
                "config_format": "json",
                "config_structure": "flat",
                "server_key": "servers",
            }
        },
    )

    issues = scan_global_mcp_config_references(
        project_root=main_root,
        config_catalog_path=catalog_path,
    )

    assert issues == []


def test_directory_backed_connector_config_is_skipped(tmp_path):
    from src.config.mcp_config_drift import scan_global_mcp_config_references

    main_root = tmp_path / "Augur"
    main_root.mkdir()
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    connector_dir = tmp_path / "connectors" / "dxt" / "installed"
    connector_dir.mkdir(parents=True)
    catalog_path = tmp_path / "ide_mcp_configs.yaml"
    _write_catalog(
        catalog_path,
        {
            "perplexity": {
                "enabled": True,
                "display_name": "Perplexity",
                "config_path": {"all": str(connector_dir)},
                "config_format": "dxt",
            }
        },
    )

    issues = scan_global_mcp_config_references(
        project_root=main_root,
        config_catalog_path=catalog_path,
    )

    assert issues == []

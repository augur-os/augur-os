from __future__ import annotations

import json
import ntpath
import os
import sys
import pytest
import tomllib
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_toml_dump_quotes_project_path_keys():
    from scripts.mcp_ide_config import _toml_dump

    rendered = _toml_dump(
        {
            "projects": {
                "/Users/tester/Projects/Augur": {
                    "trust_level": "trusted",
                }
            }
        }
    )

    assert '[projects."/Users/tester/Projects/Augur"]' in rendered
    parsed = tomllib.loads(rendered)
    assert parsed["projects"]["/Users/tester/Projects/Augur"]["trust_level"] == "trusted"


def test_windows_config_path_expands_appdata_for_cursor(tmp_path):
    from scripts.mcp_ide_config import _get_config_path_for_platform

    ide_config = {
        "config_path": {
            "windows": r"%APPDATA%/Cursor/User/globalStorage/cursor.mcp/mcp.json",
        }
    }

    with (
        patch("platform.system", return_value="Windows"),
        patch.dict(
            os.environ,
            {"APPDATA": r"C:\Users\tester\AppData\Roaming"},
            clear=False,
        ),
    ):
        result = _get_config_path_for_platform(ide_config, tmp_path)

    expected = Path(ntpath.normpath(r"C:\Users\tester\AppData\Roaming\Cursor\User\globalStorage\cursor.mcp\mcp.json"))
    assert result == expected


@pytest.mark.skipif(
    sys.platform == "win32", reason="darwin claude_desktop path resolution; WindowsPath drive-anchors the POSIX path"
)
def test_darwin_config_path_keeps_posix_absolute_path(tmp_path):
    from scripts.mcp_ide_config import _get_config_path_for_platform

    ide_config = {
        "config_path": {
            "darwin": "~/Library/Application Support/Claude/claude_desktop_config.json",
        }
    }

    with (
        patch("platform.system", return_value="Darwin"),
        patch.dict(
            os.environ,
            {"HOME": "/Users/tester"},
            clear=False,
        ),
    ):
        result = _get_config_path_for_platform(ide_config, tmp_path)

    assert result == Path("/Users/tester/Library/Application Support/Claude/claude_desktop_config.json")


def test_opencode_config_uses_local_command_array_and_environment(tmp_path):
    from scripts.mcp_ide_config import _configure_ide

    config_path = tmp_path / "opencode.json"
    config_path.write_text(
        json.dumps(
            {
                "mcp": {
                    "context7": {
                        "type": "local",
                        "command": ["context7"],
                    },
                    "augur": {
                        "type": "local",
                        "command": ["old"],
                        "enabled": False,
                        "timeout": 9000,
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    changed = _configure_ide(
        "opencode",
        {
            "display_name": "OpenCode",
            "config_format": "json",
            "config_structure": "flat",
            "config_path": {"all": str(config_path)},
            "server_key": "mcp",
        },
        tmp_path,
        {
            "augur-core": {
                "command": "python3",
                "args": ["-m", "augur_core", "--client-id", "opencode"],
                "cwd": str(tmp_path),
                "env": {"AUGUR_ROOT": str(tmp_path), "PYTHONUNBUFFERED": "1"},
            }
        },
        {},
        should_apply=True,
        quiet_mode=True,
    )

    written = json.loads(config_path.read_text(encoding="utf-8"))

    assert changed is True
    assert written["$schema"] == "https://opencode.ai/config.json"
    assert "augur" not in written["mcp"]
    assert written["mcp"]["context7"] == {
        "type": "local",
        "command": ["context7"],
    }
    assert written["mcp"]["augur-core"] == {
        "type": "local",
        "command": ["python3", "-m", "augur_core", "--client-id", "opencode"],
        "environment": {"AUGUR_ROOT": str(tmp_path), "PYTHONUNBUFFERED": "1"},
    }


def test_per_project_config_prunes_augur_servers_from_stale_worktree_projects(tmp_path):
    from scripts.mcp_ide_config import _configure_ide

    main_root = tmp_path / "Augur"
    linked_root = tmp_path / ".worktrees" / "feature"
    missing_root = tmp_path / ".worktrees" / "deleted"
    sibling_root = tmp_path / "Augur-copy"
    gitdir = main_root / ".git" / "worktrees" / "feature"
    gitdir.mkdir(parents=True)
    main_root.mkdir(exist_ok=True)
    linked_root.mkdir(parents=True)
    sibling_root.mkdir()
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (linked_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    (sibling_root / "project.yaml").write_text("name: augur-copy\n", encoding="utf-8")
    (linked_root / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")

    config_path = tmp_path / "claude.json"
    config_path.write_text(
        json.dumps(
            {
                "projects": {
                    str(linked_root): {
                        "trust_level": "trusted",
                        "mcpServers": {
                            "augur-core": {
                                "command": "python3",
                                "cwd": str(linked_root),
                            },
                            "context7": {"command": "context7"},
                        },
                    },
                    str(missing_root): {
                        "mcpServers": {
                            "augur-core": {
                                "command": "python3",
                                "cwd": str(missing_root),
                            }
                        }
                    },
                    str(sibling_root): {
                        "mcpServers": {
                            "augur-core": {
                                "command": "python3",
                                "cwd": str(sibling_root),
                            }
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    changed = _configure_ide(
        "claude_code",
        {
            "display_name": "Claude Code",
            "config_format": "json",
            "config_structure": "per_project",
            "config_path": {"all": str(config_path)},
            "server_key": "mcpServers",
        },
        main_root,
        {
            "augur-core": {
                "command": "python3",
                "args": ["-m", "augur_core"],
                "cwd": str(main_root),
                "env": {"AUGUR_ROOT": str(main_root)},
            }
        },
        {},
        should_apply=True,
        quiet_mode=True,
    )

    written = json.loads(config_path.read_text(encoding="utf-8"))
    projects = written["projects"]

    assert changed is True
    assert "augur-core" in projects[str(main_root)]["mcpServers"]
    assert "augur-core" not in projects[str(linked_root)]["mcpServers"]
    assert projects[str(linked_root)]["mcpServers"]["context7"] == {"command": "context7"}
    assert projects[str(linked_root)]["trust_level"] == "trusted"
    assert str(missing_root) not in projects
    assert "augur-core" in projects[str(sibling_root)]["mcpServers"]

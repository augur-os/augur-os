"""Auto-generated importability test for codex_cli."""
from __future__ import annotations

import sys
import platform
from pathlib import Path
from unittest.mock import patch

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

AUGUR_AI_DIR = Path(__file__).resolve().parents[1]
if str(AUGUR_AI_DIR) not in sys.path:
    sys.path.insert(0, str(AUGUR_AI_DIR))


def test_codex_cli_importable():
    """Verify that codex_cli can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.ai.augur.adapters.codex_cli")
    assert mod is not None


def test_codex_cli_builds_dynamic_mcp_entry():
    from skills.ai.augur.adapters import codex_cli

    with patch("src.cli_config.codex_runtime.platform.system", return_value="Linux"):
        entry = codex_cli._build_codex_mcp_entry()

    assert Path(entry["command"]).is_absolute()
    assert entry["command"].replace("\\", "/").endswith("/scripts/augur-codex-mcp")
    assert entry["args"] == ["-m", "augur_core", "--client-id", "codex"]
    assert "env" not in entry
    assert "cwd" not in entry
    assert "augur_mcp" not in " ".join(entry["args"])


def test_codex_cli_builds_windows_mcp_entry_when_platform_is_windows():
    from skills.ai.augur.adapters import codex_cli

    with patch("src.cli_config.codex_runtime.platform.system", return_value="Windows"):
        entry = codex_cli._build_codex_mcp_entry()

    assert entry["command"] == "powershell.exe"
    assert entry["args"][:4] == ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
    assert entry["args"][4] == str(PROJECT_ROOT / "scripts" / "augur-codex-mcp.ps1")
    assert entry["args"][5:] == ["-m", "augur_core", "--client-id", "codex"]
    assert "env" not in entry
    assert "cwd" not in entry


def test_codex_cli_ensure_config_writes_dynamic_worktree_entry(tmp_path):
    from skills.ai.augur.adapters import codex_cli

    config_home = tmp_path / "home"
    config_home.mkdir(parents=True)
    adapter = codex_cli.CodexCliAdapter()

    with patch("skills.ai.augur.adapters.codex_cli.Path.home", return_value=config_home):
        result = adapter.ensure_config()

    config_path = config_home / ".codex" / "config.toml"
    config_text = config_path.read_text(encoding="utf-8")
    assert result["success"] is True
    if platform.system() == "Windows":
        assert 'command = "powershell.exe"' in config_text
        assert "augur-codex-mcp.ps1" in config_text
        assert '"-m", "augur_core", "--client-id", "codex"' in config_text
    else:
        assert "/scripts/augur-codex-mcp" in config_text
        assert 'args = ["-m", "augur_core", "--client-id", "codex"]' in config_text
    assert 'args = ["-lc"' not in config_text
    assert 'root="$(pwd -P)"' not in config_text
    assert "[mcp_servers.augur-core]" in config_text
    # Track 3a: the legacy `augur` monolith split into augur-core + augur-framework;
    # both are exported to codex via per_client_args in config/system/mcp_servers.yaml.
    assert "[mcp_servers.augur-framework]" in config_text
    assert 'args = ["-m", "augur_framework", "--client-id", "codex"]' in config_text or '"-m", "augur_framework", "--client-id", "codex"' in config_text
    assert "[mcp_servers.augur]" not in config_text
    assert "augur_mcp" not in config_text
    assert "cwd =" not in config_text
    assert 'AUGUR_ROOT = ' not in config_text
    assert "[mcp_servers.augur-core.env]" not in config_text

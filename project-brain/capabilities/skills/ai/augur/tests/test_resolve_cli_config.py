"""Tests for resolve_cli_config.py (ADR-034)."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Load resolve_cli_config from its project-brain skill script location.
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from resolve_cli_config import get_cli_agents_path, get_cli_configs  # noqa: E402


@pytest.fixture
def cli_agents_file(tmp_path: Path) -> Path:
    """Create a temporary cli_agents.yaml for testing."""
    content = {
        "agents": {
            "claude": {
                "cmd": ["claude", "--dangerously-skip-permissions"],
                "cwd": ".",
                "env": {"HOMOSAPIEN_WELCOMED": "1"},
            },
            "codex": {
                "cmd": ["codex", "--full-auto"],
                "cwd": ".",
                "env": {"HOMOSAPIEN_WELCOMED": "1"},
            },
            "kimi": {
                "cmd": ["kimi", "--yolo"],
                "cwd": ".",
                "env": {"HOMOSAPIEN_WELCOMED": "1"},
            },
        }
    }
    config_path = tmp_path / "cli_agents.yaml"
    config_path.write_text(yaml.dump(content))
    return config_path


def test_resolve_cli_config_reads_agents(cli_agents_file: Path):
    """get_cli_configs() returns entries from cli_agents.yaml."""
    configs = get_cli_configs(cli_agents_file)

    assert "claude" in configs
    assert "codex" in configs
    assert "kimi" in configs

    assert configs["claude"].cmd == ["claude", "--dangerously-skip-permissions"]
    assert configs["claude"].label == "Claude Code"
    assert configs["codex"].cmd == ["codex", "--full-auto"]
    assert configs["kimi"].cmd == ["kimi", "--yolo"]


def test_default_cli_agents_path_uses_vault_config_dir(tmp_path: Path):
    """Default cli_agents.yaml path is the Obsidian config root."""
    config_dir = tmp_path / "vault" / "config"

    with patch("src.config.paths.get_vault_config_dir", return_value=config_dir):
        result = get_cli_agents_path()

    assert result == config_dir / "ai" / "cli_agents.yaml"


def test_resolve_cli_config_excludes_unknown_entries(cli_agents_file: Path):
    """Only entries in CLI_ENTRIES are returned."""
    configs = get_cli_configs(cli_agents_file)

    # These aren't in CLI_ENTRIES so shouldn't appear even if added to yaml
    assert "augur" not in configs
    assert "server" not in configs


def test_resolve_cli_config_missing_file():
    """Missing cli_agents.yaml raises FileNotFoundError."""
    fake_path = Path("/nonexistent/cli_agents.yaml")
    with pytest.raises(FileNotFoundError):
        get_cli_configs(fake_path)


def test_cli_config_to_dict(cli_agents_file: Path):
    """CliConfig.to_dict() returns serializable dict."""
    configs = get_cli_configs(cli_agents_file)
    claude = configs["claude"]
    d = claude.to_dict()

    assert d["cli_id"] == "claude"
    assert d["cmd"] == ["claude", "--dangerously-skip-permissions"]
    assert d["label"] == "Claude Code"

    # Should be JSON serializable
    json.dumps(d)


def test_cli_config_preserves_env(cli_agents_file: Path):
    """Environment variables are preserved from cli_agents.yaml."""
    configs = get_cli_configs(cli_agents_file)
    assert configs["claude"].env == {"HOMOSAPIEN_WELCOMED": "1"}


def test_cli_config_preserves_cwd(cli_agents_file: Path):
    """Working directory is preserved from cli_agents.yaml."""
    configs = get_cli_configs(cli_agents_file)
    assert configs["claude"].cwd == "."

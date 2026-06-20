"""Tests for augur init project creation."""

import json
from pathlib import Path

import yaml

# Import from the script directly
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _onboard_scripts_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "project-brain" / "capabilities" / "skills" / "onboard" / "scripts"


def test_write_project_yaml(tmp_path):
    """write_project_yaml creates correct project.yaml."""
    # Add script to path
    sys.path.insert(0, str(_onboard_scripts_dir()))
    from augur_init import write_project_yaml

    write_project_yaml(tmp_path, "myapp", 3001)
    loaded = yaml.safe_load((tmp_path / "project.yaml").read_text())
    assert loaded["name"] == "myapp"
    assert loaded["port"] == 3001


def test_create_external_dirs(tmp_path):
    """create_external_dirs creates all scoped directories."""
    sys.path.insert(0, str(_onboard_scripts_dir()))
    from augur_init import create_external_dirs

    fakehome = tmp_path / "fakehome"
    create_external_dirs("testapp", home=fakehome)
    assert (fakehome / "Vault" / "testapp").is_dir()
    assert (fakehome / "Vault" / "testapp" / "skills").is_dir()
    assert (fakehome / "Vault" / "testapp" / "drafts" / "staging").is_dir()
    assert (fakehome / "Documents" / "testapp").is_dir()
    assert (fakehome / "Library" / "Logs" / "testapp").is_dir()
    assert (fakehome / "Library" / "Caches" / "testapp").is_dir()


def test_write_mcp_config(tmp_path):
    """write_mcp_config generates correct .claude/mcp.json."""
    sys.path.insert(0, str(_onboard_scripts_dir()))
    from augur_init import write_mcp_config

    write_mcp_config(tmp_path, "myapp")
    mcp = json.loads((tmp_path / ".claude" / "mcp.json").read_text())
    assert "myapp" in mcp["mcpServers"]
    assert mcp["mcpServers"]["myapp"]["env"]["AUGUR_ROOT"] == str(tmp_path)

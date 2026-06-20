"""Tests for ai_monitor config loading."""
import yaml
from pathlib import Path


def test_daemon_config_loads():
    """Config file is valid YAML with expected keys."""
    config_path = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1]) / "config" / "system" / "daemon.yaml"
    assert config_path.exists(), f"Config not found: {config_path}"
    data = yaml.safe_load(config_path.read_text())
    assert "ai_monitor" in data
    monitor = data["ai_monitor"]
    assert monitor["enabled"] is False
    assert monitor["use_pty"] is True
    assert isinstance(monitor["context_pressure_bytes"], int)
    assert isinstance(monitor["debounce_seconds"], (int, float))
    assert isinstance(monitor["vault_check_interval"], int)
    assert isinstance(monitor["vault_auto_commit"], bool)
    assert isinstance(monitor["vault_auto_commit_paths"], list)

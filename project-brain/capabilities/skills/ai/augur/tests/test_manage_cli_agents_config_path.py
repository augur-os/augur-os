"""Tests for manage-cli-agents config path ownership."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from skills.ai.scripts.mcp import _coerce_client_filter, _get_cli_agents_file


def test_manage_cli_agents_file_uses_vault_config_dir(tmp_path: Path) -> None:
    config_dir = tmp_path / "vault" / "config"

    with patch("src.config.paths.get_vault_config_dir", return_value=config_dir):
        result = _get_cli_agents_file()

    assert result == config_dir / "ai" / "cli_agents.yaml"


def test_sync_status_client_filter_accepts_dashboard_preset_shape() -> None:
    assert _coerce_client_filter(None) is None
    assert _coerce_client_filter("codex, claude-code") == ["codex", "claude-code"]
    assert _coerce_client_filter(["codex", ""]) == ["codex"]

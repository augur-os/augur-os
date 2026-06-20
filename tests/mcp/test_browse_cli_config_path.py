from __future__ import annotations

from unittest.mock import patch


def test_browse_cli_default_name_reads_vault_config_root(tmp_path):
    from src.mcp.augur_framework.tools.infrastructure.browse import cli

    config_dir = tmp_path / "vault" / "config"
    (config_dir / "ai").mkdir(parents=True)
    (config_dir / "ai" / "cli_agents.yaml").write_text(
        "agents:\n" "  claude:\n" "    cmd: [\"claude\"]\n",
        encoding="utf-8",
    )

    with patch.object(cli, "get_vault_config_dir", return_value=config_dir):
        assert cli._resolve_default_cli_name() == "claude"

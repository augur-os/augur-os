"""End-to-end test for `aug config sync`."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.cli_config.adapters import ClaudeAdapter, CodexAdapter, CopilotAdapter, GeminiAdapter
from src.cli_config.config_sync import _handle_status, _handle_sync


@pytest.fixture
def manifest_path(tmp_path: Path) -> Path:
    p = tmp_path / "mcp_servers.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "project_tier": [
                    {
                        "id": "augur",
                        "command": "python",
                        "args": ["-m", "augur_framework"],
                        "scope": "global",
                    },
                    {
                        "id": "augur-project",
                        "command": "python",
                        "args": ["-m", "augur_project"],
                        "scope": "project",
                    },
                ],
                "vault_tier": [
                    {
                        "id": "augur-apple",
                        "command": "python",
                        "args": ["-m", "augur_shared.bundle_server", "apple"],
                        "bundle": "apple",
                        "bundle_path": "/tmp/apple",
                    }
                ],
                "monolith_exclusions": ["apple"],
            }
        )
    )
    return p


def test_sync_runs_against_tmp_configs(monkeypatch, tmp_path: Path, manifest_path: Path) -> None:
    """Full orchestrator round-trip: sync writes to tmp paths for each adapter."""
    claude_cfg = tmp_path / "claude_settings.json"
    codex_cfg = tmp_path / "codex_config.toml"
    gemini_cfg = tmp_path / "gemini_settings.json"
    copilot_cfg = tmp_path / "copilot_mcp.json"

    claude_cfg.write_text("{}")
    codex_cfg.write_text("")
    gemini_cfg.write_text("{}")
    copilot_cfg.write_text("{}")

    with (
        patch("src.cli_config.config_sync.load_manifest") as load_m,
        patch("src.cli_config.config_sync.get_project_root", return_value=tmp_path),
        patch.object(ClaudeAdapter, "default_config_path", return_value=claude_cfg),
        patch.object(CodexAdapter, "default_config_path", return_value=codex_cfg),
        patch.object(GeminiAdapter, "default_config_path", return_value=gemini_cfg),
        patch.object(CopilotAdapter, "default_config_path", return_value=copilot_cfg),
    ):
        from src.cli_config.manifest import load_manifest

        load_m.return_value = load_manifest(manifest_path)

        import argparse

        args = argparse.Namespace(dry_run=False, client=None)
        rc = _handle_sync(args)
        assert rc == 0

    project_servers = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]
    assert "augur-project" in project_servers, "project-scoped servers belong in repo-local .mcp.json"

    assert "augur-apple" in json.loads(claude_cfg.read_text())["mcpServers"]
    assert "augur-project" not in json.loads(claude_cfg.read_text())["mcpServers"]
    assert "augur-apple" not in json.loads(gemini_cfg.read_text())["mcpServers"]
    assert "augur-project" not in json.loads(gemini_cfg.read_text())["mcpServers"]
    assert "augur-apple" in codex_cfg.read_text()
    assert "augur-project" not in codex_cfg.read_text()
    copilot_servers = json.loads(copilot_cfg.read_text())["mcpServers"]
    assert "augur-apple" not in copilot_servers
    assert "augur-project" not in copilot_servers
    assert "augur" in copilot_servers


def test_status_signals_drift(monkeypatch, tmp_path: Path, manifest_path: Path) -> None:
    claude_cfg = tmp_path / "claude_settings.json"
    codex_cfg = tmp_path / "codex_config.toml"
    gemini_cfg = tmp_path / "gemini_settings.json"
    copilot_cfg = tmp_path / "copilot_mcp.json"
    claude_cfg.write_text("{}")
    codex_cfg.write_text("")
    gemini_cfg.write_text("{}")
    copilot_cfg.write_text("{}")

    with (
        patch("src.cli_config.config_sync.load_manifest") as load_m,
        patch.object(ClaudeAdapter, "default_config_path", return_value=claude_cfg),
        patch.object(CodexAdapter, "default_config_path", return_value=codex_cfg),
        patch.object(GeminiAdapter, "default_config_path", return_value=gemini_cfg),
        patch.object(CopilotAdapter, "default_config_path", return_value=copilot_cfg),
    ):
        from src.cli_config.manifest import load_manifest

        load_m.return_value = load_manifest(manifest_path)

        import argparse

        args = argparse.Namespace(client=None)
        rc = _handle_status(args)
        assert rc == 1  # drift exists


def test_dry_run_does_not_write(monkeypatch, tmp_path: Path, manifest_path: Path) -> None:
    claude_cfg = tmp_path / "claude_settings.json"
    codex_cfg = tmp_path / "codex_config.toml"
    gemini_cfg = tmp_path / "gemini_settings.json"
    copilot_cfg = tmp_path / "copilot_mcp.json"
    claude_cfg.write_text("{}")
    codex_cfg.write_text("")
    gemini_cfg.write_text("{}")
    copilot_cfg.write_text("{}")
    before_claude = claude_cfg.read_text()

    with (
        patch("src.cli_config.config_sync.load_manifest") as load_m,
        patch.object(ClaudeAdapter, "default_config_path", return_value=claude_cfg),
        patch.object(CodexAdapter, "default_config_path", return_value=codex_cfg),
        patch.object(GeminiAdapter, "default_config_path", return_value=gemini_cfg),
        patch.object(CopilotAdapter, "default_config_path", return_value=copilot_cfg),
    ):
        from src.cli_config.manifest import load_manifest

        load_m.return_value = load_manifest(manifest_path)
        import argparse

        args = argparse.Namespace(dry_run=True, client=None)
        _handle_sync(args)

    assert claude_cfg.read_text() == before_claude


def test_copilot_sync_preserves_user_entries(tmp_path: Path, manifest_path: Path) -> None:
    """Copilot adapter writes augur servers into mcp-config.json, keeps user's entries."""
    copilot_cfg = tmp_path / "mcp-config.json"
    copilot_cfg.write_text(json.dumps({"mcpServers": {"context7": {"command": "npx"}}}))

    with (
        patch("src.cli_config.config_sync.load_manifest") as load_m,
        patch.object(CopilotAdapter, "default_config_path", return_value=copilot_cfg),
    ):
        from src.cli_config.manifest import load_manifest

        load_m.return_value = load_manifest(manifest_path)

        import argparse

        args = argparse.Namespace(dry_run=False, client="copilot")
        rc = _handle_sync(args)
        assert rc == 0

    servers = json.loads(copilot_cfg.read_text())["mcpServers"]
    assert "context7" in servers, "user-owned entries must survive sync"
    assert "augur" in servers
    assert "augur-apple" not in servers, "bundled vault-tier entries are filtered (Gemini parity)"
    assert "augur-project" not in servers, "project-scoped entries never ship to home configs"


def test_manifest_accepts_copilot_per_client_args(tmp_path: Path) -> None:
    p = tmp_path / "mcp_servers.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "project_tier": [
                    {
                        "id": "augur",
                        "command": "python",
                        "args": ["-m", "augur_framework"],
                        "scope": "global",
                        "per_client_args": {"copilot": ["--client-id", "copilot"]},
                    }
                ]
            }
        )
    )
    from src.cli_config.manifest import load_manifest

    manifest = load_manifest(p)  # must not raise ValueError (copilot now a known client)
    entries = manifest.all_augur_servers_for_client("copilot")
    assert entries and entries[0].per_client_args["copilot"] == ["--client-id", "copilot"]

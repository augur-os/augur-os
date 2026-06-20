from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path


def test_resolve_agent_cli_config_uses_client_routing_default(monkeypatch) -> None:
    from src.lib import agent_cli_config

    monkeypatch.setattr(
        agent_cli_config,
        "_resolve_client_routing",
        lambda _action_id: SimpleNamespace(
            client_id="codex",
            client_type="ide",
            source="global",
        ),
    )
    monkeypatch.setattr(
        agent_cli_config,
        "load_cli_agents",
        lambda: (
            Path("cli_agents.yaml"),
            {
                "claude": {"print_cmd": ["claude", "--print"]},
                "codex": {"print_cmd": ["codex", "exec", "--json"]},
            },
        ),
    )

    result = agent_cli_config.resolve_agent_cli_config("document-ocr-cloud")

    assert result.cli_id == "codex"
    assert result.command == ["codex", "exec", "--json"]
    assert result.source == "global"
    assert result.error is None


def test_resolve_agent_cli_config_uses_cli_registry_order_for_implicit_default(
    monkeypatch,
) -> None:
    from src.lib import agent_cli_config

    monkeypatch.setattr(
        agent_cli_config,
        "_resolve_client_routing",
        lambda _action_id: SimpleNamespace(
            client_id="",
            client_type="ide",
            source="implicit",
        ),
    )
    monkeypatch.setattr(
        agent_cli_config,
        "load_cli_agents",
        lambda: (
            Path("cli_agents.yaml"),
            {
                "codex": {"print_cmd": ["codex", "exec", "--json"]},
                "claude": {"print_cmd": ["claude", "--print"]},
            },
        ),
    )

    result = agent_cli_config.resolve_agent_cli_config("run-oneshot-cli")

    assert result.cli_id == "codex"
    assert result.command == ["codex", "exec", "--json"]
    assert result.source == "cli_agents"


def test_build_agent_command_normalizes_claude_stream_json(tmp_path: Path) -> None:
    from src.lib.agent_cli_config import build_agent_command

    command = build_agent_command(
        "C:\\Tools\\claude.exe",
        "claude",
        "OCR prompt",
        configured_command=["claude", "-p", "--output-format", "stream-json"],
        job_dir=tmp_path,
    )

    assert "--verbose" in command
    assert "--dangerously-skip-permissions" in command
    assert "--permission-mode" not in command
    assert f"--add-dir={tmp_path}" in command

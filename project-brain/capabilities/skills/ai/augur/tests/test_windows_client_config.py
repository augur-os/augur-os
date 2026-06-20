"""Tests for shared client config path wiring."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from skills.ai.augur.adapters.claude_desktop import ClaudeDesktopAdapter
from skills.ai.augur.adapters.cowork import CoworkAdapter


def _write_plugin_pack_formatter(project_root: Path, monkeypatch) -> None:
    """Provide a project-local plugin-pack formatter for temp checkout tests."""
    monkeypatch.delitem(sys.modules, "mcp_config", raising=False)
    formatters_dir = project_root / "project-brain" / "capabilities" / "skills" / "plugin-pack" / "scripts" / "formatters"
    formatters_dir.mkdir(parents=True)
    (formatters_dir / "mcp_config.py").write_text(
        "def build_augur_mcp_servers(project_root, python_cmd, client_id):\n"
        "    return {'augur': {\n"
        "        'command': str(python_cmd),\n"
        "        'args': ['-m', 'augur_mcp'],\n"
        "        'cwd': str(project_root),\n"
        "        'env': {'AUGUR_ROOT': str(project_root)},\n"
        "    }}\n"
        "def prune_augur_servers(servers):\n"
        "    for key in list(servers):\n"
        "        if key.startswith('legacy-augur'):\n"
        "            servers.pop(key, None)\n",
        encoding="utf-8",
    )


def test_claude_desktop_adapter_uses_shared_runtime_dir(monkeypatch, tmp_path):
    """Claude Desktop config should be written under the shared runtime dir."""
    import skills.ai.augur.adapters.claude_desktop as module

    runtime_dir = tmp_path / "runtime"
    project_root = tmp_path / "project"
    python_path = tmp_path / "python"
    _write_plugin_pack_formatter(project_root, monkeypatch)
    calls: list[str] = []

    def fake_get_client_runtime_dir(client: str) -> Path:
        calls.append(client)
        return runtime_dir

    monkeypatch.setattr(module, "get_client_runtime_dir", fake_get_client_runtime_dir)
    monkeypatch.setattr(module, "get_project_root", lambda: project_root)
    monkeypatch.setattr(module, "get_python_executable", lambda: python_path)

    result = ClaudeDesktopAdapter().ensure_config()

    expected_path = runtime_dir / "claude_desktop_config.json"
    assert calls == ["claude-desktop"]
    assert result["success"] is True
    assert result["changed"] is True
    assert result["config_paths"] == [str(expected_path)]
    assert expected_path.exists()

    config = json.loads(expected_path.read_text(encoding="utf-8"))
    assert config["mcpServers"]["augur"]["command"] == str(python_path)
    assert config["mcpServers"]["augur"]["cwd"] == str(project_root)


def test_claude_desktop_adapter_rewrites_stale_augur_root(monkeypatch, tmp_path):
    """Claude Desktop config should be refreshed when Augur points at an old checkout."""
    import skills.ai.augur.adapters.claude_desktop as module

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    project_root = tmp_path / "project"
    project_root.mkdir()
    python_path = tmp_path / "python"
    _write_plugin_pack_formatter(project_root, monkeypatch)
    config_path = runtime_dir / "claude_desktop_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "augur": {
                        "command": str(python_path),
                        "env": {"AUGUR_ROOT": str(tmp_path / "missing-old-checkout")},
                    },
                    "other": {"command": "other-mcp"},
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "get_client_runtime_dir", lambda _client: runtime_dir)
    monkeypatch.setattr(module, "get_project_root", lambda: project_root)
    monkeypatch.setattr(module, "get_python_executable", lambda: python_path)

    result = ClaudeDesktopAdapter().ensure_config()

    assert result["success"] is True
    assert result["changed"] is True
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["mcpServers"]["augur"]["env"]["AUGUR_ROOT"] == str(project_root)
    assert config["mcpServers"]["other"] == {"command": "other-mcp"}


def test_claude_desktop_adapter_rewrites_generic_python_command(monkeypatch, tmp_path):
    """Claude Desktop config should use the project Python, not a generic python3."""
    import skills.ai.augur.adapters.claude_desktop as module

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    project_root = tmp_path / "project"
    project_root.mkdir()
    python_path = tmp_path / "python"
    _write_plugin_pack_formatter(project_root, monkeypatch)
    config_path = runtime_dir / "claude_desktop_config.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "augur": {
                        "command": "python3",
                        "env": {"AUGUR_ROOT": str(project_root)},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "get_client_runtime_dir", lambda _client: runtime_dir)
    monkeypatch.setattr(module, "get_project_root", lambda: project_root)
    monkeypatch.setattr(module, "get_python_executable", lambda: python_path)

    result = ClaudeDesktopAdapter().ensure_config()

    assert result["success"] is True
    assert result["changed"] is True
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["mcpServers"]["augur"]["command"] == str(python_path)


def test_cowork_adapter_uses_shared_claude_desktop_runtime_dir(monkeypatch, tmp_path):
    """Cowork should resolve the shared Claude Desktop MCP config path."""
    import skills.ai.augur.adapters.cowork as module

    runtime_dir = tmp_path / "runtime"
    calls: list[str] = []

    def fake_get_client_runtime_dir(client: str) -> Path:
        calls.append(client)
        return runtime_dir

    monkeypatch.setattr(module, "get_client_runtime_dir", fake_get_client_runtime_dir)

    assert CoworkAdapter()._get_claude_desktop_config_path() == runtime_dir / "claude_desktop_config.json"
    assert calls == ["claude-desktop"]

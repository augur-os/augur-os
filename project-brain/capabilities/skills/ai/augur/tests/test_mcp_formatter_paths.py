from __future__ import annotations

import importlib
import sys
from pathlib import Path


REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SHARED_VAULT_ROOT = REPO_ROOT / "project-brain"
AI_SKILL_ROOT = SHARED_VAULT_ROOT / "capabilities" / "skills" / "ai"
for _path in (REPO_ROOT, SHARED_VAULT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


ADAPTER_PATHS = [
    AI_SKILL_ROOT / "augur" / "adapters" / "claude_desktop.py",
    AI_SKILL_ROOT / "augur" / "adapters" / "cursor.py",
    AI_SKILL_ROOT / "augur" / "adapters" / "cursor_cli.py",
    AI_SKILL_ROOT / "augur" / "adapters" / "kimi_cli.py",
    AI_SKILL_ROOT / "augur" / "adapters" / "opencode.py",
]


def _write_stub_formatter(project_root: Path) -> Path:
    formatters_dir = project_root / "project-brain" / "capabilities" / "skills" / "plugin-pack" / "scripts" / "formatters"
    formatters_dir.mkdir(parents=True)
    (formatters_dir / "mcp_config.py").write_text(
        "def build_augur_mcp_servers(project_root, python_cmd, client_id):\n"
        "    return {'client': client_id, 'project_root': str(project_root), 'python': python_cmd}\n"
        "def prune_augur_servers(servers):\n"
        "    servers.pop('legacy-augur', None)\n",
        encoding="utf-8",
    )
    return formatters_dir


def test_kimi_cli_loads_mcp_formatter_from_shared_vault(tmp_path, monkeypatch):
    """Kimi CLI should import plugin-pack formatters from project-brain."""
    formatters_dir = _write_stub_formatter(tmp_path)
    monkeypatch.delitem(sys.modules, "mcp_config", raising=False)

    mod = importlib.import_module("skills.ai.augur.adapters.kimi_cli")
    try:
        result = mod.KimiCliAdapter()._get_mcp_entries(tmp_path, tmp_path / "data")

        assert result["client"] == "kimi_cli"
        assert str(formatters_dir) in sys.path
    finally:
        sys.modules.pop("mcp_config", None)
        if str(formatters_dir) in sys.path:
            sys.path.remove(str(formatters_dir))


def test_ai_adapters_do_not_reference_retired_plugin_pack_root():
    """Formatter imports must not use project_root/skills/plugin-pack."""
    retired_root = "project_root / " + '"skills"' + ' / "plugin-pack"'
    for adapter_path in ADAPTER_PATHS:
        source = adapter_path.read_text(encoding="utf-8")
        assert retired_root not in source

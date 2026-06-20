"""Auto-generated importability test for ide_pillars."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

LIB_DIR = Path(__file__).resolve().parents[1] / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))


def test_ide_pillars_importable():
    """Verify that ide_pillars can be imported without errors."""
    mod = importlib.import_module("src.lib.ai.ide_pillars")
    assert mod is not None


def test_check_agents_pillar_uses_agent_registry(tmp_path: Path):
    mod = importlib.import_module("src.lib.ai.ide_pillars")

    agents_dir = tmp_path / "plugins" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "registry.json").write_text('{"agents": {}}', encoding="utf-8")
    (agents_dir / "developer.md").write_text("# developer\n", encoding="utf-8")
    (agents_dir / "README.md").write_text("# readme\n", encoding="utf-8")

    mcp_server = tmp_path / "src" / "mcp" / "augur_mcp"
    mcp_server.mkdir(parents=True)
    (mcp_server / "server.py").write_text("agent tool", encoding="utf-8")

    with patch.object(mod, "get_project_root", return_value=tmp_path):
        checker = mod.PillarChecker()
        result = checker.check_agents_pillar("codex")

    assert result["status"] == "healthy"
    assert result["details"]["agent_registry_exists"] is True
    assert result["details"]["agent_count"] == 1

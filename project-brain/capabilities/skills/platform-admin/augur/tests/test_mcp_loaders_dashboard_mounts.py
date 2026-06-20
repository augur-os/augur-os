from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MCP_DIR = Path(__file__).resolve().parents[2] / "scripts" / "mcp"
PKG_NAME = "platform_admin_mcp_loaders_shared_vault_test"
if PKG_NAME not in sys.modules:
    pkg = types.ModuleType(PKG_NAME)
    pkg.__path__ = [str(MCP_DIR)]  # type: ignore[attr-defined]
    sys.modules[PKG_NAME] = pkg


def test_verify_dashboard_mounts_reads_shared_vault_skills(tmp_path, monkeypatch):
    """Dashboard mount verification should read project-brain skill metadata."""
    loaders = importlib.import_module(f"{PKG_NAME}._loaders")
    skill_md = tmp_path / "project-brain" / "capabilities" / "skills" / "demo" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(
        "---\n"
        "name: demo\n"
        "x-augur-hub: dev\n"
        "x-augur-config:\n"
        "  contributions:\n"
        "    pages:\n"
        "      - id: overview\n"
        "---\n"
        "# Demo\n",
        encoding="utf-8",
    )
    (tmp_path / "apps" / "dashboard" / "app" / "dev" / "demo" / "overview").mkdir(parents=True)
    monkeypatch.setattr(loaders, "get_project_root", lambda: tmp_path)

    result = loaders._verify_dashboard_mounts()

    assert result["success"] is True
    assert result["total_checked"] == 1
    assert result["issues_found"] == 0

"""Auto-generated importability test for tools_memory_profile."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_tools_memory_profile_importable():
    """Verify that tools_memory_profile can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_profile")
    assert mod is not None


def test_profile_payload_to_markdown_preserves_frontmatter_shape():
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_profile")
    content = mod._profile_payload_to_markdown({
        "role": "Engineer",
        "expertise": ["Python", "TypeScript"],
        "communicationStyle": "Direct",
        "successCriteria": ["Verified changes"],
        "contextGaps": ["Ask about deployment"],
    })

    assert content.startswith("---\n")
    assert "role: Engineer" in content
    assert "expertise:" in content
    assert "communicationStyle: Direct" in content
    assert "# Human API Profile" in content
    assert "- Verified changes" in content


def test_resolve_workspace_target_maps_profile_to_vault_wiki(monkeypatch, tmp_path):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_profile")
    vault_dir = tmp_path / "vault"
    memory_dir = vault_dir / "memory"

    monkeypatch.setattr("src.config.paths.get_vault_dir", lambda: vault_dir)
    monkeypatch.setattr("src.config.paths.get_memory_dir", lambda: memory_dir)

    resolved = mod._resolve_workspace_target(file_id="profile")

    assert resolved == str(vault_dir / "wiki" / "profile-human-api.md")


def test_resolve_workspace_target_maps_report_to_vault_wiki(monkeypatch, tmp_path):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_profile")
    vault_dir = tmp_path / "vault"
    memory_dir = vault_dir / "memory"

    monkeypatch.setattr("src.config.paths.get_vault_dir", lambda: vault_dir)
    monkeypatch.setattr("src.config.paths.get_memory_dir", lambda: memory_dir)

    resolved = mod._resolve_workspace_target(file_id="report")

    assert resolved == str(vault_dir / "wiki" / "profile-human-api.md")


def test_handle_profile_reads_vault_wiki_profile(monkeypatch, tmp_path):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_profile")
    vault_dir = tmp_path / "vault"
    profile_path = vault_dir / "wiki" / "profile-human-api.md"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(
        "---\nupdated: '2026-05-12T12:00:00+00:00'\n---\n"
        "# Memory Profile\n\n"
        "## Role\nFounder and lead builder\n\n"
        "## Expertise\n- Dashboard delivery\n- MCP workflows\n\n"
        "## Communication Style\nDirect, concise responses.\n\n"
        "## Success Criteria\n- Verified changes\n- Root-cause fixes\n\n"
        "## Context Gaps\n- Current priority\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("src.config.paths.get_vault_dir", lambda: vault_dir)

    payload = mod._handle_profile("read", None)

    assert payload["exists"] is True
    assert payload["role"] == "Founder and lead builder"
    assert payload["expertise"] == ["Dashboard delivery", "MCP workflows"]
    assert payload["communicationStyle"] == "Direct, concise responses."
    assert payload["successCriteria"] == ["Verified changes", "Root-cause fixes"]
    assert payload["contextGaps"] == ["Current priority"]
    assert payload["lastUpdated"] == "2026-05-12T12:00:00+00:00"


def test_handle_profile_writes_vault_wiki_profile(monkeypatch, tmp_path):
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_profile")
    vault_dir = tmp_path / "vault"
    monkeypatch.setattr("src.config.paths.get_vault_dir", lambda: vault_dir)

    result = mod._handle_profile(
        "write",
        mod._profile_payload_to_markdown({
            "role": "Engineer",
            "expertise": ["Python"],
            "communicationStyle": "Direct",
            "successCriteria": ["Tests pass"],
            "contextGaps": ["Deployment target"],
        }),
    )

    profile_path = vault_dir / "wiki" / "profile-human-api.md"
    assert result["success"] is True
    assert profile_path.exists()
    assert "## Role\nEngineer" in profile_path.read_text(encoding="utf-8")

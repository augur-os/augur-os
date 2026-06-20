from __future__ import annotations

from pathlib import Path

from src.lib.capabilities import discovery as discovery_module
from src.lib.capabilities.discovery import (
    discover_declared_skill_capabilities,
    discover_script_mcp_tool_capabilities,
)


def _write_skill(root: Path, name: str, frontmatter: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(frontmatter, encoding="utf-8")
    return skill_dir


def test_discovery_reads_new_x_augur_tools(tmp_path: Path) -> None:
    shared = tmp_path / "project-brain" / "capabilities" / "skills"
    private = tmp_path / "vault" / "skills"
    _write_skill(
        shared,
        "knowledge",
        "---\n"
        "name: knowledge\n"
        "description: Knowledge tools.\n"
        "x-augur:\n"
        "  tools:\n"
        "    - name: memory-search\n"
        "      surface: mcp\n"
        "    - name: knowledge-project-index-rebuild\n"
        "      surface: cli\n"
        "---\n",
    )

    records = discover_declared_skill_capabilities(
        tmp_path,
        skill_source_dirs=(shared, private),
    )
    by_id = {record.id: record for record in records}

    assert by_id["mcp-tool:memory-search"].metadata["primary_surface"] == "mcp"
    assert by_id["mcp-tool:knowledge-project-index-rebuild"].metadata["primary_surface"] == "cli"
    assert by_id["mcp-tool:memory-search"].owner_kind == "augur"


def test_discovery_marks_private_vault_tools_as_user_owned(tmp_path: Path) -> None:
    shared = tmp_path / "project-brain" / "capabilities" / "skills"
    vault = tmp_path / "vault"
    private = vault / "skills"
    (tmp_path / "project.yaml").write_text(
        f'name: Augur\npaths:\n  vault: "{vault.as_posix()}"\n',
        encoding="utf-8",
    )
    _write_skill(
        private,
        "file-manager",
        "---\n"
        "name: file-manager\n"
        "description: Private file routing.\n"
        "x-augur:\n"
        "  tools:\n"
        "    - name: get-pending\n"
        "      surface: mcp\n"
        "---\n",
    )

    records = discover_declared_skill_capabilities(
        tmp_path,
        skill_source_dirs=(shared, private),
    )

    assert len(records) == 1
    assert records[0].id == "mcp-tool:get-pending"
    assert records[0].owner_kind == "user"
    assert records[0].metadata["skill"] == "file-manager"


def test_deprecated_declared_mcp_tool_exposure_uses_policy_exports_without_direct_mcp(
    tmp_path: Path,
) -> None:
    shared = tmp_path / "project-brain" / "capabilities" / "skills"
    private = tmp_path / "vault" / "skills"
    _write_skill(
        shared,
        "knowledge",
        "---\n"
        "name: knowledge\n"
        "description: Knowledge tools.\n"
        "x-augur:\n"
        "  tools:\n"
        "    - name: knowledge-graph\n"
        "      surface: mcp\n"
        "---\n",
    )

    records = discover_declared_skill_capabilities(
        tmp_path,
        policy={
            "capabilities": {
                "mcp-tool:knowledge-graph": {
                    "classification_status": "deprecated",
                    "export_to": ["cli", "agents-md", "browse"],
                }
            }
        },
        skill_source_dirs=(shared, private),
    )

    assert len(records) == 1
    assert records[0].id == "mcp-tool:knowledge-graph"
    assert records[0].current_exposure == ("cli", "agents-md", "browse")


def test_discovery_marks_live_fallback_private_vault_tools_as_user_owned(
    tmp_path: Path,
    monkeypatch,
) -> None:
    stale_vault = tmp_path / "stale-vault"
    live_vault = tmp_path / "live-vault"
    shared = tmp_path / "project-brain" / "capabilities" / "skills"
    private = live_vault / "skills"
    (tmp_path / "project.yaml").write_text(
        f'name: Augur\npaths:\n  vault: "{stale_vault.as_posix()}"\n',
        encoding="utf-8",
    )
    _write_skill(
        private,
        "file-manager",
        "---\n"
        "name: file-manager\n"
        "description: Private file routing.\n"
        "x-augur:\n"
        "  tools:\n"
        "    - name: get-pending\n"
        "      surface: mcp\n"
        "---\n",
    )
    monkeypatch.setattr(discovery_module, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        discovery_module,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [shared, private],
    )
    monkeypatch.setattr(
        discovery_module,
        "get_vault_skills_dir",
        lambda: private,
        raising=False,
    )

    records = discover_declared_skill_capabilities()

    assert len(records) == 1
    assert records[0].id == "mcp-tool:get-pending"
    assert records[0].owner_kind == "user"


def test_script_mcp_discovery_marks_private_vault_tools_as_user_owned(
    tmp_path: Path,
    monkeypatch,
) -> None:
    shared = tmp_path / "project-brain" / "capabilities" / "skills"
    vault = tmp_path / "vault"
    private = vault / "skills"
    skill_dir = private / "private-tools"
    mcp_dir = skill_dir / "scripts" / "mcp"
    mcp_dir.mkdir(parents=True)
    (tmp_path / "project.yaml").write_text(
        f'name: Augur\npaths:\n  vault: "{vault.as_posix()}"\n',
        encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text(
        "---\nname: private-tools\ndescription: Private file routing.\n---\n",
        encoding="utf-8",
    )
    (mcp_dir / "pending.py").write_text(
        "def register_tools(mcp, interceptor, metrics):\n"
        "    @mcp.tool(name='get-pending')\n"
        "    async def get_pending():\n"
        "        return '{}'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        discovery_module,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [shared, private],
    )

    records = discover_script_mcp_tool_capabilities(tmp_path)

    assert len(records) == 1
    assert records[0].id == "mcp-tool:get-pending"
    assert records[0].owner_kind == "user"
    assert records[0].source_paths == ("vault/skills/private-tools/scripts/mcp/pending.py",)

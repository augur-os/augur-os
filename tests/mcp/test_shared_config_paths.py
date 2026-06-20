from __future__ import annotations


def test_shared_mcp_config_skill_data_uses_vault_first_mapping(tmp_path, monkeypatch):
    """MCP shared config must match the canonical vault data resolver."""
    from src.config import paths
    from src.lib import dir_alignment
    from src.mcp.augur_shared import config as mcp_config

    skills_dir = tmp_path / "skills"
    for name in ("career-ops", "file-manager", "websites"):
        (skills_dir / name).mkdir(parents=True)
    vault = tmp_path / "vault"
    vault.mkdir()

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: vault)
    paths.invalidate_project_cache()
    mcp_config.reset_config()

    assert mcp_config.get_skill_data_dir("career-ops") == vault / "career"
    assert mcp_config.get_skill_data_dir("file-manager") == vault / "config" / "file-manager"
    assert mcp_config.get_skill_data_dir("websites") == vault / "config" / "websites"

"""Auto-generated importability test for skill_paths."""

from __future__ import annotations

import sys
from pathlib import Path

import src.config.paths as paths

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_skill_paths_importable():
    """Verify that skill_paths can be imported without errors."""
    import src.lib.skill_paths

    assert src.lib.skill_paths is not None


def test_get_own_data_dir_respects_x_augur_data_dir(tmp_path, monkeypatch):
    """Renamed skills can keep a stable vault directory via x-augur-data-dir."""
    from src.lib import dir_alignment, skill_paths

    project_root = tmp_path / "repo"
    skills_dir = project_root / "project-brain" / "capabilities" / "skills"
    skill_root = skills_dir / "reading"
    script_path = skill_root / "scripts" / "mcp" / "__init__.py"
    skill_root.mkdir(parents=True)
    script_path.parent.mkdir(parents=True)
    script_path.write_text("# test\n", encoding="utf-8")
    (skill_root / "SKILL.md").write_text(
        "---\n" "name: reading\n" "x-augur-data-dir: reading-list\n" "---\n" "# Reading\n",
        encoding="utf-8",
    )

    vault = tmp_path / "vault"
    vault.mkdir()

    monkeypatch.chdir(project_root)
    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: vault)

    paths.invalidate_project_cache()
    skill_paths._deps_cache.clear()
    skill_paths._data_dir_cache.clear()

    assert skill_paths.get_own_data_dir(script_path) == vault / "reading-list"


def test_get_own_data_dir_respects_nested_x_augur_data_dir(tmp_path, monkeypatch):
    """Skill metadata can point to Obsidian-first nested vault locations."""
    from src.lib import dir_alignment, skill_paths

    project_root = tmp_path / "repo"
    skills_dir = project_root / "project-brain" / "capabilities" / "skills"
    skill_root = skills_dir / "career-ops"
    script_path = skill_root / "scripts" / "mcp" / "__init__.py"
    skill_root.mkdir(parents=True)
    script_path.parent.mkdir(parents=True)
    script_path.write_text("# test\n", encoding="utf-8")
    (skill_root / "SKILL.md").write_text(
        "---\n" "name: career-ops\n" "x-augur-data-dir: knowledge/notes/career\n" "---\n" "# Career Ops\n",
        encoding="utf-8",
    )

    vault = tmp_path / "vault"
    vault.mkdir()

    monkeypatch.chdir(project_root)
    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: vault)

    paths.invalidate_project_cache()
    skill_paths._deps_cache.clear()
    skill_paths._data_dir_cache.clear()

    assert skill_paths.get_own_data_dir(script_path) == vault / "knowledge" / "notes" / "career"


def test_get_own_data_dir_ignores_malformed_x_augur_data_dir(tmp_path, monkeypatch):
    """Malformed descriptive values should not become literal vault paths."""
    from src.lib import dir_alignment, skill_paths

    project_root = tmp_path / "repo"
    skills_dir = project_root / "project-brain" / "capabilities" / "skills"
    skill_root = skills_dir / "books"
    script_path = skill_root / "scripts" / "mcp" / "__init__.py"
    skill_root.mkdir(parents=True)
    script_path.parent.mkdir(parents=True)
    script_path.write_text("# test\n", encoding="utf-8")
    (skill_root / "SKILL.md").write_text(
        "---\n" "name: books\n" "x-augur-data-dir: books across all saved content\n" "---\n" "# Books\n",
        encoding="utf-8",
    )

    vault = tmp_path / "vault"
    vault.mkdir()

    monkeypatch.chdir(project_root)
    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: vault)

    paths.invalidate_project_cache()
    skill_paths._deps_cache.clear()
    skill_paths._data_dir_cache.clear()

    assert skill_paths.get_own_data_dir(script_path) == vault / "books"


def test_get_peer_data_dir_can_resolve_mapped_non_skill_data_dir(tmp_path, monkeypatch):
    """Declared peer data deps may point at mapped Obsidian-first data dirs."""
    from src.lib import dir_alignment, skill_paths

    project_root = tmp_path / "repo"
    skills_dir = project_root / "project-brain" / "capabilities" / "skills"
    skill_root = skills_dir / "books"
    script_path = skill_root / "scripts" / "mcp" / "__init__.py"
    skill_root.mkdir(parents=True)
    script_path.parent.mkdir(parents=True)
    script_path.write_text("# test\n", encoding="utf-8")
    (skill_root / "SKILL.md").write_text(
        "---\n" "name: books\n" "x-augur-data-deps:\n" "  - reading-list\n" "---\n" "# Books\n",
        encoding="utf-8",
    )

    vault = tmp_path / "vault"
    vault.mkdir()

    monkeypatch.chdir(project_root)
    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: vault)

    paths.invalidate_project_cache()
    skill_paths._deps_cache.clear()
    skill_paths._data_dir_cache.clear()

    assert skill_paths.get_peer_data_dir(script_path, "reading-list") == vault / "books"


def test_get_peer_data_dir_resolves_legacy_aliases_to_moved_roots(tmp_path, monkeypatch):
    """Legacy peer names should resolve to mapped roots, not new top-level dirs."""
    from src.lib import dir_alignment, skill_paths

    project_root = tmp_path / "repo"
    skills_dir = project_root / "project-brain" / "capabilities" / "skills"
    skill_root = skills_dir / "daemon"
    script_path = skill_root / "scripts" / "check_expirations.py"
    skill_root.mkdir(parents=True)
    script_path.parent.mkdir(parents=True)
    script_path.write_text("# test\n", encoding="utf-8")
    (skill_root / "SKILL.md").write_text(
        "---\n" "name: daemon\n" "x-augur-data-deps:\n" "  - venture\n" "  - channels\n" "---\n" "# Daemon\n",
        encoding="utf-8",
    )

    vault = tmp_path / "vault"
    vault.mkdir()

    monkeypatch.chdir(project_root)
    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: vault)

    paths.invalidate_project_cache()
    skill_paths._deps_cache.clear()
    skill_paths._data_dir_cache.clear()

    assert skill_paths.get_peer_data_dir(script_path, "venture") == vault / "venture"
    assert skill_paths.get_peer_data_dir(script_path, "channels") == vault / "config" / "attention"

"""Tests for src.config.paths skill data path resolution."""

import json
from pathlib import Path

import pytest

import src.config.paths as paths


@pytest.fixture(autouse=True)
def _clear_skill_cache():
    from src.lib.dir_alignment import get_skill_names

    paths.invalidate_project_cache()
    get_skill_names.cache_clear()
    yield
    paths.invalidate_project_cache()
    get_skill_names.cache_clear()


@pytest.fixture
def _skill_env(tmp_path, monkeypatch):
    """Set up a minimal skills + vault environment for path resolution tests."""
    from src.lib import dir_alignment

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    for name in ("developer", "career", "knowledge"):
        (skills_dir / name).mkdir()
    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [skills_dir])
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: vault)
    paths.invalidate_project_cache()
    return vault


def test_get_skill_data_dir_returns_vault_path(_skill_env):
    """get_skill_data_dir() should delegate to get_skill_vault_dir() per ADR-270."""
    result = paths.get_skill_data_dir("developer")
    expected = paths.get_skill_vault_dir("developer")
    assert result == expected


def test_get_skill_data_dir_includes_skill_name(_skill_env):
    """Result path should end with the skill name."""
    result = paths.get_skill_data_dir("developer")
    assert result.name == "developer"


def test_get_skill_data_dir_apps_bundle(_skill_env):
    """Verify career skill data resolves consistently."""
    result = paths.get_skill_data_dir("career")
    expected = paths.get_skill_vault_dir("career")
    assert result == expected
    assert result.name == "career"


def test_get_skill_data_dir_services_bundle(_skill_env):
    """Verify knowledge skill data resolves consistently."""
    result = paths.get_skill_data_dir("knowledge")
    expected = paths.get_skill_vault_dir("knowledge")
    assert result == expected
    assert result.name == "knowledge"


def test_get_skill_data_dir_reserved_name_allowed_via_dotfile(tmp_path, monkeypatch):
    """Reserved vault names listed in .augur-reserved are allowed, not rejected."""
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [tmp_path / "empty_skills"])
    (tmp_path / "empty_skills").mkdir(exist_ok=True)
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".augur-reserved").write_text("config\ndev\nmemory\n")
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: vault)
    paths.invalidate_project_cache()
    result = paths.get_skill_data_dir("config")
    assert result == vault / "config"


def test_get_skill_vault_dir_rejects_unknown_name(tmp_path, monkeypatch):
    """get_skill_vault_dir() raises ValueError for names not in skills or .augur-reserved."""
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [tmp_path / "empty_skills"])
    (tmp_path / "empty_skills").mkdir(exist_ok=True)
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: tmp_path / "vault")
    (tmp_path / "vault").mkdir()
    paths.invalidate_project_cache()
    with pytest.raises(ValueError, match="not a recognized skill name"):
        paths.get_skill_vault_dir("nonexistent-skill")


def test_get_skill_vault_dir_allows_reserved_name_via_dotfile(tmp_path, monkeypatch):
    """get_skill_vault_dir() allows names listed in .augur-reserved."""
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [tmp_path / "empty_skills"])
    (tmp_path / "empty_skills").mkdir(exist_ok=True)
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".augur-reserved").write_text("config\ndev\nmemory\n")
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: vault)
    paths.invalidate_project_cache()
    result = paths.get_skill_vault_dir("config")
    assert result == vault / "config"


def test_get_vault_config_dir_returns_vault_config(_skill_env):
    assert paths.get_vault_config_dir() == _skill_env / "config"


def test_get_skill_vault_dirs_includes_existing_config_fallback(_skill_env):
    (_skill_env / "config" / "developer").mkdir(parents=True)

    result = paths.get_skill_vault_dirs("developer")

    assert result == [
        _skill_env / "developer",
        _skill_env / "config" / "developer",
    ]


def test_get_skill_vault_dir_uses_vault_first_mapping(_skill_env):
    """Migrated skill data resolves to domain-first locations (no knowledge/notes prefix)."""
    result = paths.get_skill_vault_dir("career")
    assert result == _skill_env / "career"


def test_get_skill_vault_dirs_includes_existing_legacy_fallback(_skill_env):
    """Existing flat roots remain readable as a fallback during migration cleanup."""
    legacy = _skill_env / "career"
    legacy.mkdir()

    result = paths.get_skill_vault_dirs("career")

    # The domain-first primary (vault/career) and the legacy flat root are now
    # the same directory, so dedup leaves exactly one entry.
    assert result == [_skill_env / "career"]


def test_legacy_aliases_resolve_to_vault_first_locations(_skill_env):
    """Skill vault relative dirs use domain-first paths (no knowledge/notes prefix)."""
    assert paths.get_skill_vault_relative_dir("venture") == Path("venture")
    assert paths.get_skill_vault_relative_dir("channels") == Path("config/attention")


def test_resolved_migration_aliases_do_not_recreate_vault_roots(_skill_env):
    """Migration roots resolve to domain-first locations (no knowledge/notes prefix)."""
    from src.lib import dir_alignment

    skills_dir = dir_alignment._get_all_client_skill_dirs()[0]
    for skill_name in ("apple", "content"):
        (skills_dir / skill_name).mkdir()
    (_skill_env / ".augur-reserved").write_text("growth\nremote-access\n", encoding="utf-8")

    assert paths.get_skill_data_dir("apple") == _skill_env / "lifestyle" / "apple"
    assert paths.get_skill_data_dir("content") == _skill_env / "venture" / "content"
    assert paths.get_skill_data_dir("growth") == _skill_env / "career" / "growth"
    assert paths.get_skill_data_dir("remote-access") == _skill_env / "config" / "remote-access"


def test_updater_data_resolves_to_config_root(_skill_env):
    """Updater config/data should not recreate a top-level vault updater root."""
    from src.lib import dir_alignment

    skills_dir = dir_alignment._get_all_client_skill_dirs()[0]
    (skills_dir / "updater").mkdir()

    assert paths.get_skill_data_dir("updater") == _skill_env / "config" / "updater"


def test_get_skill_documents_dir_rejects_unknown_name(tmp_path, monkeypatch):
    """get_skill_documents_dir() raises ValueError for unknown names."""
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [tmp_path / "empty_skills"])
    (tmp_path / "empty_skills").mkdir(exist_ok=True)
    monkeypatch.setattr(paths, "_documents_home_dir", lambda: tmp_path / "docs")
    (tmp_path / "docs").mkdir()
    paths.invalidate_project_cache()
    with pytest.raises(ValueError, match="not a recognized skill name"):
        paths.get_skill_documents_dir("nonexistent-skill")


def test_get_skill_documents_dir_allows_reserved_name_via_dotfile(tmp_path, monkeypatch):
    """get_skill_documents_dir() allows names listed in .augur-reserved."""
    from src.lib import dir_alignment

    monkeypatch.setattr(dir_alignment, "_get_all_client_skill_dirs", lambda: [tmp_path / "empty_skills"])
    (tmp_path / "empty_skills").mkdir(exist_ok=True)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / ".augur-reserved").write_text("dev\n")
    monkeypatch.setattr(paths, "_documents_home_dir", lambda: docs)
    paths.invalidate_project_cache()
    result = paths.get_skill_documents_dir("dev")
    assert result == docs / "dev"


def test_get_all_client_skill_dirs_uses_explicit_project_root(tmp_path, monkeypatch):
    """Explicit project_root should drive skill discovery for worktrees/tests."""
    project_root = (tmp_path / "repo").resolve()
    skills_dir = project_root / "project-brain" / "capabilities" / "skills"
    root_skills = project_root.joinpath("skills")
    skills_dir.mkdir(parents=True)
    root_skills.mkdir(parents=True)
    monkeypatch.setattr(paths, "get_claude_plugin_skill_dirs", lambda: [])

    result = paths.get_all_client_skill_dirs(project_root)

    assert result == [skills_dir]
    assert root_skills not in result


def test_get_all_client_skill_dirs_includes_supported_installed_clients_for_project_root(tmp_path, monkeypatch):
    """The project inventory should include the configured vault and project-local client skill dirs."""
    project_root = (tmp_path / "repo").resolve()
    project_skills = project_root / "project-brain" / "capabilities" / "skills"
    root_skills = project_root.joinpath("skills")
    vault = tmp_path / "vault"
    vault_skills = vault / "capabilities" / "skills"
    for skills_dir in (
        project_skills,
        root_skills,
        vault_skills,
        project_root / ".claude" / "skills",
        project_root / ".codex" / "skills",
        project_root / ".gemini" / "skills",
    ):
        skills_dir.mkdir(parents=True)

    # The vault is resolved through project.yaml's paths.vault (capabilities/skills
    # layout), not get_vault_skills_dir, so isolate via the explicit-root config.
    # Keep the explicit project_root distinct from the live repo root (do NOT
    # monkeypatch get_project_root to it) so the explicit-root resolution path runs
    # instead of the live layered stack / installed client dirs, which would leak the
    # developer's real vault and home client skill dirs. An empty tmp brain registry
    # guards the layered stack as well.
    (project_root / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {vault}\n",
        encoding="utf-8",
    )
    registry = tmp_path / "brains.yaml"
    registry.write_text("brains: {}\n", encoding="utf-8")
    monkeypatch.setattr(paths, "get_brain_registry_path", lambda: registry)
    monkeypatch.setattr(paths, "get_claude_plugin_skill_dirs", lambda: [])

    result = paths.get_all_client_skill_dirs(project_root)

    assert result == [
        project_skills,
        vault_skills,
        project_root / ".claude" / "skills",
        project_root / ".codex" / "skills",
        project_root / ".gemini" / "skills",
    ]
    assert root_skills not in result


def test_get_claude_plugin_skill_dirs_uses_installed_plugin_registry(tmp_path, monkeypatch):
    project_root = (tmp_path / "repo").resolve()
    claude_home = tmp_path / "home" / ".claude"
    plugins_dir = claude_home / "plugins"
    cache_dir = plugins_dir / "cache"
    enabled_plugin = cache_dir / "ui-ux-pro-max-skill" / "ui-ux-pro-max" / "2.5.0"
    disabled_plugin = cache_dir / "claude-plugins-official" / "superpowers" / "5.1.0"
    inactive_official_plugin = cache_dir / "claude-plugins-official" / "frontend-design" / "unknown"
    enabled_skills = enabled_plugin / ".claude" / "skills"
    disabled_skills = disabled_plugin / "skills"
    inactive_official_skills = inactive_official_plugin / "skills"
    (enabled_skills / "ui-ux-pro-max").mkdir(parents=True)
    (disabled_skills / "systematic-debugging").mkdir(parents=True)
    (inactive_official_skills / "frontend-design").mkdir(parents=True)

    (plugins_dir / "installed_plugins.json").write_text(
        json.dumps(
            {
                "plugins": {
                    "ui-ux-pro-max@ui-ux-pro-max-skill": [
                        {
                            "projectPath": str(project_root),
                            "installPath": str(enabled_plugin),
                        }
                    ],
                    "superpowers@claude-plugins-official": [
                        {
                            "projectPath": str(project_root),
                            "installPath": str(disabled_plugin),
                        }
                    ],
                    "frontend-design@claude-plugins-official": [
                        {
                            "projectPath": str(project_root),
                            "installPath": str(inactive_official_plugin),
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    (claude_home / "settings.json").write_text(
        json.dumps({"enabledPlugins": {"superpowers@claude-plugins-official": False}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(paths, "_get_claude_plugin_cache_dir", lambda: cache_dir)
    monkeypatch.setattr(paths, "get_project_root", lambda: project_root)

    assert paths.get_claude_plugin_skill_dirs() == [enabled_skills]


def test_get_claude_plugin_skill_dirs_falls_back_to_highest_cache_version(tmp_path, monkeypatch):
    cache_dir = tmp_path / "home" / ".claude" / "plugins" / "cache"
    old_skills = cache_dir / "vendor" / "design-pack" / "1.0.0" / "skills"
    new_skills = cache_dir / "vendor" / "design-pack" / "2.0.0" / ".claude" / "skills"
    old_skills.mkdir(parents=True)
    new_skills.mkdir(parents=True)

    monkeypatch.setattr(paths, "_get_claude_plugin_cache_dir", lambda: cache_dir)

    assert paths.get_claude_plugin_skill_dirs() == [new_skills]


def test_vault_user_surface_helpers_share_vault_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: tmp_path / "vault")
    (tmp_path / "vault").mkdir()
    paths.invalidate_project_cache()

    assert paths.get_vault_drafts_dir() == tmp_path / "vault" / "drafts"
    assert paths.get_vault_staging_dir() == tmp_path / "vault" / "drafts" / "staging"
    assert paths.get_vault_skills_dir() == tmp_path / "vault" / "capabilities" / "skills"


def test_vault_first_helpers_share_vault_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: tmp_path / "vault")
    (tmp_path / "vault").mkdir()
    paths.invalidate_project_cache()

    assert paths.get_vault_drafts_dir() == tmp_path / "vault" / "drafts"
    assert paths.get_vault_staging_dir() == tmp_path / "vault" / "drafts" / "staging"
    assert paths.get_vault_archive_dir() == tmp_path / "vault" / "archive"
    assert paths.get_vault_notes_dir() == tmp_path / "vault" / "knowledge" / "notes"
    assert paths.get_vault_config_dir() == tmp_path / "vault" / "config"
    assert paths.get_vault_skills_dir() == tmp_path / "vault" / "capabilities" / "skills"
    assert paths.get_vault_config_dir() == tmp_path / "vault" / "config"


def test_vault_prompts_dir_resolves_under_vault_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: tmp_path / "vault")
    (tmp_path / "vault").mkdir()
    paths.invalidate_project_cache()

    assert paths.get_vault_prompts_dir() == tmp_path / "vault" / "prompts"


def test_get_skill_vault_dirs_includes_config_candidate(_skill_env):
    (_skill_env / "config" / "developer").mkdir(parents=True)

    result = paths.get_skill_vault_dirs("developer")

    assert result == [
        _skill_env / "developer",
        _skill_env / "config" / "developer",
    ]


def test_get_skills_dir_returns_project_brain_skills_after_physical_migration(tmp_path, monkeypatch):
    project_root = tmp_path / "repo"
    project_root.mkdir()
    monkeypatch.setattr(paths, "get_project_root", lambda: project_root)
    paths.invalidate_project_cache()

    assert paths.get_skills_dir() == project_root / "project-brain" / "capabilities" / "skills"


def test_private_vault_aliases_keep_existing_vault_contract(tmp_path, monkeypatch):
    private_vault = tmp_path / "private-vault"
    private_vault.mkdir()

    monkeypatch.setattr(paths, "_vault_home_dir", lambda: private_vault)
    paths.invalidate_project_cache()

    assert paths.get_private_vault_dir() == private_vault
    assert paths.get_private_vault_skills_dir() == private_vault / "capabilities" / "skills"
    assert paths.get_private_wiki_dir() == private_vault / "knowledge" / "wiki"


def test_get_vault_source_roots_returns_project_then_private(tmp_path, monkeypatch):
    project_root = tmp_path / "repo"
    private_vault = tmp_path / "private-vault"
    project_root.mkdir()
    private_vault.mkdir()

    monkeypatch.setattr(paths, "get_project_root", lambda: project_root)
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: private_vault)
    paths.invalidate_project_cache()

    assert paths.get_vault_source_roots() == [
        ("project", project_root / "project-brain"),
        ("private", private_vault),
    ]


def test_get_managed_skill_source_dirs_includes_project_brain_and_live_vault(monkeypatch, tmp_path):
    project_root = tmp_path / "repo"
    project_skills = project_root / "project-brain" / "capabilities" / "skills"
    project_skills.mkdir(parents=True)
    vault = tmp_path / "vault"
    vault_skills = vault / "capabilities" / "skills"
    vault_skills.mkdir(parents=True)

    # The vault is resolved via get_configured_vault_skills_dir(root) (project.yaml
    # paths.vault, capabilities/skills layout), not get_vault_skills_dir. Point the
    # brain registry at an empty tmp file so the layered brain stack does not leak
    # the developer's real personal vault into this tmp-path assertion.
    (project_root / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {vault}\n",
        encoding="utf-8",
    )
    registry = tmp_path / "brains.yaml"
    registry.write_text("brains: {}\n", encoding="utf-8")
    monkeypatch.setattr(paths, "get_brain_registry_path", lambda: registry)
    monkeypatch.setattr(paths, "get_project_root", lambda: project_root)
    monkeypatch.setattr(paths, "get_vault_skills_dir", lambda: vault_skills)

    result = paths.get_managed_skill_source_dirs()

    assert result == [project_skills, vault_skills]


def test_managed_skill_source_dirs_omits_repo_root_skills(tmp_path, monkeypatch):
    project_root = tmp_path / "repo"
    project_skills = project_root / "project-brain" / "capabilities" / "skills"
    private_vault = tmp_path / "private-vault"
    private_skills = private_vault / "capabilities" / "skills"
    root_skills = project_root.joinpath("skills")
    for path in (project_skills, private_skills, root_skills):
        path.mkdir(parents=True)

    # The vault resolves through get_configured_vault_skills_dir(root) (capabilities/skills),
    # not get_vault_skills_dir; an empty tmp brain registry keeps the layered stack from
    # leaking the developer's real personal vault.
    (project_root / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {private_vault}\n",
        encoding="utf-8",
    )
    registry = tmp_path / "brains.yaml"
    registry.write_text("brains: {}\n", encoding="utf-8")
    monkeypatch.setattr(paths, "get_brain_registry_path", lambda: registry)
    monkeypatch.setattr(paths, "get_project_root", lambda: project_root)
    monkeypatch.setattr(paths, "get_vault_skills_dir", lambda: private_skills)
    paths.invalidate_project_cache()

    assert paths.get_managed_skill_source_dirs(project_root) == [project_skills, private_skills]


def test_get_managed_skill_source_dirs_for_explicit_temp_root_stays_project_local(monkeypatch, tmp_path):
    explicit_root = tmp_path / "other-root"
    project_skills = explicit_root / "project-brain" / "capabilities" / "skills"
    project_skills.mkdir(parents=True)
    monkeypatch.setattr(paths, "get_project_root", lambda: tmp_path / "live-root")
    monkeypatch.setattr(paths, "get_vault_skills_dir", lambda: tmp_path / "vault" / "skills")

    result = paths.get_managed_skill_source_dirs(explicit_root)

    assert result == [project_skills]


def test_get_skill_root_resolves_vault_skill_when_repo_skill_absent(monkeypatch, tmp_path):
    project_root = tmp_path / "repo"
    (project_root / "project-brain" / "capabilities" / "skills").mkdir(parents=True)
    vault = tmp_path / "vault"
    vault_skills = vault / "capabilities" / "skills"
    vault_skill = vault_skills / "apple"
    vault_skill.mkdir(parents=True)
    (vault_skill / "SKILL.md").write_text("---\nname: apple\n---\n", encoding="utf-8")

    # find_skill_root() walks get_managed_skill_source_dirs(), which resolves the vault
    # via get_configured_vault_skills_dir (capabilities/skills) and the layered brain
    # stack. Supply project.yaml and an empty registry so the developer's real vault
    # does not leak in.
    (project_root / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {vault}\n",
        encoding="utf-8",
    )
    registry = tmp_path / "brains.yaml"
    registry.write_text("brains: {}\n", encoding="utf-8")
    monkeypatch.setattr(paths, "get_brain_registry_path", lambda: registry)
    monkeypatch.setattr(paths, "get_project_root", lambda: project_root)
    monkeypatch.setattr(paths, "get_vault_skills_dir", lambda: vault_skills)

    assert paths.get_skill_root("apple") == vault_skill


def test_get_skill_root_prefers_project_brain_skill_over_vault_skill(monkeypatch, tmp_path):
    project_root = tmp_path / "repo"
    project_skill = project_root / "project-brain" / "capabilities" / "skills" / "apple"
    project_skill.mkdir(parents=True)
    vault_skill = tmp_path / "vault" / "skills" / "apple"
    vault_skill.mkdir(parents=True)

    monkeypatch.setattr(paths, "get_project_root", lambda: project_root)
    monkeypatch.setattr(paths, "get_vault_skills_dir", lambda: tmp_path / "vault" / "skills")

    assert paths.get_skill_root("apple") == project_skill


def test_get_adaptive_loop_skill_dirs_includes_configured_vault_skills(tmp_path):
    project_root = tmp_path / "repo"
    project_skills = project_root / "project-brain" / "capabilities" / "skills"
    vault_skills = tmp_path / "vault" / "capabilities" / "skills"
    project_skills.mkdir(parents=True)
    vault_skills.mkdir(parents=True)
    (project_root / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {tmp_path / 'vault'}\n",
        encoding="utf-8",
    )

    result = paths.get_adaptive_loop_skill_dirs(project_root)

    assert result == [project_skills, vault_skills]


def test_get_adaptive_loop_skill_dirs_excludes_generated_client_exports(tmp_path):
    project_root = tmp_path / "repo"
    project_skills = project_root / "project-brain" / "capabilities" / "skills"
    vault_skills = tmp_path / "vault" / "capabilities" / "skills"
    generated_dirs = [
        project_root / ".gemini" / "skills",
        project_root / ".opencode" / "skills",
        project_root / ".codex" / "skills",
    ]
    for skills_dir in [project_skills, vault_skills, *generated_dirs]:
        skills_dir.mkdir(parents=True)
    (project_root / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {tmp_path / 'vault'}\n",
        encoding="utf-8",
    )

    result = paths.get_adaptive_loop_skill_dirs(project_root)

    assert result == [project_skills, vault_skills]
    assert not any(".gemini" in str(path) for path in result)
    assert not any(".opencode" in str(path) for path in result)
    assert not any(".codex" in str(path) for path in result)


def test_get_adaptive_loop_skill_dirs_explicit_root_ignores_augur_vault_env(
    tmp_path,
    monkeypatch,
):
    project_root = tmp_path / "repo"
    project_skills = project_root / "project-brain" / "capabilities" / "skills"
    project_vault_skills = tmp_path / "project-vault" / "capabilities" / "skills"
    env_vault_skills = tmp_path / "env-vault" / "capabilities" / "skills"
    project_skills.mkdir(parents=True)
    project_vault_skills.mkdir(parents=True)
    env_vault_skills.mkdir(parents=True)
    (project_root / "project.yaml").write_text(
        f"name: TestAugur\npaths:\n  vault: {tmp_path / 'project-vault'}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path / "env-vault"))

    result = paths.get_adaptive_loop_skill_dirs(project_root)

    assert result == [project_skills, project_vault_skills]
    assert env_vault_skills not in result


def test_get_client_runtime_dir_claude_desktop_windows_uses_appdata(monkeypatch):
    """Claude Desktop runtime dir should use APPDATA on Windows."""
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\tester\AppData\Roaming")

    result = paths.get_client_runtime_dir("claude-desktop")

    assert result == Path(r"C:\Users\tester\AppData\Roaming") / "Claude"


def test_resolve_wiki_dir_defaults_to_personal(monkeypatch):
    """No env var -> personal vault wiki (unchanged default)."""
    monkeypatch.delenv("AUGUR_WIKI_TARGET_BRAIN", raising=False)
    assert paths.resolve_wiki_dir() == paths.get_wiki_dir()


def test_resolve_wiki_dir_targets_project_brain(monkeypatch):
    """AUGUR_WIKI_TARGET_BRAIN=project -> project-brain wiki."""
    monkeypatch.setenv("AUGUR_WIKI_TARGET_BRAIN", "project")
    assert paths.resolve_wiki_dir() == paths.get_project_brain_wiki_dir()


def test_resolve_wiki_dir_is_case_and_space_insensitive(monkeypatch):
    monkeypatch.setenv("AUGUR_WIKI_TARGET_BRAIN", "  Project ")
    assert paths.resolve_wiki_dir() == paths.get_project_brain_wiki_dir()


def test_resolve_wiki_dir_ignores_unknown_value(monkeypatch):
    """Unknown value -> safe default (personal)."""
    monkeypatch.setenv("AUGUR_WIKI_TARGET_BRAIN", "bogus")
    assert paths.resolve_wiki_dir() == paths.get_wiki_dir()


def test_get_documents_machine_dir(monkeypatch, tmp_path):
    """get_documents_machine_dir(name) returns <documents_dir>/_augur/<name>."""
    monkeypatch.setattr(paths, "_documents_home_dir", lambda: tmp_path)
    paths.invalidate_project_cache()
    for name in ("evals", "reports", "dev", "test-security", "consulting-template"):
        result = paths.get_documents_machine_dir(name)
        assert result == tmp_path / "_augur" / name
    paths.invalidate_project_cache()

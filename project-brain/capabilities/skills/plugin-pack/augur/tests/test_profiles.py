# skills/plugin-pack/augur/tests/test_profiles.py
"""Tests for plugin-pack filter profiles."""
import sys
from pathlib import Path

REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SHARED_VAULT_ROOT = REPO_ROOT / "project-brain"
PLUGIN_PACK_ROOT = SHARED_VAULT_ROOT / "capabilities" / "skills" / "plugin-pack"
for _path in (REPO_ROOT, SHARED_VAULT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

SCRIPTS_DIR = PLUGIN_PACK_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_cowork_profile_has_expected_groups():
    from profiles import COWORK_PROFILE
    assert COWORK_PROFILE.groups == frozenset({"brain"})


def test_codex_profile_packages_full_toolset():
    from profiles import CODEX_PROFILE
    assert CODEX_PROFILE.groups == frozenset(
        {"brain", "augur_core", "augur_autoloops", "augur_admin"}
    )


def test_codex_profile_allows_dev_prefix():
    from profiles import CODEX_PROFILE
    assert "dev-" not in CODEX_PROFILE.excluded_prefixes


def test_cowork_profile_excludes_dev_prefix():
    from profiles import COWORK_PROFILE
    assert "dev-" in COWORK_PROFILE.excluded_prefixes


def test_packaged_profiles_exclude_plugin_pack():
    from profiles import COWORK_PROFILE, CODEX_PROFILE, COPILOT_PROFILE, GEMINI_PROFILE

    packaged_profiles = (COWORK_PROFILE, CODEX_PROFILE, GEMINI_PROFILE, COPILOT_PROFILE)
    for profile in packaged_profiles:
        assert "plugin-pack" in profile.excluded_skills


def test_cowork_profile_ships_ask_and_keep_commands():
    # Desktop has no repo checkout; ask + keep hydrate to full command docs so
    # regular chats get the bare-/keep Session Reconcile flow (spec 2026-06-11).
    from profiles import COWORK_PROFILE

    assert sorted(COWORK_PROFILE.commands) == ["ask", "keep"]


def test_native_client_profiles_keep_canonical_commands():
    from profiles import CODEX_PROFILE, GEMINI_PROFILE

    packaged_profiles = (CODEX_PROFILE, GEMINI_PROFILE)
    for profile in packaged_profiles:
        assert set(profile.commands) == {
            "ask",
            "discover",
            "keep",
            "project",
            "routines",
            "skillify",
        }
        assert profile.commands["project"]["description"] == "Current-folder project router"
        assert "current folder" in profile.commands["project"]["body"]
        assert "adr" not in profile.commands
        assert "dev" not in profile.commands
        assert "sweep" not in profile.commands
        assert "dev-build" not in profile.commands
        assert "save" not in profile.commands
        assert "wiki" not in profile.commands


def test_copilot_profile_keeps_prompt_commands():
    from profiles import COPILOT_PROFILE

    assert set(COPILOT_PROFILE.commands) == {"ask", "wiki"}
    assert "dev-build" not in COPILOT_PROFILE.commands
    assert "save" not in COPILOT_PROFILE.commands


def test_get_profile_by_name():
    from profiles import get_profile
    assert get_profile("cowork").name == "cowork"
    assert get_profile("codex").name == "codex"
    assert get_profile("gemini").name == "gemini"
    assert get_profile("copilot").name == "copilot"


def test_gemini_profile_matches_codex_initial_scope():
    from profiles import GEMINI_PROFILE, CODEX_PROFILE
    assert GEMINI_PROFILE.groups == CODEX_PROFILE.groups
    assert GEMINI_PROFILE.excluded_prefixes == CODEX_PROFILE.excluded_prefixes
    assert GEMINI_PROFILE.excluded_skills == CODEX_PROFILE.excluded_skills
    assert GEMINI_PROFILE.commands == CODEX_PROFILE.commands


def test_copilot_profile_matches_codex_initial_skill_scope():
    from profiles import COPILOT_PROFILE, CODEX_PROFILE
    assert COPILOT_PROFILE.groups == CODEX_PROFILE.groups
    assert COPILOT_PROFILE.excluded_prefixes == CODEX_PROFILE.excluded_prefixes
    assert COPILOT_PROFILE.excluded_skills == CODEX_PROFILE.excluded_skills


def test_get_profile_unknown_raises():
    from profiles import get_profile
    import pytest
    with pytest.raises(ValueError, match="Unknown target"):
        get_profile("unknown-target")

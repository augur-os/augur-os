from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

scripts_dir = Path(__file__).resolve().parents[2]
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))


def _source(tmp_path: Path, name: str) -> tuple[str, Path, str, str, str, bool]:
    skill_dir = tmp_path / "sources" / name
    skill_dir.mkdir(parents=True)
    raw = f"---\nname: {name}\ndescription: {name}\n---\n# {name}\n"
    (skill_dir / "SKILL.md").write_text(raw, encoding="utf-8")
    return (name, skill_dir, raw, f"# {name}", name, False)


def test_skill_target_dir_respects_gate_and_tier(tmp_path: Path) -> None:
    from sync_agents import skill_sync

    client_dirs = {
        "claude-local": tmp_path / "repo" / ".claude" / "skills",
        "claude-global": tmp_path / "home" / ".claude" / "skills",
    }
    home_skills = {"user-only"}
    repo_skills = {"proj-only"}

    with patch("src.lib.brain_home_sync.home_sync_enabled", return_value=True):
        assert (
            skill_sync._skill_target_dir(
                "user-only", "claude", client_dirs, home_skills, repo_skills
            )
            == client_dirs["claude-global"]
        )
        assert (
            skill_sync._skill_target_dir(
                "proj-only", "claude", client_dirs, home_skills, repo_skills
            )
            == client_dirs["claude-local"]
        )

    with patch("src.lib.brain_home_sync.home_sync_enabled", return_value=False):
        assert (
            skill_sync._skill_target_dir(
                "user-only", "claude", client_dirs, home_skills, repo_skills
            )
            == client_dirs["claude-local"]
        )


def test_skill_exports_project_all_sources_to_enabled_local_clients_by_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from sync_agents import skill_sync

    sources = [_source(tmp_path, "proj-only"), _source(tmp_path, "user-only")]
    claude_local = tmp_path / "repo" / ".claude" / "skills"
    claude_global = tmp_path / "home" / ".claude" / "skills"
    codex_local = tmp_path / "repo" / ".codex" / "skills"
    codex_global = tmp_path / "home" / ".codex" / "skills"
    gemini_local = tmp_path / "repo" / ".gemini" / "skills"
    gemini_global = tmp_path / "home" / ".gemini" / "skills"
    monkeypatch.setattr(
        skill_sync,
        "filter_named_sources",
        lambda _kind, source_list, *, target, existing_names: list(source_list),
    )

    with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
        patch(
            "sync_agents.skill_sync._resolve_client_skill_dirs",
            return_value=[
                ("claude-local", claude_local, True),
                ("claude-global", claude_global, True),
                ("codex-local", codex_local, True),
                ("codex-global", codex_global, True),
                ("gemini-local", gemini_local, True),
                ("gemini-global", gemini_global, True),
            ],
        ), \
        patch("sync_agents.skill_sync._load_skill_scopes", return_value={}), \
        patch("src.lib.brain_home_sync.home_sync_enabled", return_value=False), \
        patch(
            "sync_agents.skill_sync.get_codex_prompt_dir",
            side_effect=[tmp_path / "legacy-prompts-project", tmp_path / "legacy-prompts-global"],
        ), \
        patch(
            "sync_agents.skill_sync.get_codex_native_skills_dir",
            side_effect=[tmp_path / "legacy-native-project", tmp_path / "legacy-native-global"],
        ):
        written = skill_sync._sync_skill_exports(
            [
                SimpleNamespace(adapter_name="claude_code"),
                SimpleNamespace(adapter_name="codex"),
                SimpleNamespace(adapter_name="gemini"),
            ],
            sources,
        )

    assert written == 6
    for local_dir in (claude_local, codex_local, gemini_local):
        assert (local_dir / "proj-only" / "SKILL.md").is_file()
        assert (local_dir / "user-only" / "SKILL.md").is_file()
    for global_dir in (claude_global, codex_global, gemini_global):
        assert not global_dir.exists()

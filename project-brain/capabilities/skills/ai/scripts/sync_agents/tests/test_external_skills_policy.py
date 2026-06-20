from __future__ import annotations

from pathlib import Path

from sync_agents import external_skills
from sync_agents import skill_sync


def _write_skill(skill_dir: Path, name: str) -> None:
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name}\n---\n# {name}\n",
        encoding="utf-8",
    )


def test_gemini_external_skill_distribution_removes_policy_denied_exports(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "vendor" / "external"
    target = tmp_path / "project" / ".gemini" / "skills"
    _write_skill(source / "skills" / "defuddle", "defuddle")
    _write_skill(source / "skills" / "obsidian-cli", "obsidian-cli")
    _write_skill(target / "defuddle", "defuddle")

    bundle = external_skills.ExternalSkillBundle(
        id="external",
        source=source,
        upstream="",
        pinned_sha="",
        skills=["defuddle", "obsidian-cli"],
        targets={"gemini": "convert_and_copy"},
    )
    monkeypatch.setattr(
        external_skills,
        "_allowed_external_skill_names",
        lambda _names, _adapter_name, _existing_names: {"obsidian-cli"},
    )

    written = external_skills._distribute_for_gemini([bundle], target_root=target)

    assert written == 1
    assert not (target / "defuddle").exists()
    assert (target / "obsidian-cli" / "SKILL.md").is_file()


def test_codex_superpowers_source_is_codex_global_subdir_source(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "home" / ".codex" / "superpowers" / "skills"
    monkeypatch.setattr(
        "src.config.paths.get_client_skill_dirs",
        lambda: {"codex-global-superpowers": source},
    )

    assert skill_sync._source_tag_to_adapter_name("codex-global-superpowers") == "codex"
    assert skill_sync._source_tag_scope("codex-global-superpowers") == "global"
    assert skill_sync._resolve_client_skill_dirs(tmp_path) == [
        ("codex-global-superpowers", source, True)
    ]

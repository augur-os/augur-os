from __future__ import annotations

from pathlib import Path


def _write_skill(skill_dir: Path, name: str, *, generated: bool = False) -> None:
    skill_dir.mkdir(parents=True)
    generated_header = (
        "<!--\n" "AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY\n" "Generator: test\n" "-->\n" if generated else ""
    )
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name} skill\n---\n{generated_header}# {name}\n",
        encoding="utf-8",
    )


def test_discover_all_skills_includes_supported_client_skill_dirs(tmp_path: Path, monkeypatch) -> None:
    from src.plugins import skill_discovery

    claude_global = tmp_path / "home" / ".claude" / "skills"
    codex_global = tmp_path / "home" / ".codex" / "skills"
    gemini_local = tmp_path / "project" / ".gemini" / "skills"

    _write_skill(claude_global / "geo-audit", "geo-audit")
    _write_skill(codex_global / ".system" / "imagegen", "imagegen")
    _write_skill(codex_global / "codex-primary-runtime" / "spreadsheets", "excel")
    _write_skill(gemini_local / "gemini-helper", "gemini-helper", generated=True)

    monkeypatch.setattr(skill_discovery, "_load_disabled_skills", lambda: set())
    monkeypatch.setattr(skill_discovery, "get_skills_dir", lambda: tmp_path / "project" / "skills")
    monkeypatch.setattr(skill_discovery, "get_claude_plugin_skill_dirs", lambda: [])
    monkeypatch.setattr(
        skill_discovery,
        "_get_client_skill_dirs",
        lambda: {
            "claude-global": claude_global,
            "codex-global": codex_global,
            "gemini-local": gemini_local,
        },
    )
    skill_discovery.invalidate_discovery_cache()

    records = skill_discovery.discover_all_skills(tiers=(2,))

    by_name = {record.name: record for record in records}
    assert {"geo-audit", "imagegen", "excel", "gemini-helper"} <= set(by_name)
    assert by_name["geo-audit"].source == "claude-global"
    assert by_name["geo-audit"].ownership == "external"
    assert by_name["geo-audit"].source_root == "external-client"
    assert by_name["geo-audit"].canonical is False
    assert by_name["imagegen"].source == "codex-global"
    assert by_name["imagegen"].ownership == "external"
    assert by_name["imagegen"].source_root == "external-client"
    assert by_name["imagegen"].canonical is False
    assert by_name["excel"].source == "codex-global"
    assert by_name["excel"].ownership == "external"
    assert by_name["excel"].source_root == "external-client"
    assert by_name["excel"].canonical is False
    assert by_name["gemini-helper"].source == "gemini-local"
    assert by_name["gemini-helper"].ownership == "external"
    assert by_name["gemini-helper"].source_root == "external-client"
    assert by_name["gemini-helper"].canonical is False


def test_discover_all_skills_aggregates_same_skill_across_clients(tmp_path: Path, monkeypatch) -> None:
    from src.plugins import skill_discovery

    codex_local = tmp_path / "project" / ".codex" / "skills"
    gemini_local = tmp_path / "project" / ".gemini" / "skills"
    _write_skill(codex_local / "dev-loops", "dev-loops", generated=True)
    _write_skill(gemini_local / "dev-loops", "dev-loops", generated=True)

    monkeypatch.setattr(skill_discovery, "_load_disabled_skills", lambda: set())
    monkeypatch.setattr(skill_discovery, "get_skills_dir", lambda: tmp_path / "project" / "skills")
    monkeypatch.setattr(skill_discovery, "get_claude_plugin_skill_dirs", lambda: [])
    monkeypatch.setattr(
        skill_discovery,
        "_get_client_skill_dirs",
        lambda: {
            "codex-local": codex_local,
            "gemini-local": gemini_local,
        },
    )
    skill_discovery.invalidate_discovery_cache()

    records = skill_discovery.discover_all_skills(tiers=(2,))

    dev_loops = [record for record in records if record.name == "dev-loops"]
    assert len(dev_loops) == 1
    assert set(dev_loops[0].client_sources) == {"codex-local", "gemini-local"}
    assert dev_loops[0].source_root == "external-client"
    assert dev_loops[0].canonical is False


def test_discover_all_skills_includes_codex_superpowers_source(tmp_path: Path, monkeypatch) -> None:
    from src.plugins import skill_discovery

    codex_superpowers = tmp_path / "home" / ".codex" / "superpowers" / "skills"
    _write_skill(codex_superpowers / "systematic-debugging", "systematic-debugging")

    monkeypatch.setattr(skill_discovery, "_load_disabled_skills", lambda: set())
    monkeypatch.setattr(skill_discovery, "get_skills_dir", lambda: tmp_path / "project" / "skills")
    monkeypatch.setattr(skill_discovery, "get_claude_plugin_skill_dirs", lambda: [])
    monkeypatch.setattr(
        skill_discovery,
        "_get_client_skill_dirs",
        lambda: {
            "codex-global-superpowers": codex_superpowers,
        },
    )
    skill_discovery.invalidate_discovery_cache()

    records = skill_discovery.discover_all_skills(tiers=(2,))

    by_name = {record.name: record for record in records}
    assert by_name["systematic-debugging"].source == "codex-global-superpowers"
    assert by_name["systematic-debugging"].client_sources == ("codex-global-superpowers",)
    assert by_name["systematic-debugging"].source_root == "external-client"
    assert by_name["systematic-debugging"].canonical is False

"""Tests for ownership and upstream fields in SkillRecord."""

from __future__ import annotations

import tempfile
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch


from src.plugins.skill_discovery import (
    SkillRecord,
    discover_all_skills,
    _discover_all_skills_impl,
    invalidate_discovery_cache,
)


def _minimal_record(**overrides) -> SkillRecord:
    """Build a SkillRecord with minimal required fields."""
    defaults = dict(
        name="test-skill",
        description="A test skill",
        path=Path("/tmp/test-skill"),
        author="bundled",
        hub="dev",
        visibility="",
        loop_config={},
        dependencies={},
        mcp_tools=[],
        dashboard_pages=[],
        commands=[],
        config={},
        agent=None,
        skill_type="domain",
        tags=(),
        tier=0,
        origin="augur",
        ownership="augur",
        upstream={},
        source="augur",
        source_root="project-brain",
        canonical=True,
    )
    defaults.update(overrides)
    return SkillRecord(**defaults)


def _write_skill_md(skill_dir: Path, name: str, description: str = "test", extra_fm: str = "") -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    fm = f"---\nname: {name}\ndescription: {description}\n{extra_fm}---\n\nSkill body.\n"
    (skill_dir / "SKILL.md").write_text(fm, encoding="utf-8")


def _write_flat_skill(skill_dir: Path, name: str, description: str = "test", ext: str = ".md") -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / f"{name}{ext}").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\nBody.\n",
        encoding="utf-8",
    )


def _client_dirs(**overrides) -> dict[str, Path]:
    base = {
        "claude-local": Path("/nonexistent"),
        "claude-global": Path("/nonexistent"),
        "codex-local": Path("/nonexistent"),
        "codex-global": Path("/nonexistent"),
        "gemini-local": Path("/nonexistent"),
        "gemini-global": Path("/nonexistent"),
        "cursor-local": Path("/nonexistent"),
        "cursor-global": Path("/nonexistent"),
        "copilot-local": Path("/nonexistent"),
        "copilot-global": Path("/nonexistent"),
        "opencode-local": Path("/nonexistent"),
        "opencode-global": Path("/nonexistent"),
    }
    base.update(overrides)
    return base


def test_ownership_field_exists():
    record = _minimal_record(ownership="augur")
    assert record.ownership == "augur"


def test_upstream_field_defaults_to_dict():
    record = _minimal_record()
    assert record.upstream == {}
    assert isinstance(record.upstream, dict)


def test_ownership_field_can_be_adopted():
    record = _minimal_record(ownership="adopted")
    assert record.ownership == "adopted"


def test_upstream_field_can_be_set():
    record = _minimal_record(ownership="adopted", upstream={"repo": "owner/seo"})
    assert record.upstream == {"repo": "owner/seo"}


def test_ownership_and_upstream_in_asdict():
    record = _minimal_record(ownership="adopted", upstream={"repo": "owner/seo"})
    d = asdict(record)
    assert d["ownership"] == "adopted"
    assert d["upstream"] == {"repo": "owner/seo"}


def test_ownership_defaults_to_augur():
    """Ownership should default to 'augur' when not specified."""
    defaults = dict(
        name="test",
        description="test",
        path=Path("/tmp/test"),
        author="bundled",
        hub="dev",
        visibility="",
        loop_config={},
        dependencies={},
        mcp_tools=[],
        dashboard_pages=[],
        commands=[],
        config={},
        agent=None,
        skill_type="domain",
        tags=(),
        tier=0,
        origin="augur",
    )
    record = SkillRecord(**defaults)
    assert record.ownership == "augur"


def test_discover_managed_skill_defaults_to_augur_ownership():
    """Skills under project-brain/capabilities/skills/ default to managed augur ownership."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skill_dir = root / "project-brain" / "capabilities" / "skills" / "seo"
        _write_skill_md(skill_dir, "seo")

        with (
            patch("src.plugins.skill_discovery.get_project_root", return_value=root),
            patch(
                "src.plugins.skill_discovery.get_managed_skill_source_dirs",
                return_value=[root / "project-brain" / "capabilities" / "skills"],
            ),
            patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
            patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value=_client_dirs()),
        ):
            invalidate_discovery_cache()
            records = _discover_all_skills_impl(tiers=(0,))

        record = next(r for r in records if r.name == "seo")
        assert record.ownership == "augur"
        assert record.upstream == {}
        assert record.origin == "project-brain"
        assert record.source_root == "project-brain"


def test_discovery_ignores_stale_repo_root_skills_even_if_supplied_as_managed(tmp_path):
    """root/skills is not an active managed source after the project-brain migration."""
    root = tmp_path / "repo"
    stale_skill = root.joinpath("skills", "legacy")
    shared_skill = root / "project-brain" / "capabilities" / "skills" / "active"
    _write_skill_md(stale_skill, "legacy")
    _write_skill_md(shared_skill, "active")

    with (
        patch("src.plugins.skill_discovery.get_project_root", return_value=root),
        patch(
            "src.plugins.skill_discovery.get_managed_skill_source_dirs",
            return_value=[root.joinpath("skills"), root / "project-brain" / "capabilities" / "skills"],
        ),
        patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
        patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value=_client_dirs()),
    ):
        invalidate_discovery_cache()
        records = _discover_all_skills_impl(tiers=(0,))

    records_by_name = {record.name: record for record in records}
    assert "active" in records_by_name
    assert "legacy" not in records_by_name
    assert records_by_name["active"].source_root == "project-brain"


def test_discovery_ignores_vault_drafts_and_archive(monkeypatch, tmp_path):
    from src.plugins import skill_discovery

    repo = tmp_path / "repo"
    vault = tmp_path / "vault"
    repo_skills = repo / "project-brain" / "capabilities" / "skills"
    vault_skills = vault / "skills"
    draft_skill = vault / "drafts" / "staging" / "r4" / "skills" / "draft-only"
    archived_skill = vault / "archive" / "skills" / "archived-only"

    for skill_dir in (repo_skills / "knowledge", vault_skills / "career-ops", draft_skill, archived_skill):
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {skill_dir.name}\nx-augur-hub: workspace\n---\n", encoding="utf-8"
        )

    monkeypatch.setattr(skill_discovery, "get_project_root", lambda: repo)
    monkeypatch.setattr(
        skill_discovery, "get_managed_skill_source_dirs", lambda project_root=None: [repo_skills, vault_skills]
    )
    monkeypatch.setattr(skill_discovery, "get_configured_vault_skills_dir", lambda project_root=None: vault_skills)
    monkeypatch.setattr(skill_discovery, "get_vault_skills_dir", lambda: vault_skills)
    skill_discovery.invalidate_discovery_cache()

    names = {record.name for record in skill_discovery.discover_all_skills(tiers=(0,))}

    assert "knowledge" in names
    assert "career-ops" in names
    assert "draft-only" not in names
    assert "archived-only" not in names


def test_discovery_source_roots_resolve_only_active_repo_and_vault_skills(monkeypatch, tmp_path):
    from src.plugins import skill_discovery

    repo = tmp_path / "repo"
    vault = tmp_path / "vault"
    repo_skills = repo / "project-brain" / "capabilities" / "skills"
    vault_skills = vault / "capabilities" / "skills"
    draft_skill = vault / "drafts" / "staging" / "r4" / "skills" / "draft-only"
    archived_skill = vault / "archive" / "skills" / "archived-only"

    for skill_dir in (
        repo_skills / "knowledge",
        vault_skills / "career-ops",
        draft_skill,
        archived_skill,
    ):
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {skill_dir.name}\nx-augur-hub: workspace\n---\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(skill_discovery, "get_project_root", lambda: repo)
    monkeypatch.setattr(
        skill_discovery,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [repo_skills, vault_skills],
    )
    monkeypatch.setattr(skill_discovery, "get_configured_vault_skills_dir", lambda project_root=None: vault_skills)
    monkeypatch.setattr(skill_discovery, "get_vault_skills_dir", lambda: vault_skills)
    monkeypatch.setattr(skill_discovery, "get_claude_plugin_skill_dirs", lambda: [])
    monkeypatch.setattr(skill_discovery, "_get_client_skill_dirs", lambda: _client_dirs())
    skill_discovery.invalidate_discovery_cache()

    roots = skill_discovery.get_managed_skill_source_dirs(skill_discovery.get_project_root())
    resolved_roots = {root.resolve() for root in roots}
    records_by_name = {record.name: record for record in skill_discovery.discover_all_skills(tiers=(0,))}

    assert repo_skills.resolve() in resolved_roots
    assert vault_skills.resolve() in resolved_roots
    assert draft_skill.parent.resolve() not in resolved_roots
    assert archived_skill.parent.resolve() not in resolved_roots
    assert all("drafts" not in root.parts for root in roots)
    assert all("archive" not in root.parts for root in roots)

    knowledge = records_by_name["knowledge"]
    career_ops = records_by_name["career-ops"]

    assert knowledge.path.resolve() == (repo_skills / "knowledge").resolve()
    assert knowledge.source_root == "project-brain"
    assert knowledge.origin == "project-brain"
    assert career_ops.path.resolve() == (vault_skills / "career-ops").resolve()
    assert career_ops.source_root == "private-vault"
    assert career_ops.origin == "private-vault"
    assert "draft-only" not in records_by_name
    assert "archived-only" not in records_by_name


def test_discovery_includes_standard_bundle_subskills(monkeypatch, tmp_path):
    from src.plugins import skill_discovery

    repo = tmp_path / "repo"
    vault = tmp_path / "vault"
    repo_skills = repo / "project-brain" / "capabilities" / "skills"
    vault_skills = vault / "capabilities" / "skills"
    apple = vault_skills / "apple"
    (apple / "apple-notes").mkdir(parents=True)
    (apple / "DESCRIPTION.md").write_text("# Apple\n\nLocal Apple skills.\n", encoding="utf-8")
    (apple / "apple-notes" / "SKILL.md").write_text(
        "# Apple Notes\n\nUse local Apple Notes.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(skill_discovery, "get_project_root", lambda: repo)
    monkeypatch.setattr(
        skill_discovery,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [repo_skills, vault_skills],
    )
    monkeypatch.setattr(skill_discovery, "get_configured_vault_skills_dir", lambda project_root=None: vault_skills)
    monkeypatch.setattr(skill_discovery, "get_vault_skills_dir", lambda: vault_skills)
    monkeypatch.setattr(skill_discovery, "get_claude_plugin_skill_dirs", lambda: [])
    monkeypatch.setattr(skill_discovery, "_get_client_skill_dirs", lambda: _client_dirs())
    skill_discovery.invalidate_discovery_cache()

    records_by_name = {record.name: record for record in skill_discovery.discover_all_skills(tiers=(0,))}

    assert "apple-notes" in records_by_name
    record = records_by_name["apple-notes"]
    assert record.path == apple / "apple-notes"
    assert record.description == "Use local Apple Notes."
    assert record.origin == "private-vault"
    assert record.source_root == "private-vault"
    assert record.ownership == "user"
    assert record.requires_platform is False


def test_discover_managed_skill_can_be_adopted_with_upstream():
    """Managed skills can opt into adopted ownership and upstream metadata."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skill_dir = root / "project-brain" / "capabilities" / "skills" / "seo"
        _write_skill_md(
            skill_dir,
            "seo",
            extra_fm="ownership: adopted\nupstream:\n  repo: owner/seo\n  ref: v1\n",
        )

        with (
            patch("src.plugins.skill_discovery.get_project_root", return_value=root),
            patch(
                "src.plugins.skill_discovery.get_managed_skill_source_dirs",
                return_value=[root / "project-brain" / "capabilities" / "skills"],
            ),
            patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
            patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value=_client_dirs()),
        ):
            invalidate_discovery_cache()
            records = _discover_all_skills_impl(tiers=(0,))

        record = next(r for r in records if r.name == "seo")
        assert record.ownership == "adopted"
        assert record.upstream == {"repo": "owner/seo", "ref": "v1"}


def test_discover_claude_local_skills_are_external():
    """Skills outside skills/ are discovered as external inventory."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skill_dir = root / ".claude" / "skills" / "my-tool"
        _write_skill_md(skill_dir, "my-tool")

        with (
            patch("src.plugins.skill_discovery.get_project_root", return_value=root),
            patch("src.plugins.skill_discovery.get_managed_skill_source_dirs", return_value=[]),
            patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
            patch(
                "src.plugins.skill_discovery._get_client_skill_dirs",
                return_value=_client_dirs(**{"claude-local": root / ".claude" / "skills"}),
            ),
        ):
            invalidate_discovery_cache()
            records = _discover_all_skills_impl()

        record = next(r for r in records if r.name == "my-tool")
        assert record.ownership == "external"
        assert record.upstream == {}
        assert record.origin == "claude-local"
        assert record.tier == 2


def test_discover_cursor_flat_skills_are_external():
    """Flat cursor prompt files outside skills/ are external inventory."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        prompts_dir = root / ".cursor" / "rules"
        _write_flat_skill(prompts_dir, "cursor-tool", ext=".mdc")

        with (
            patch("src.plugins.skill_discovery.get_project_root", return_value=root),
            patch("src.plugins.skill_discovery.get_managed_skill_source_dirs", return_value=[]),
            patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
            patch(
                "src.plugins.skill_discovery._get_client_skill_dirs",
                return_value=_client_dirs(**{"cursor-local": prompts_dir}),
            ),
        ):
            invalidate_discovery_cache()
            records = _discover_all_skills_impl()

        record = next(r for r in records if r.name == "cursor-tool")
        assert record.ownership == "external"
        assert record.upstream == {}
        assert record.origin == "cursor-local"
        assert record.tier == 2


def test_augur_skill_wins_over_client_skill():
    """When same skill exists in project-brain/capabilities/skills/ and .claude/skills/, project-brain wins."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        augur_skill = root / "project-brain" / "capabilities" / "skills" / "shared"
        _write_skill_md(augur_skill, "shared", description="augur version")
        claude_skill = root / ".claude" / "skills" / "shared"
        _write_skill_md(claude_skill, "shared", description="claude version")

        with (
            patch("src.plugins.skill_discovery.get_project_root", return_value=root),
            patch(
                "src.plugins.skill_discovery.get_managed_skill_source_dirs",
                return_value=[root / "project-brain" / "capabilities" / "skills"],
            ),
            patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
            patch(
                "src.plugins.skill_discovery._get_client_skill_dirs",
                return_value=_client_dirs(**{"claude-local": root / ".claude" / "skills"}),
            ),
        ):
            invalidate_discovery_cache()
            records = _discover_all_skills_impl()

        shared = next((s for s in records if s.name == "shared"), None)
        assert shared is not None
        assert shared.ownership == "augur"
        assert shared.description == "augur version"


def test_discover_vault_skill_is_user_owned_and_canonical(tmp_path):
    root = tmp_path / "repo"
    vault = tmp_path / "vault"
    vault_skill = vault / "skills" / "career-ops"
    _write_skill_md(vault_skill, "career-ops")

    with (
        patch("src.plugins.skill_discovery.get_project_root", return_value=root),
        patch(
            "src.plugins.skill_discovery.get_managed_skill_source_dirs",
            return_value=[root / "project-brain" / "capabilities" / "skills", vault / "skills"],
        ),
        patch("src.plugins.skill_discovery.get_configured_vault_skills_dir", return_value=vault / "skills"),
        patch("src.plugins.skill_discovery.get_vault_skills_dir", return_value=vault / "skills"),
        patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
        patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value=_client_dirs()),
    ):
        invalidate_discovery_cache()
        records = _discover_all_skills_impl(tiers=(0,))

    record = next(r for r in records if r.name == "career-ops")
    assert record.ownership == "user"
    assert record.source_root == "private-vault"
    assert record.canonical is True


def test_discovery_ignores_vault_drafts(tmp_path):
    root = tmp_path / "repo"
    vault = tmp_path / "vault"
    draft_skill = vault / "_drafts" / "staging" / "r4" / "skills" / "venture"
    _write_skill_md(draft_skill, "venture")

    with (
        patch("src.plugins.skill_discovery.get_project_root", return_value=root),
        patch(
            "src.plugins.skill_discovery.get_managed_skill_source_dirs",
            return_value=[root / "project-brain" / "capabilities" / "skills", vault / "skills"],
        ),
        patch("src.plugins.skill_discovery.get_configured_vault_skills_dir", return_value=vault / "skills"),
        patch("src.plugins.skill_discovery.get_vault_skills_dir", return_value=vault / "skills"),
        patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
        patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value=_client_dirs()),
    ):
        invalidate_discovery_cache()
        records = _discover_all_skills_impl()

    assert all(record.name != "venture" for record in records)


def test_shared_vault_skill_beats_private_vault_skill_even_when_managed_roots_are_reversed(tmp_path):
    root = tmp_path / "repo"
    vault = tmp_path / "vault"
    repo_skill = root / "project-brain" / "capabilities" / "skills" / "shared-skill"
    vault_skill = vault / "skills" / "shared-skill"
    _write_skill_md(repo_skill, "shared-skill", description="repo version")
    _write_skill_md(vault_skill, "shared-skill", description="vault version")

    with (
        patch("src.plugins.skill_discovery.get_project_root", return_value=root),
        patch(
            "src.plugins.skill_discovery.get_managed_skill_source_dirs",
            return_value=[vault / "skills", root / "project-brain" / "capabilities" / "skills"],
        ),
        patch("src.plugins.skill_discovery.get_configured_vault_skills_dir", return_value=vault / "skills"),
        patch("src.plugins.skill_discovery.get_vault_skills_dir", return_value=vault / "skills"),
        patch("src.plugins.skill_discovery.get_claude_plugin_skill_dirs", return_value=[]),
        patch("src.plugins.skill_discovery._get_client_skill_dirs", return_value=_client_dirs()),
    ):
        invalidate_discovery_cache()
        records = discover_all_skills(tiers=(0,))

    record = next(r for r in records if r.name == "shared-skill")
    assert record.description == "repo version"
    assert record.source_root == "project-brain"
    assert record.ownership == "augur"

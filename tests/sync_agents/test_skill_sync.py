"""Tests for skill sync compatibility helpers and auto-tag functions."""

from __future__ import annotations

from types import SimpleNamespace


class TestCleanupOrphanAdaptedCopies:
    """Post-ADR-479 orphan cleanup is intentionally a no-op."""

    def test_returns_empty_list(self, tmp_path):
        from sync_agents.engine import cleanup_orphan_adapted_copies

        assert cleanup_orphan_adapted_copies(tmp_path) == []

    def test_leaves_existing_adapted_copy_untouched(self, tmp_path):
        from sync_agents.engine import cleanup_orphan_adapted_copies

        adapted = tmp_path / ".gemini" / "skills" / "legacy-copy"
        adapted.mkdir(parents=True)
        skill_md = adapted / "SKILL.md"
        skill_md.write_text(
            "---\nname: legacy-copy\n---\n" "<!-- AUGUR-ADAPTED-COPY source=claude-code -->\n# Legacy\n"
        )

        assert cleanup_orphan_adapted_copies(tmp_path) == []
        assert skill_md.exists()


# ---------------------------------------------------------------------------
# auto_tag_master
# ---------------------------------------------------------------------------


class TestAutoTagMaster:
    """Tests for auto_tag_master()."""

    def test_writes_tag_when_missing(self, tmp_path):
        from sync_agents.engine import auto_tag_master

        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\ndescription: A skill\n---\n# My Skill\n")

        result = auto_tag_master(skill_md, "claude-code")
        assert result is True

        content = skill_md.read_text()
        assert "x-augur-master: claude-code" in content
        assert "# My Skill" in content

    def test_skips_when_already_set(self, tmp_path):
        from sync_agents.engine import auto_tag_master

        skill_md = tmp_path / "SKILL.md"
        original = "---\ndescription: A skill\nx-augur-master: codex\n---\n# My Skill\n"
        skill_md.write_text(original)

        result = auto_tag_master(skill_md, "claude-code")
        assert result is False

        content = skill_md.read_text()
        assert "x-augur-master: codex" in content
        assert "x-augur-master: claude-code" not in content

    def test_handles_no_frontmatter(self, tmp_path):
        from sync_agents.engine import auto_tag_master

        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("# Plain Skill\nNo frontmatter here.\n")

        result = auto_tag_master(skill_md, "gemini")
        assert result is True

        content = skill_md.read_text()
        assert "x-augur-master: gemini" in content


def test_managed_skill_sources_reads_repo_and_vault_roots(tmp_path, monkeypatch):
    from sync_agents import skill_sync

    repo_skills = tmp_path / "repo" / "skills"
    vault_skills = tmp_path / "vault" / "skills"
    for root, name in ((repo_skills, "ask"), (vault_skills, "career-ops")):
        skill_dir = root / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {name}\n---\n\n# {name}\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        skill_sync,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [repo_skills, vault_skills],
    )

    sources = skill_sync._load_managed_skill_sources(tmp_path / "repo")

    assert [name for name, *_ in sources] == ["ask", "career-ops"]


def test_managed_skill_sources_only_reads_returned_roots_and_excludes_inactive_vault_roots(
    tmp_path,
    monkeypatch,
):
    from sync_agents import skill_sync

    repo_skills = tmp_path / "repo" / "skills"
    vault_skills = tmp_path / "vault" / "skills"
    draft_skill = tmp_path / "vault" / "drafts" / "staging" / "r4" / "skills" / "draft-only"
    archived_skill = tmp_path / "vault" / "archive" / "skills" / "archived-only"
    (repo_skills / "ask").mkdir(parents=True)
    (repo_skills / "ask" / "SKILL.md").write_text(
        "---\nname: ask\ndescription: ask\n---\n\n# Ask\n",
        encoding="utf-8",
    )
    (vault_skills / "career-ops").mkdir(parents=True)
    (vault_skills / "career-ops" / "SKILL.md").write_text(
        "---\nname: career-ops\ndescription: career-ops\n---\n\n# Career Ops\n",
        encoding="utf-8",
    )
    draft_skill.mkdir(parents=True)
    (draft_skill / "SKILL.md").write_text(
        "---\nname: draft-only\ndescription: draft-only\n---\n\n# Draft Only\n",
        encoding="utf-8",
    )
    archived_skill.mkdir(parents=True)
    (archived_skill / "SKILL.md").write_text(
        "---\nname: archived-only\ndescription: archived-only\n---\n\n# Archived Only\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        skill_sync,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [repo_skills, vault_skills],
    )

    # This verifies the managed-root contract only: loading traverses the returned
    # roots and therefore excludes draft content that exists elsewhere in the vault.
    sources = skill_sync._load_managed_skill_sources(tmp_path / "repo")
    exported_names = [name for name, *_ in sources]

    assert exported_names == ["ask", "career-ops"]
    assert "draft-only" not in exported_names
    assert "archived-only" not in exported_names


def test_managed_skill_sources_prefer_repo_over_vault_for_duplicate_names_even_if_roots_are_reversed(
    tmp_path,
    monkeypatch,
):
    from sync_agents import skill_sync

    repo_skills = tmp_path / "repo" / "skills"
    vault_skills = tmp_path / "vault" / "skills"
    repo_skill_dir = repo_skills / "ask"
    vault_skill_dir = vault_skills / "ask"
    repo_skill_dir.mkdir(parents=True)
    vault_skill_dir.mkdir(parents=True)
    (vault_skill_dir / "SKILL.md").write_text(
        "---\nname: ask\ndescription: vault ask\n---\n\n# Vault Ask\nVault body\n",
        encoding="utf-8",
    )
    (repo_skill_dir / "SKILL.md").write_text(
        "---\nname: ask\ndescription: repo ask\n---\n\n# Repo Ask\nRepo body\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        skill_sync,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [vault_skills, repo_skills],
    )

    sources = skill_sync._load_managed_skill_sources(tmp_path / "repo")

    assert [name for name, *_ in sources] == ["ask"]
    assert sources[0][1] == repo_skill_dir
    assert "Repo body" in sources[0][3]
    assert sources[0][4] == "repo ask"


def test_managed_skill_sources_drive_canonical_skill_exports(tmp_path, monkeypatch):
    from sync_agents import skill_sync

    managed_sources = [
        ("ask", tmp_path / "skills" / "ask", "---\nname: ask\n---\n", "# ask", "ask", False),
        (
            "career-ops",
            tmp_path / "vault" / "skills" / "career-ops",
            "---\nname: career-ops\n---\n",
            "# career-ops",
            "career-ops",
            False,
        ),
    ]
    captured: dict[str, object] = {}

    monkeypatch.setattr(skill_sync, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(skill_sync, "_load_managed_skill_sources", lambda project_root: managed_sources)

    def fake_sync_skill_exports(adapters, sources, **kwargs):
        captured["adapters"] = adapters
        captured["sources"] = sources
        captured["kwargs"] = kwargs
        return 2

    monkeypatch.setattr(skill_sync, "_sync_skill_exports", fake_sync_skill_exports)

    written = skill_sync._sync_skill_stubs([SimpleNamespace(adapter_name="claude-code")], cleanup_disabled=False)

    assert written == 2
    assert captured["sources"] == managed_sources
    assert captured["kwargs"] == {"cleanup_disabled": False}


def test_sync_skill_stubs_excludes_vault_drafts_and_archive(tmp_path, monkeypatch):
    from sync_agents import skill_sync

    repo_root = tmp_path / "repo"
    repo_skills = repo_root / "project-brain" / "capabilities" / "skills"
    vault_skills = tmp_path / "vault" / "skills"
    draft_skill = tmp_path / "vault" / "drafts" / "staging" / "r4" / "skills" / "draft-only"
    archived_skill = tmp_path / "vault" / "archive" / "skills" / "archived-only"

    for root, name in (
        (repo_skills, "ask"),
        (vault_skills, "career-ops"),
        (draft_skill.parent, "draft-only"),
        (archived_skill.parent, "archived-only"),
    ):
        skill_dir = root / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {name}\n---\n\n# {name}\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(skill_sync, "PROJECT_ROOT", repo_root)
    monkeypatch.setattr(
        skill_sync,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [repo_skills, vault_skills],
    )

    captured: dict[str, object] = {}

    def fake_sync_skill_exports(adapters, sources, **kwargs):
        captured["sources"] = sources
        return len(sources)

    monkeypatch.setattr(skill_sync, "_sync_skill_exports", fake_sync_skill_exports)

    written = skill_sync._sync_skill_stubs([SimpleNamespace(adapter_name="claude-code")], cleanup_disabled=False)
    sources = captured["sources"]
    assert isinstance(sources, list)
    exported_names = [name for name, *_ in sources]

    assert written == 2
    assert exported_names == ["ask", "career-ops"]
    assert "draft-only" not in exported_names
    assert "archived-only" not in exported_names


def test_managed_command_sources_prefer_repo_over_vault_for_duplicate_ids_even_if_roots_are_reversed(
    tmp_path,
    monkeypatch,
):
    from sync_agents import skill_sync

    repo_skills = tmp_path / "repo" / "project-brain" / "capabilities" / "skills"
    vault_skills = tmp_path / "vault" / "skills"
    repo_commands = repo_skills / "release" / "commands"
    vault_commands = vault_skills / "release" / "commands"
    repo_commands.mkdir(parents=True)
    vault_commands.mkdir(parents=True)
    (repo_commands.parent / "SKILL.md").write_text(
        "---\nname: release\ndescription: release\n---\n\n# Release\n",
        encoding="utf-8",
    )
    (vault_commands.parent / "SKILL.md").write_text(
        "---\nname: release\ndescription: release\n---\n\n# Release\n",
        encoding="utf-8",
    )
    (vault_commands / "deploy.md").write_text(
        "---\ndescription: vault deploy\nx-augur-export-command: true\n---\n\nVault deploy body\n",
        encoding="utf-8",
    )
    (repo_commands / "deploy.md").write_text(
        "---\ndescription: repo deploy\nx-augur-export-command: true\n---\n\nRepo deploy body\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(skill_sync, "PROJECT_ROOT", tmp_path / "repo")
    monkeypatch.setattr(
        skill_sync,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [vault_skills, repo_skills],
    )

    command_sources = skill_sync._load_managed_command_sources(tmp_path / "repo")

    assert [name for name, *_ in command_sources] == ["deploy"]
    assert command_sources[0][1] == repo_commands / "deploy.md"
    assert "Repo deploy body" in command_sources[0][2]


def test_sync_command_stubs_prefer_repo_command_content_over_vault_duplicates(
    tmp_path,
    monkeypatch,
):
    from sync_agents import skill_sync

    repo_root = tmp_path / "repo"
    repo_skills = repo_root / "project-brain" / "capabilities" / "skills"
    vault_skills = tmp_path / "vault" / "skills"
    repo_commands = repo_skills / "release" / "commands"
    vault_commands = vault_skills / "release" / "commands"
    repo_commands.mkdir(parents=True)
    vault_commands.mkdir(parents=True)
    (repo_commands.parent / "SKILL.md").write_text(
        "---\nname: release\ndescription: release\n---\n\n# Release\n",
        encoding="utf-8",
    )
    (vault_commands.parent / "SKILL.md").write_text(
        "---\nname: release\ndescription: release\n---\n\n# Release\n",
        encoding="utf-8",
    )
    (vault_commands / "deploy.md").write_text(
        "---\ndescription: vault deploy\nx-augur-export-command: true\n---\n\nVault deploy body\n",
        encoding="utf-8",
    )
    (repo_commands / "deploy.md").write_text(
        "---\ndescription: repo deploy\nx-augur-export-command: true\n---\n\nRepo deploy body\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(skill_sync, "PROJECT_ROOT", repo_root)
    monkeypatch.setattr(
        skill_sync,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [vault_skills, repo_skills],
    )
    monkeypatch.setattr(
        skill_sync,
        "filter_named_sources",
        lambda _capability_type, sources, *, target, existing_names: sources,
    )

    written = skill_sync._sync_command_stubs([SimpleNamespace(adapter_name="gemini")], cleanup_disabled=False)

    generated_skill = repo_root / ".antigravity" / "plugins" / "deploy" / "SKILL.md"
    assert written == 1
    assert generated_skill.exists()
    content = generated_skill.read_text(encoding="utf-8")
    assert "Repo deploy body" in content
    assert "Vault deploy body" not in content


def test_sync_command_stubs_cleans_stale_outputs_when_no_managed_commands_exist(
    tmp_path,
    monkeypatch,
):
    from sync_agents import skill_sync

    repo_root = tmp_path / "repo"
    monkeypatch.setattr(skill_sync, "PROJECT_ROOT", repo_root)
    monkeypatch.setattr(skill_sync, "_load_managed_command_sources", lambda project_root: [])

    claude_dir = repo_root / ".claude" / "commands"
    claude_dir.mkdir(parents=True)
    (claude_dir / "deploy.md").write_text("stale claude deploy\n", encoding="utf-8")
    (claude_dir / ".augur-generated-commands.json").write_text(
        '{"files": ["deploy.md"]}\n',
        encoding="utf-8",
    )

    gemini_dir = repo_root / ".antigravity" / "plugins"
    stale_gemini = gemini_dir / "deploy"
    stale_gemini.mkdir(parents=True)
    (stale_gemini / "SKILL.md").write_text("stale gemini deploy\n", encoding="utf-8")
    (gemini_dir / ".augur-generated-commands.json").write_text(
        '{"files": ["deploy"]}\n',
        encoding="utf-8",
    )

    written = skill_sync._sync_command_stubs([SimpleNamespace(adapter_name="gemini")])

    assert written == 0
    assert not (claude_dir / "deploy.md").exists()
    assert not (claude_dir / ".augur-generated-commands.json").exists()
    assert not stale_gemini.exists()
    assert not (gemini_dir / ".augur-generated-commands.json").exists()

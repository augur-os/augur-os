"""Tests for sync_agents external skill distribution (ADR-605 Phase 3)."""

from __future__ import annotations

import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def test_external_skills_loads_yaml():
    """Retired Kepano/Obsidian bundles are not active external skill config.

    Note: ``find_project_root`` resolves a worktree to its main checkout, but
    config cleanup changes only land in the worktree. So this test passes the
    worktree root (the test file's grandparent) explicitly.
    """
    from sync_agents.external_skills import load_external_bundles

    worktree_root = Path(__file__).resolve().parents[2]
    bundles = load_external_bundles(project_root=worktree_root)
    retired = {"kepano-obsidian-skills", "kepano-defuddle-skill"}
    assert retired.isdisjoint({bundle.id for bundle in bundles})


# ---------------------------------------------------------------------------
# Codex file_copy
# ---------------------------------------------------------------------------


def _make_fake_bundle(tmp_path: Path) -> "object":
    """Build an in-memory ExternalSkillBundle backed by tmp_path skills."""
    from sync_agents.external_skills import ExternalSkillBundle

    source = tmp_path / "vendor" / "skills" / "obsidian-skills"
    skills_root = source / "skills"
    skill_names = [
        "obsidian-markdown",
        "obsidian-bases",
        "obsidian-cli",
        "json-canvas",
        "defuddle",
    ]
    for name in skill_names:
        skill_dir = skills_root / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            textwrap.dedent(f"""\
                ---
                name: {name}
                description: Test skill {name}
                ---
                # {name}

                Body for {name}.
                """),
            encoding="utf-8",
        )
        # Add a reference subdir to verify recursive copy.
        refs = skill_dir / "references"
        refs.mkdir()
        (refs / "notes.md").write_text(f"refs for {name}\n", encoding="utf-8")

    return ExternalSkillBundle(
        id="kepano-obsidian-skills",
        source=source,
        upstream="https://example.invalid/kepano",
        pinned_sha="deadbeef" * 5,
        skills=skill_names,
        targets={
            "codex": "file_copy",
            "opencode": "file_copy",
            "gemini": "convert_and_copy",
            "copilot": "convert_to_instructions",
            "claude_code": "marketplace",
        },
    )


def test_distribute_external_skills_codex_copies_allowed_files(tmp_path, monkeypatch):
    """The Codex adapter copies only policy-allowed skills to ``.codex/skills/``."""
    from sync_agents import external_skills as ext_mod
    from sync_agents.adapters import codex as codex_mod
    from sync_agents.adapters.codex import CodexAdapter

    bundle = _make_fake_bundle(tmp_path)

    target_root = tmp_path / "project" / ".codex" / "skills"

    # Patch PROJECT_ROOT both where the adapter resolves it AND where the
    # helper resolves it, so the adapter writes into our tmp_path tree.
    monkeypatch.setattr(codex_mod, "PROJECT_ROOT", target_root.parent.parent)
    monkeypatch.setattr(ext_mod, "PROJECT_ROOT", target_root.parent.parent)

    adapter = CodexAdapter()
    adapter.distribute_external_skills([bundle])

    assert (target_root / "defuddle" / "SKILL.md").exists()
    assert not (target_root / "obsidian-markdown").exists()
    assert not (target_root / "obsidian-bases").exists()
    assert not (target_root / "obsidian-cli").exists()
    assert not (target_root / "json-canvas").exists()

    # references/ subtree should be preserved.
    assert (target_root / "defuddle" / "references" / "notes.md").exists()


def test_file_copy_removes_stale_external_skills_when_target_dropped(tmp_path):
    """If an adapter target is removed, stale generated copies are deleted."""
    from sync_agents.external_skills import _distribute_via_file_copy

    bundle = _make_fake_bundle(tmp_path)
    bundle.targets = {"claude_code": "marketplace"}
    target_root = tmp_path / "project" / ".codex" / "skills"
    stale = target_root / "obsidian-markdown"
    stale.mkdir(parents=True)
    (stale / "SKILL.md").write_text("stale\n", encoding="utf-8")

    written = _distribute_via_file_copy(
        [bundle],
        adapter_name="codex",
        target_root=target_root,
        label="Codex",
    )

    assert written == 0
    assert not stale.exists()


def test_copilot_removes_stale_external_instruction_when_target_dropped(tmp_path):
    """Copilot instruction exports follow the same retired-target cleanup."""
    from sync_agents.external_skills import _distribute_for_copilot

    bundle = _make_fake_bundle(tmp_path)
    bundle.targets = {"claude_code": "marketplace"}
    target_root = tmp_path / "project" / ".github" / "instructions"
    target_root.mkdir(parents=True)
    stale = target_root / "obsidian-markdown.instructions.md"
    stale.write_text("stale\n", encoding="utf-8")

    written = _distribute_for_copilot([bundle], target_root=target_root)

    assert written == 0
    assert not stale.exists()


# ---------------------------------------------------------------------------
# Default no-op
# ---------------------------------------------------------------------------


def test_distribute_external_skills_default_is_noop(tmp_path):
    """``BaseAdapter.distribute_external_skills`` must not raise or write anything."""
    from sync_agents.adapters.base import BaseAdapter
    from sync_agents.external_skills import ExternalSkillBundle

    bundles = [
        ExternalSkillBundle(
            id="anything",
            source=tmp_path / "nonexistent",
            upstream="",
            pinned_sha="",
            skills=["x"],
            targets={"unknown_adapter": "file_copy"},
        )
    ]

    adapter = BaseAdapter()
    # Snapshot tmp_path contents BEFORE call.
    before = sorted(tmp_path.rglob("*"))
    result = adapter.distribute_external_skills(bundles)
    after = sorted(tmp_path.rglob("*"))

    assert result is None
    assert before == after, "default no-op must not write to filesystem"

"""Tests for src.lib.capabilities.duplicates (ADR-734 D5 scanner)."""

from __future__ import annotations

from pathlib import Path

from src.lib.capabilities import duplicates


def test_find_external_skill_duplicates_across_clients(tmp_path: Path):
    for client in (".claude", ".codex", ".gemini"):
        skill_dir = tmp_path / client / "skills" / "shared-tool"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: shared-tool\n---\n", encoding="utf-8")

    pairs = duplicates.find_external_skill_duplicates(tmp_path)
    assert pairs == [
        ("shared-tool", ("claude", "codex", "gemini")),
    ]


def test_find_external_skill_duplicates_ignores_single_client(tmp_path: Path):
    skill_dir = tmp_path / ".claude" / "skills" / "claude-only"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("x", encoding="utf-8")

    assert duplicates.find_external_skill_duplicates(tmp_path) == []


def test_find_external_skill_duplicates_skips_dirs_without_skill_md(tmp_path: Path):
    for client in (".claude", ".codex"):
        skill_dir = tmp_path / client / "skills" / "no-skill-md"
        skill_dir.mkdir(parents=True)

    assert duplicates.find_external_skill_duplicates(tmp_path) == []


def test_find_external_skill_duplicates_handles_missing_client_dirs(tmp_path: Path):
    assert duplicates.find_external_skill_duplicates(tmp_path) == []

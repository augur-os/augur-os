"""Tests for src.lib.capabilities.drafts (ADR-734 D6 scanner)."""

from __future__ import annotations

from pathlib import Path

from src.lib.capabilities import drafts


def test_find_draft_leftovers_finds_draft_suffix(tmp_path: Path):
    (tmp_path / "project-brain" / "capabilities" / "skills" / "demo").mkdir(parents=True)
    (tmp_path / "project-brain" / "capabilities" / "skills" / "demo" / "SKILL.draft.md").write_text(
        "x", encoding="utf-8"
    )

    leftovers = drafts.find_draft_leftovers(tmp_path)
    rel = sorted(p.relative_to(tmp_path).as_posix() for p in leftovers)
    assert rel == [
        "project-brain/capabilities/skills/demo/SKILL.draft.md",
    ]


def test_find_draft_leftovers_empty_when_no_drafts(tmp_path: Path):
    (tmp_path / "project-brain" / "capabilities" / "skills" / "real").mkdir(parents=True)
    (tmp_path / "project-brain" / "capabilities" / "skills" / "real" / "SKILL.md").write_text("x", encoding="utf-8")
    assert drafts.find_draft_leftovers(tmp_path) == []

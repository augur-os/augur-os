from pathlib import Path

from scripts.check_obsidian_vault_roots import (
    check_disallowed_skill_markdown,
    check_vault_roots,
)


def test_check_vault_roots_accepts_final_and_temporary_roots(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    for root in (
        "inbox",
        "notes",
        "sources",
        "wiki",
        "skills",
        "drafts",
        "archive",
        "config",
        "memory",
        "apple",
    ):
        (vault / root).mkdir(parents=True)

    result = check_vault_roots(vault, temporary_roots={"apple"})

    assert result == []


def test_check_vault_roots_reports_unapproved_root(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "career-ops").mkdir(parents=True)

    result = check_vault_roots(vault, temporary_roots=set())

    assert result == ["career-ops"]


def test_check_vault_roots_strict_keeps_memory_but_reports_temporary_roots(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    for root in ("memory", "apple"):
        (vault / root).mkdir(parents=True)

    result = check_vault_roots(vault, temporary_roots=set())

    assert result == ["apple"]


def test_default_temporary_roots_are_disallowed_after_review(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    for root in ("apple", "content", "growth", "remote-access", "updater"):
        (vault / root).mkdir(parents=True)

    result = check_vault_roots(vault)

    assert result == ["apple", "content", "growth", "remote-access", "updater"]


def test_check_disallowed_skill_markdown_reports_inactive_or_note_roots(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    allowed_active = vault / "skills" / "career-ops" / "SKILL.md"
    allowed_draft = vault / "drafts" / "staging" / "r4" / "skills" / "draft-only" / "SKILL.md"
    disallowed_note = vault / "notes" / "career" / "SKILL.md"
    disallowed_archive = vault / "archive" / "career" / "old-skill" / "SKILL.md"
    disallowed_config = vault / "config" / "career-ops" / "SKILL.md"

    for path in (allowed_active, allowed_draft, disallowed_note, disallowed_archive, disallowed_config):
        path.parent.mkdir(parents=True)
        path.write_text("---\nname: sample\n---\n", encoding="utf-8")

    result = check_disallowed_skill_markdown(vault)

    assert result == [
        "archive/career/old-skill/SKILL.md",
        "config/career-ops/SKILL.md",
        "notes/career/SKILL.md",
    ]

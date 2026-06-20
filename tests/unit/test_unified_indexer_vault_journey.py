from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.index._scanners_structural import _vault_journey_category, index_vault


def test_vault_journey_category_uses_drafts_root(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    draft_file = vault / "drafts" / "staging" / "r4" / "skills" / "career-ops" / "SKILL.md"
    legacy_file = vault / "_drafts" / "staging" / "r4" / "skills" / "career-ops" / "SKILL.md"
    archive_file = vault / "archive" / "career" / "old.md"

    assert _vault_journey_category(draft_file, vault) == "drafts"
    assert _vault_journey_category(legacy_file, vault) == "other"
    assert _vault_journey_category(archive_file, vault) == "archive"


def test_index_vault_marks_drafts_and_archive_inactive(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    rag_dir = tmp_path / "rag"
    files = [
        "notes/active.md",
        "drafts/staging/draft.md",
        "archive/career/old.md",
    ]
    for rel_path in files:
        path = vault / rel_path
        path.parent.mkdir(parents=True)
        path.write_text("---\ntitle: Test\n---\nBody\n", encoding="utf-8")

    assert index_vault(vault, rag_dir) == 3

    active_meta, _ = parse_frontmatter(rag_dir / "vault" / "notes" / "private" / "active.md")
    draft_meta, _ = parse_frontmatter(rag_dir / "vault" / "drafts" / "private" / "staging" / "draft.md")
    archive_meta, _ = parse_frontmatter(rag_dir / "vault" / "archive" / "private" / "career" / "old.md")

    assert active_meta["active_search_scope"] == "true"
    assert "inactive_scope" not in active_meta
    assert active_meta["vault_scope"] == "private"
    assert draft_meta["journey_category"] == "drafts"
    assert draft_meta["vault_scope"] == "private"
    assert draft_meta["inactive_scope"] == "true"
    assert draft_meta["active_search_scope"] == "false"
    assert archive_meta["journey_category"] == "archive"
    assert archive_meta["vault_scope"] == "private"
    assert archive_meta["inactive_scope"] == "true"
    assert archive_meta["active_search_scope"] == "false"


def test_index_vault_includes_project_brain_knowledge_notes_as_shared_notes(tmp_path: Path) -> None:
    project_root = tmp_path / "repo"
    shared_vault = project_root / "project-brain"
    private_vault = tmp_path / "private-vault"
    rag_dir = tmp_path / "rag"
    note = shared_vault / "knowledge" / "notes" / "comparison.md"
    note.parent.mkdir(parents=True)
    private_vault.mkdir(parents=True)
    note.write_text(
        "---\n" "title: Project Comparison\n" "tags:\n" "  - architecture\n" "---\n" "Shared project note body.\n",
        encoding="utf-8",
    )

    assert index_vault(private_vault, rag_dir, shared_vault_dir=shared_vault, root=project_root) == 1

    meta, _ = parse_frontmatter(rag_dir / "vault" / "notes" / "shared" / "comparison.md")
    assert meta["journey_category"] == "notes"
    assert meta["vault_scope"] == "shared"
    assert meta["source_root"] == "project-brain"
    assert meta["source_path"] == "project-brain/knowledge/notes/comparison.md"
    assert meta["title"] == "Project Comparison"
    assert meta["active_search_scope"] == "true"


def test_index_vault_keeps_scanning_when_markdown_is_not_utf8(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    rag_dir = tmp_path / "rag"
    bad = vault / "notes" / "legacy-export.md"
    good = vault / "notes" / "audio.md"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"---\ntitle: Legacy\x97Export\n---\nBody\n")
    good.write_text("---\ntitle: Audio Note\n---\nBody\n", encoding="utf-8")

    assert index_vault(vault, rag_dir) == 2

    bad_meta, _ = parse_frontmatter(rag_dir / "vault" / "notes" / "private" / "legacy-export.md")
    good_meta, _ = parse_frontmatter(rag_dir / "vault" / "notes" / "private" / "audio.md")
    assert bad_meta["frontmatter_parse_error"].startswith("UnicodeDecodeError:")
    assert bad_meta["description"] == "legacy-export"
    # Body summary takes precedence over the frontmatter title for vault notes
    # (commit 7bdfc1d81 "prefer vault summary callouts for descriptions").
    assert good_meta["description"] == "Body"


def test_index_vault_preserves_staged_skill_identity_in_drafts(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    rag_dir = tmp_path / "rag"
    staged_skill = vault / "drafts" / "staging" / "r3" / "skills" / "advisor" / "SKILL.md"
    staged_skill.parent.mkdir(parents=True)
    staged_skill.write_text(
        "---\n" "name: advisor\n" "description: Agent management draft.\n" "---\n" "Draft body\n",
        encoding="utf-8",
    )
    staged_action = staged_skill.parent / "augur" / "actions" / "advisor-overview.md"
    staged_action.parent.mkdir(parents=True)
    staged_action.write_text("---\ntitle: Advisor Overview\n---\nDraft action\n", encoding="utf-8")

    assert index_vault(vault, rag_dir) == 2

    meta, _ = parse_frontmatter(
        rag_dir / "vault" / "drafts" / "private" / "staging" / "r3" / "skills" / "advisor" / "SKILL.md"
    )
    action_meta, _ = parse_frontmatter(
        rag_dir
        / "vault"
        / "drafts"
        / "private"
        / "staging"
        / "r3"
        / "skills"
        / "advisor"
        / "augur"
        / "actions"
        / "advisor-overview.md"
    )

    assert meta["journey_category"] == "drafts"
    assert meta["inactive_scope"] == "true"
    assert meta["active_search_scope"] == "false"
    assert meta["draft_kind"] == "skill"
    assert meta["promotion_state"] == "staged-draft"
    assert meta["staging_batch"] == "r3"
    assert meta["skill"] == "advisor"
    assert meta["name"] == "advisor"
    assert meta["title"] == "advisor"
    # ADR-802 removed the hub concept; the indexer no longer emits hub metadata.
    assert "hub" not in meta
    assert meta["description"] == "Agent management draft."
    assert action_meta["journey_category"] == "drafts"
    assert action_meta["draft_kind"] == "skill-file"
    assert action_meta["promotion_state"] == "staged-draft"
    assert action_meta["staging_batch"] == "r3"
    assert action_meta["skill"] == "advisor"


def test_domains_layout_domain_dirs_are_notes_journey(tmp_path):
    """Domains-layout vaults bucket domain folders into the notes journey with
    the domain as collection (2026-06-12 reorg: Browse Notes showed zero
    personal notes because domains classified as 'other')."""
    from src.lib.index._scanners_structural import (
        _vault_journey_category_for_rel,
        _vault_note_collection,
    )

    rel = Path("career/interview/story-bank.md")
    assert _vault_journey_category_for_rel(rel, layout="domains") == "notes"
    assert _vault_note_collection(rel, "notes", layout="domains") == "career"
    assert _vault_journey_category_for_rel(Path("inbox/x.md"), layout="domains") == "inbox"
    assert _vault_journey_category_for_rel(Path("wiki/index.md"), layout="domains") == "wiki"
    # legacy unchanged
    assert _vault_journey_category_for_rel(Path("knowledge/notes/books/x.md")) == "notes"
    assert _vault_note_collection(Path("notes/books/x.md"), "notes") == "books"

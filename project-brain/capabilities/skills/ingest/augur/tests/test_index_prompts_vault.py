"""Tests for index_prompts() scanning the vault prompts directory (ADR-748 Task 5b).

index_prompts() must scan <vault>/prompts/*.md so user-saved prompt cards reach
the Browse "prompts" category, and must carry the prompt body + placeholders so
the dashboard Trigger button has something to dispatch. The prompt text is
stored in the index entry's body section (read back as `_body`), not its
frontmatter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import paths
from src.config.paths import get_project_root
from src.lib.index._scanners_knowledge import index_prompts
from src.lib.index.index_reader import read_index_entry
from skills.ingest.scripts.prompt_cards import write_prompt_card


@pytest.fixture(autouse=True)
def _clear_path_cache():
    paths.invalidate_project_cache()
    yield
    paths.invalidate_project_cache()


def _read_entries_by_source(prompts_dir: Path, source: str) -> list[dict]:
    """Return read-index-entry dicts whose `source` matches."""
    entries = []
    for entry_file in prompts_dir.rglob("*.md"):
        entry = read_index_entry(entry_file)
        if entry.get("source") == source:
            entries.append(entry)
    return entries


def test_index_prompts_scans_vault_prompts(tmp_path, monkeypatch):
    """A vault prompt card is indexed with source=vault, a body, and placeholders."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    body = "Draft a plan for {{goal}} given {{constraints}}.\n"
    card_path = write_prompt_card(
        vault_dir=vault_dir,
        label="Plan Drafter",
        description="Draft a project plan from a goal",
        body=body,
        source_url="https://example.com/prompt",
    )
    assert card_path.is_file()

    # Point get_vault_prompts_dir() at the temp vault.
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: vault_dir)
    paths.invalidate_project_cache()
    assert paths.get_vault_prompts_dir() == vault_dir / "prompts"

    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()

    count = index_prompts(get_project_root(), rag_dir)
    assert count > 0

    prompts_dir = rag_dir / "prompts"
    vault_entries = _read_entries_by_source(prompts_dir, "vault")

    assert len(vault_entries) == 1, f"expected one vault prompt entry, got {vault_entries}"
    entry = vault_entries[0]

    assert entry["source"] == "vault"
    assert entry["type"] == "prompt"
    assert entry["hub"] == "workspace"
    assert entry["bundle"] == "vault"
    # The prompt text lives in the entry's body section, surfaced as `_body`.
    assert "body" not in entry, "body must not be stored in entry frontmatter"
    assert entry.get("_body", "").strip(), "vault prompt entry must carry the prompt body"
    assert "{{goal}}" in entry["_body"]
    assert entry.get("placeholders") == "goal,constraints"
    assert entry.get("source_url") == "https://example.com/prompt"
    # Vault entries write to a distinct subdir to avoid skill-id collisions.
    assert Path(entry["_index_path"]).parent.name == "vault"


def test_index_prompts_skill_entries_carry_body_and_source(tmp_path, monkeypatch):
    """Existing skill-prompt entries now carry body, placeholders, source=skill."""
    # No vault prompts dir — exercise only the skill loop.
    empty_vault = tmp_path / "empty-vault"
    empty_vault.mkdir()
    monkeypatch.setattr(paths, "_vault_home_dir", lambda: empty_vault)
    paths.invalidate_project_cache()

    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()

    count = index_prompts(get_project_root(), rag_dir)
    assert count > 0

    prompts_dir = rag_dir / "prompts"
    skill_entries = _read_entries_by_source(prompts_dir, "skill")

    assert skill_entries, "expected at least one skill prompt entry"
    for entry in skill_entries:
        assert entry.get("source") == "skill"
        assert "body" not in entry, "body must not be stored in entry frontmatter"
        assert "placeholders" in entry


def test_index_prompts_skips_malformed_vault_file(tmp_path, monkeypatch):
    """A malformed vault prompt .md is skipped; the run completes and indexes the rest."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    # One well-formed prompt card.
    good_path = write_prompt_card(
        vault_dir=vault_dir,
        label="Good Prompt",
        description="A valid prompt card",
        body="Summarize {{topic}} concisely.\n",
    )
    assert good_path.is_file()

    # One malformed file in the same notes dir — non-UTF-8 binary content
    # that makes parse_frontmatter raise UnicodeDecodeError. Per ADR-751,
    # prompt cards live in <vault>/knowledge/notes/ alongside other note types; the
    # scanner must skip malformed files there without aborting.
    notes_dir = vault_dir / "knowledge" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    malformed = notes_dir / "broken.md"
    malformed.write_bytes(b"\xff\xfe\x00\x01\x80\x81 not utf-8 \xc3\x28")

    monkeypatch.setattr(paths, "_vault_home_dir", lambda: vault_dir)
    paths.invalidate_project_cache()

    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()

    # Must not raise.
    count = index_prompts(get_project_root(), rag_dir)
    assert count > 0

    prompts_dir_out = rag_dir / "prompts"
    vault_entries = _read_entries_by_source(prompts_dir_out, "vault")
    names = {entry.get("name") for entry in vault_entries}
    assert "good-prompt" in names, "the well-formed vault prompt must still be indexed"
    assert "broken" not in names, "the malformed vault prompt must be skipped"

"""Tests for prompt_cards — pure-logic helpers for user-saved prompts."""
from __future__ import annotations

from skills.ingest.scripts.prompt_cards import (
    compute_prompt_hash,
    extract_placeholders,
    find_existing_prompt_card,
    slugify_label,
    write_prompt_card,
)
from src.lib.frontmatter_utils import parse_frontmatter


def test_slugify_label_is_filesystem_safe():
    assert slugify_label("Define a Goal!") == "define-a-goal"
    assert slugify_label("  Multi   Space  ") == "multi-space"


def test_extract_placeholders_dedupes_preserving_order():
    body = "Given my {{goal}} and {{constraints}}, refine {{goal}}."
    assert extract_placeholders(body) == ["goal", "constraints"]


def test_extract_placeholders_empty_when_none():
    assert extract_placeholders("plain prompt, no slots") == []


def test_compute_prompt_hash_is_stable_and_content_sensitive():
    assert compute_prompt_hash("abc") == compute_prompt_hash("abc")
    assert compute_prompt_hash("abc") != compute_prompt_hash("abd")
    assert compute_prompt_hash("abc").startswith("sha256:")


def test_write_prompt_card_persists_under_notes_dir(tmp_path):
    path = write_prompt_card(
        vault_dir=tmp_path,
        label="Define a Goal",
        description="Define then act on a goal",
        body="State your {{goal}} clearly.",
        source_url="https://example.com/goal-prompt",
    )
    assert path.parent == tmp_path / "knowledge" / "notes"
    # naming spec 2026-06-12 Wave 3: date-free slug from label (max 6 words)
    assert not path.stem[0].isdigit(), f"name must not start with date digit: {path.name}"
    assert "define-a-goal" in path.name
    meta, body = parse_frontmatter(path)
    assert meta["id"] == "define-a-goal"
    assert meta["label"] == "Define a Goal"
    assert meta["icon"] == "MessageSquare"
    assert meta["source_url"] == "https://example.com/goal-prompt"
    assert meta["x-augur-note-type"] == "prompt"
    assert meta["x-augur-prompt-triggerable"] is True
    assert meta["placeholders"] == ["goal"]
    assert "State your {{goal}} clearly." in body


def test_find_existing_prompt_card_matches_by_content_hash(tmp_path):
    path = write_prompt_card(
        vault_dir=tmp_path, label="Reusable", description="d",
        body="reuse {{x}}", source_url="",
    )
    meta, _ = parse_frontmatter(path)
    assert "source_url" not in meta
    content_hash = compute_prompt_hash("reuse {{x}}")
    found = find_existing_prompt_card(tmp_path, content_hash)
    assert found is not None and found.parent == tmp_path / "knowledge" / "notes"
    assert find_existing_prompt_card(tmp_path, "sha256:deadbeef") is None

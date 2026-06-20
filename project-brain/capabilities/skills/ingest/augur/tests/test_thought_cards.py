"""Tests for thought_cards pure-logic helpers."""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
THOUGHT_CARDS_PATH = (
    PROJECT_ROOT
    / "project-brain"
    / "capabilities"
    / "skills"
    / "ingest"
    / "scripts"
    / "thought_cards.py"
)


def _load_thought_cards():
    spec = importlib.util.spec_from_file_location(
        "ingest_thought_cards",
        THOUGHT_CARDS_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_thought_cards"] = module
    spec.loader.exec_module(module)
    return module


def test_slugify_thought_is_filesystem_safe():
    tc = _load_thought_cards()
    assert tc.slugify_thought("  Notes Zone: Why it works!  ") == "notes-zone-why-it-works"


def test_write_thought_card_persists_under_notes_dir(tmp_path: Path):
    tc = _load_thought_cards()
    path = tc.write_thought_card(
        vault_dir=tmp_path,
        title="Notes Zone Verification",
        body="One canonical capture zone keeps browsing and commands aligned.",
        captured_at=datetime(2026, 5, 16, 12, 0, tzinfo=UTC),
    )

    assert path.parent == tmp_path / "knowledge" / "notes"
    # naming spec 2026-06-12 Wave 3: date-free slug from title (max 6 words)
    assert path.name == "notes-zone-verification.md"
    meta, body = parse_frontmatter(path)
    assert meta["title"] == "Notes Zone Verification"
    assert meta["source_type"] == "thought"
    assert meta["x-augur-note-type"] == "thought"
    assert meta["content_hash"].startswith("sha256:")
    assert meta["tags"] == ["thought"]
    assert "One canonical capture zone" in body


def test_find_existing_thought_card_matches_by_content_hash(tmp_path: Path):
    tc = _load_thought_cards()
    path = tc.write_thought_card(vault_dir=tmp_path, body="keep this thought")
    meta, _ = parse_frontmatter(path)

    assert tc.find_existing_thought_card(tmp_path, meta["content_hash"]) == path
    assert tc.find_existing_thought_card(tmp_path, "sha256:deadbeef") is None

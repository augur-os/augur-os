"""Tests for src.lib.brain_layout (per-brain layout resolution)."""

from pathlib import Path

from src.lib.brain_layout import (
    MACHINE_DIR,
    MACHINE_TOP_DIRS,
    brain_capture_dir,
    brain_knowledge_dir,
    brain_layout,
    brain_notes_root,
    brain_sources_dir,
    brain_wiki_dir,
    is_machine_path,
    join_brain_relative,
    vault_machine_dir,
)


def _make_brain(tmp_path: Path, layout: str | None) -> Path:
    body = "schema_version: 1\nid: t\ntype: personal\n"
    if layout:
        body += f"layout: {layout}\n"
    (tmp_path / "BRAIN.yaml").write_text(body, encoding="utf-8")
    return tmp_path


def test_layout_defaults_to_knowledge(tmp_path):
    root = _make_brain(tmp_path, None)
    assert brain_layout(root) == "knowledge"


def test_layout_missing_brain_yaml_is_knowledge(tmp_path):
    assert brain_layout(tmp_path) == "knowledge"


def test_domains_layout_paths(tmp_path):
    root = _make_brain(tmp_path, "domains")
    assert brain_layout(root) == "domains"
    assert brain_notes_root(root) == root
    assert brain_capture_dir(root) == root / "inbox"
    assert brain_knowledge_dir(root) == root / MACHINE_DIR / "knowledge"
    assert brain_wiki_dir(root) == root / "wiki"
    assert brain_sources_dir(root) == root / "sources"


def test_knowledge_layout_paths(tmp_path):
    root = _make_brain(tmp_path, None)
    assert brain_notes_root(root) == root / "knowledge" / "notes"
    assert brain_capture_dir(root) == root / "knowledge" / "notes"
    assert brain_knowledge_dir(root) == root / "knowledge"
    assert brain_wiki_dir(root) == root / "knowledge" / "wiki"
    assert brain_sources_dir(root) == root / "knowledge" / "sources"


def test_vault_machine_dir(tmp_path):
    (tmp_path / "d").mkdir()
    domains = _make_brain(tmp_path / "d", "domains")
    assert vault_machine_dir(domains, "drafts") == domains / "_augur" / "drafts"
    (tmp_path / "k").mkdir()
    legacy = _make_brain(tmp_path / "k", None)
    assert vault_machine_dir(legacy, "drafts") == legacy / "drafts"


def test_machine_top_dirs_cover_migrated_machine_config(tmp_path):
    # Invariant: MACHINE_TOP_DIRS mirrors the migration move map
    # (scripts/migrations/vault_reorg_2026_06_12.py TOP_MOVES).
    assert "system" in MACHINE_TOP_DIRS
    assert "integrations" in MACHINE_TOP_DIRS


def test_join_brain_relative_routes_machine_roots(tmp_path):
    (tmp_path / "d").mkdir()
    domains = _make_brain(tmp_path / "d", "domains")
    assert join_brain_relative(domains, Path("system/pins.yaml")) == domains / "_augur" / "system" / "pins.yaml"
    assert (
        join_brain_relative(domains, Path("integrations/github-cli.yaml"))
        == domains / "_augur" / "integrations" / "github-cli.yaml"
    )
    assert join_brain_relative(domains, Path("career/cv.md")) == domains / "career" / "cv.md"
    (tmp_path / "k").mkdir()
    legacy = _make_brain(tmp_path / "k", None)
    assert join_brain_relative(legacy, Path("system/pins.yaml")) == legacy / "system" / "pins.yaml"
    assert (
        join_brain_relative(legacy, Path("integrations/github-cli.yaml")) == legacy / "integrations" / "github-cli.yaml"
    )


def test_is_machine_path(tmp_path):
    root = _make_brain(tmp_path, "domains")
    assert is_machine_path(root, root / "_augur" / "drafts" / "x.md")
    assert is_machine_path(root, root / "SOUL.md")
    assert is_machine_path(root, root / "MEMORY.md")
    assert not is_machine_path(root, root / "career" / "cv.md")
    assert not is_machine_path(root, root / "career" / "interview" / "story-bank.md")
    (tmp_path / "legacy").mkdir()
    legacy = _make_brain(tmp_path / "legacy", None)
    assert is_machine_path(legacy, legacy / "MEMORY.md")

"""Tests for layout-aware capture routing (domains vs knowledge layout).

Verifies that writers land cards in inbox/ (domains) vs knowledge/notes/
(legacy), and that scanners skip _augur/ and symlinked subtrees.
"""
from __future__ import annotations

import os
from pathlib import Path


def _domains_vault(tmp_path: Path) -> Path:
    (tmp_path / "BRAIN.yaml").write_text(
        "schema_version: 1\nid: t\ntype: personal\nlayout: domains\n", encoding="utf-8"
    )
    return tmp_path


def _clear_layout_cache() -> None:
    """Clear brain_layout lru_cache so each test starts clean."""
    from src.lib.brain_layout import brain_layout

    brain_layout.cache_clear()


def test_thought_card_lands_in_inbox(tmp_path: Path) -> None:
    _clear_layout_cache()
    try:
        from thought_cards import write_thought_card

        vault = _domains_vault(tmp_path)
        path = write_thought_card(vault_dir=vault, body="test thought", title="t")
        assert path.parent == vault / "inbox"
    finally:
        _clear_layout_cache()


def test_url_card_lands_in_inbox(tmp_path: Path) -> None:
    _clear_layout_cache()
    try:
        from url_ingest import card_target_path

        vault = _domains_vault(tmp_path)
        target = card_target_path(vault, "https://example.com/a")
        assert target.parent == vault / "inbox"
    finally:
        _clear_layout_cache()


def test_scanner_skips_machine_and_symlinks(tmp_path: Path) -> None:
    """index_vault must skip _augur/ (machine) and symlinked subtrees."""
    _clear_layout_cache()
    try:
        from src.lib.index._scanners_structural import index_vault

        vault = _domains_vault(tmp_path)

        # User domain note — should be indexed.
        (vault / "career").mkdir()
        (vault / "career" / "cv.md").write_text("# cv", encoding="utf-8")

        # Machine path — should be excluded.
        (vault / "_augur" / "drafts").mkdir(parents=True)
        (vault / "_augur" / "drafts" / "junk.md").write_text("x", encoding="utf-8")

        # Symlinked directory — rglob on Python 3.12 does NOT follow symlinked
        # dirs, so doc.md inside the symlink target must NOT appear in results.
        docs = tmp_path.parent / "docs-store"
        (docs / "career").mkdir(parents=True)
        (docs / "career" / "doc.md").write_text("binary-side", encoding="utf-8")
        os.symlink(
            os.path.relpath(docs / "career", vault / "career"),
            vault / "career" / "files",
        )

        rag_dir = tmp_path / "rag"
        count = index_vault(vault, rag_dir, root=tmp_path)

        # Collect all indexed names from rag output files.
        found: set[str] = set()
        if (rag_dir / "vault").is_dir():
            for f in (rag_dir / "vault").rglob("*.md"):
                found.add(f.stem)

        assert "cv" in found, f"cv.md should be indexed; found={found}"
        assert "junk" not in found, f"junk.md (_augur/) should be excluded; found={found}"
        assert "doc" not in found, f"doc.md (symlink target) should be excluded; found={found}"
    finally:
        _clear_layout_cache()


def test_prompt_card_in_domains_vault_is_scanned(tmp_path: Path, monkeypatch) -> None:
    """Capture/scan alignment: a prompt card written to a domains vault's
    inbox/ must surface via both index_prompts and list_prompts."""
    import asyncio
    import json

    from src.config import paths

    _clear_layout_cache()
    try:
        from prompt_cards import write_prompt_card

        vault = tmp_path / "vault"
        vault.mkdir()
        _domains_vault(vault)

        card = write_prompt_card(
            vault_dir=vault,
            label="Domains Prompt",
            description="prompt saved in a domains vault",
            body="Refine {{goal}}.",
        )
        # Writer lands in inbox/ (domains capture dir).
        assert card.parent == vault / "inbox"

        monkeypatch.setattr(paths, "_vault_home_dir", lambda: vault)
        paths.invalidate_project_cache()

        # index_prompts must scan the same capture dir the writer used.
        from src.config.paths import get_project_root
        from src.lib.index._scanners_knowledge import index_prompts

        rag_dir = tmp_path / "rag"
        rag_dir.mkdir()
        count = index_prompts(get_project_root(), rag_dir)
        assert count > 0
        entry_names = {f.stem for f in (rag_dir / "prompts").rglob("*.md")}
        assert "domains-prompt" in entry_names, (
            f"prompt card in domains inbox/ must be indexed; got {entry_names}"
        )

        # list_prompts must surface it too.
        from src.mcp.augur_framework.tools.infrastructure.browse.skills import (
            list_prompts_impl,
        )

        result = json.loads(asyncio.run(list_prompts_impl()))
        vault_items = [i for i in result["items"] if i.get("source") == "vault"]
        assert any(i["title"] == "Domains Prompt" for i in vault_items), (
            f"list_prompts must surface the domains-vault prompt; got {vault_items}"
        )
    finally:
        paths.invalidate_project_cache()
        _clear_layout_cache()

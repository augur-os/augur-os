from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wiki_scanner.py"
SPEC = importlib.util.spec_from_file_location("wiki_scanner_priority_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
wiki_scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki_scanner)


def _make_scanner(tmp_path: Path, **kwargs):
    return wiki_scanner.WikiScanner(
        vault_dir=tmp_path / "vault",
        documents_dir=tmp_path / "documents",
        **kwargs,
    )


def test_scanner_adds_tier_and_weight_to_all_sources(tmp_path: Path) -> None:
    note = tmp_path / "vault" / "notes" / "general" / "thought.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Thought\n\nbody\n", encoding="utf-8")
    old = time.time() - 60 * 60 * 24
    os.utime(note, (old, old))

    sources = _make_scanner(tmp_path).scan()
    matched = [source for source in sources if source["path"] == str(note)]

    assert matched
    assert matched[0]["source_surface"] == "vault"
    assert matched[0]["tier"] == "high"
    assert matched[0]["weight"] == 2.0
    assert all("tier" in source and "weight" in source for source in sources)


def test_frontmatter_wiki_tier_overrides_default(tmp_path: Path) -> None:
    note = tmp_path / "vault" / "notes" / "important.md"
    note.parent.mkdir(parents=True)
    note.write_text("---\nwiki_tier: critical\n---\n# Important\n\nbody\n", encoding="utf-8")
    old = time.time() - 60 * 60 * 24
    os.utime(note, (old, old))

    matched = [source for source in _make_scanner(tmp_path).scan() if source["path"] == str(note)]

    assert matched[0]["tier"] == "critical"
    assert matched[0]["weight"] == 3.0


def test_recent_vault_file_promotes_to_save_events(tmp_path: Path) -> None:
    note = tmp_path / "vault" / "notes" / "recent.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Recent\n\nbody\n", encoding="utf-8")

    matched = [source for source in _make_scanner(tmp_path).scan() if source["path"] == str(note)]

    assert matched[0]["source_surface"] == "save_events"
    assert matched[0]["tier"] == "critical"
    assert matched[0]["weight"] == 3.0


def test_memory_adapter_sources_are_included(tmp_path: Path) -> None:
    memory_dir = tmp_path / ".claude" / "projects" / "-Users-test-Project" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")

    cfg = wiki_scanner.WikiSignalsConfig()
    cfg.client_memory["clients"] = {
        "claude": {
            "enabled": True,
            "path": str(tmp_path / ".claude"),
            "globs": ["projects/*/memory/*.md"],
            "tier": "critical",
        }
    }

    sources = scanner = _make_scanner(tmp_path, signals_config=cfg).scan()
    matched = [source for source in sources if source["path"].endswith("MEMORY.md")]

    assert matched
    assert matched[0]["source_surface"] == "client_memory"
    assert matched[0]["client"] == "claude"
    assert matched[0]["tier"] == "critical"

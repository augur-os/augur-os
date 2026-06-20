"""Auto-generated importability test for wiki_concept_state."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_wiki_concept_state_importable():
    """Verify that wiki_concept_state can be imported without errors."""
    import importlib
    mod = importlib.import_module("wiki_concept_state")
    assert mod is not None


def test_already_bound_sources_must_match_current_compiler_version() -> None:
    from skills.wiki.scripts.wiki_concept_state import (
        COMPILER_VERSION,
        SourceCompileState,
        WikiCompilerState,
        source_is_already_bound,
        source_needs_extraction,
    )

    state = WikiCompilerState()
    state.sources["vault://a.md"] = SourceCompileState(
        checksum="same",
        compiler_version="concept-article-v3",
        generated_at="2026-05-13T10:00:00Z",
        concept_slugs=["example"],
    )

    assert not source_is_already_bound(state, "vault://a.md")
    assert source_needs_extraction(state, "vault://a.md", "same")

    state.sources["vault://a.md"] = SourceCompileState(
        checksum="same",
        compiler_version=COMPILER_VERSION,
        generated_at="2026-05-14T10:00:00Z",
        concept_slugs=["example"],
    )

    assert source_is_already_bound(state, "vault://a.md")


def test_reconcile_state_from_compiled_wiki_recovers_v4_source_bindings(tmp_path: Path) -> None:
    """Existing v4 concept pages can rebuild stale runtime compiler bindings."""
    from skills.wiki.scripts.wiki_concept_models import SourceDescriptor
    from skills.wiki.scripts.wiki_concept_state import (
        COMPILER_VERSION,
        SourceCompileState,
        WikiCompilerState,
        reconcile_state_from_compiled_wiki,
        source_is_already_bound,
        source_needs_extraction,
    )

    wiki_dir = tmp_path / "wiki"
    concept_dir = wiki_dir / "concepts"
    concept_dir.mkdir(parents=True)
    (concept_dir / "existing-concept.md").write_text(
        """---
title: Existing Concept
page_type: concept
sources:
  - vault://a.md
  - vault://missing.md
compiler_version: concept-article-v4
updated: '2026-05-28T12:00:00Z'
---
# Existing Concept

## Compiled truth

Human compiled truth.
""",
        encoding="utf-8",
    )
    state = WikiCompilerState(compiler_version="concept-article-v3")
    state.sources["vault://old-path.md"] = SourceCompileState(
        checksum="old",
        compiler_version="concept-article-v3",
        concept_slugs=[],
    )
    sources = [
        SourceDescriptor(
            source_id="vault://a.md",
            kind="vault",
            title="A",
            source_path="/tmp/a.md",
            checksum="new-checksum",
        )
    ]

    report = reconcile_state_from_compiled_wiki(
        state,
        sources=sources,
        wiki_dir=wiki_dir,
    )

    assert report["state_version_before"] == "concept-article-v3"
    assert report["recovered_sources"] == 1
    assert report["stale_sources_pruned"] == 1
    assert report["recovered_concept_payloads"] == 1
    assert state.compiler_version == COMPILER_VERSION
    assert "vault://old-path.md" not in state.sources
    assert source_is_already_bound(state, "vault://a.md")
    assert not source_needs_extraction(state, "vault://a.md", "new-checksum")
    assert state.sources["vault://a.md"].concept_slugs == ["existing-concept"]
    assert state.extracted_concepts["vault://a.md"][0]["slug"] == "existing-concept"
    assert state.extracted_concepts["vault://a.md"][0]["evidence"][0]["source_id"] == "vault://a.md"


def test_reconciled_state_preserves_existing_pages_during_apply(tmp_path: Path) -> None:
    """Recovered payloads keep future apply runs from pruning existing v4 pages."""
    from skills.wiki.scripts.wiki_concept_compiler import apply_extraction_batch
    from skills.wiki.scripts.wiki_concept_models import SourceDescriptor
    from skills.wiki.scripts.wiki_concept_state import (
        WikiCompilerState,
        reconcile_state_from_compiled_wiki,
    )

    wiki_dir = tmp_path / "wiki"
    concept_dir = wiki_dir / "concepts"
    runtime_dir = tmp_path / "runtime" / "wiki"
    concept_dir.mkdir(parents=True)
    source_ids = [f"vault://source-{index}.md" for index in range(8)]
    concept_path = concept_dir / "existing-concept.md"
    concept_path.write_text(
        """---
title: Existing Concept
page_type: concept
summary: Existing page summary.
sources:
"""
        + "\n".join(f"  - {source_id}" for source_id in source_ids)
        + """
compiler_version: concept-article-v4
updated: '2026-05-28T12:00:00Z'
---
# Existing Concept

## Compiled truth

Original compiled truth survives.

## Timeline
""",
        encoding="utf-8",
    )
    sources = [
        SourceDescriptor(
            source_id=source_id,
            kind="vault",
            title=f"Source {index}",
            source_path=f"/tmp/source-{index}.md",
            checksum=f"checksum-{index}",
        )
        for index, source_id in enumerate(source_ids)
    ]
    state = WikiCompilerState(compiler_version="concept-article-v3")

    reconcile_state_from_compiled_wiki(state, sources=sources, wiki_dir=wiki_dir)
    apply_extraction_batch(
        wiki_dir,
        runtime_dir,
        state,
        sources,
        payloads={},
        timestamp="2026-05-28T12:30:00Z",
    )

    assert concept_path.exists()
    assert "Original compiled truth survives." in concept_path.read_text(encoding="utf-8")

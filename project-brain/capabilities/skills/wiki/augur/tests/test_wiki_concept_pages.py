"""Auto-generated importability test for wiki_concept_pages."""
from __future__ import annotations

from dataclasses import replace
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from skills.wiki.scripts.wiki_concept_merge import MergedConcept
from skills.wiki.scripts.wiki_concept_models import ConceptArticle, ConceptEvidence, ExtractedQuery
from skills.wiki.scripts.wiki_concept_pages import write_concept_pages, write_query_pages


def test_wiki_concept_pages_importable():
    """Verify that wiki_concept_pages can be imported without errors."""
    import importlib
    mod = importlib.import_module("wiki_concept_pages")
    assert mod is not None


def _merged_concept_with_evidence(slug: str) -> MergedConcept:
    return MergedConcept(
        slug=slug,
        title=slug.replace("-", " ").title(),
        summary="This concept explains how durable wiki knowledge stays useful.",
        source_ids=["source-card://alpha"],
        evidence=[
            ConceptEvidence(
                source_id="source-card://alpha",
                quote="Durable wiki pages separate stable synthesis from cited observations.",
                note="Stable synthesis belongs in compiled truth while observations belong in the timeline.",
            )
        ],
        aliases=["Durable Wiki Knowledge"],
        related=["adjacent-concept"],
        queries=[
            ExtractedQuery(
                title=f"How should {slug} be used?",
                slug=f"how-should-{slug}-be-used",
                summary="Use the compiled concept before returning to raw evidence.",
                answer="Read the concept page first, then inspect the cited source card.",
                evidence=[
                    ConceptEvidence(
                        source_id="source-card://alpha",
                        quote="A query page can still cite the source-card evidence directly.",
                        note="Query pages remain compatible with concept article v3.",
                    )
                ],
                source_ids=["source-card://alpha"],
                related=[slug],
            )
        ],
        article=ConceptArticle(
            core_thesis="The stable thesis belongs in compiled truth.",
            source_synthesis="The page knows how to separate human-owned synthesis from machine-owned observations.",
            key_dimensions=["Compiled truth is human-editable.", "Timeline entries cite their source."],
            recent_shifts=["Concept pages now use ADR-740 v4 structure."],
            open_tensions=["Automated updates must not overwrite human edits."],
            how_to_use="Use the page as the current synthesis before reading source cards.",
            boundaries="The page is bounded by the sources currently compiled.",
            open_questions=["Which source should supersede stale timeline entries?"],
        ),
    )


def test_write_concept_pages_creates_v4_compiled_truth_and_timeline(tmp_path: Path) -> None:
    concept = _merged_concept_with_evidence("compiled-truth-test")

    written = write_concept_pages(tmp_path, [concept], timestamp="2026-05-14T10:00:00Z")

    assert written == [tmp_path / "concepts" / "compiled-truth-test.md"]
    text = (tmp_path / "concepts" / "compiled-truth-test.md").read_text(encoding="utf-8")
    assert "compiler_version: concept-article-v4" in text
    assert "## Compiled truth" in text
    assert "### Current Thesis" in text
    assert "### What This Page Knows" in text
    assert "## Timeline" in text
    assert "_at: 2026-05-14T10:00:00Z" in text
    assert "_source: source-card://alpha" in text
    assert "## Evidence" not in text


def test_write_concept_pages_preserves_existing_compiled_truth_without_duplicate_timeline(
    tmp_path: Path,
) -> None:
    concept = _merged_concept_with_evidence("preserve-human-truth")
    first = write_concept_pages(tmp_path, [concept], timestamp="2026-05-14T10:00:00Z")
    assert first
    target = tmp_path / "concepts" / "preserve-human-truth.md"
    original = target.read_text(encoding="utf-8")
    human_edited = original.replace(
        "### Current Thesis\n\nThe stable thesis belongs in compiled truth.",
        "### Current Thesis\n\nHuman-edited thesis.",
    )
    target.write_text(human_edited, encoding="utf-8")

    second = write_concept_pages(tmp_path, [concept], timestamp="2026-05-15T10:00:00Z")

    assert second == [target]
    updated = target.read_text(encoding="utf-8")
    assert "Human-edited thesis." in updated
    assert "The stable thesis belongs in compiled truth." not in updated
    assert "_at: 2026-05-14T10:00:00Z" in updated
    assert "_at: 2026-05-15T10:00:00Z" not in updated
    assert updated.count("_source: source-card://alpha") == 1


def test_write_concept_pages_appends_only_new_timeline_observations(tmp_path: Path) -> None:
    concept = _merged_concept_with_evidence("append-new-only")
    assert write_concept_pages(tmp_path, [concept], timestamp="2026-05-14T10:00:00Z")
    expanded = replace(
        concept,
        source_ids=["source-card://alpha", "source-card://beta"],
        evidence=[
            *concept.evidence,
            ConceptEvidence(
                source_id="source-card://beta",
                quote="A second cited observation should be appended once.",
                note="A second cited observation should be appended once.",
            ),
        ],
    )

    assert write_concept_pages(tmp_path, [expanded], timestamp="2026-05-15T10:00:00Z")

    updated = (tmp_path / "concepts" / "append-new-only.md").read_text(encoding="utf-8")
    assert updated.count("_source: source-card://alpha") == 1
    assert updated.count("_source: source-card://beta") == 1
    assert "_at: 2026-05-15T10:00:00Z  _source: source-card://beta" in updated


def test_write_concept_pages_does_not_dedupe_against_malformed_timeline_entry(
    tmp_path: Path,
) -> None:
    concept = _merged_concept_with_evidence("malformed-existing-entry")
    assert write_concept_pages(tmp_path, [concept], timestamp="2026-05-14T10:00:00Z")
    target = tmp_path / "concepts" / "malformed-existing-entry.md"
    text = target.read_text(encoding="utf-8")
    target.write_text(text.replace("_at: 2026-05-14T10:00:00Z", "_at: not-a-timestamp"), encoding="utf-8")

    assert write_concept_pages(tmp_path, [concept], timestamp="2026-05-15T10:00:00Z")

    updated = target.read_text(encoding="utf-8")
    assert "_at: not-a-timestamp  _source: source-card://alpha" in updated
    assert "_at: 2026-05-15T10:00:00Z  _source: source-card://alpha" in updated


def test_write_concept_pages_dedupe_survives_malformed_timeline_bullet(
    tmp_path: Path,
) -> None:
    concept = _merged_concept_with_evidence("malformed-bullet-entry")
    assert write_concept_pages(tmp_path, [concept], timestamp="2026-05-14T10:00:00Z")
    target = tmp_path / "concepts" / "malformed-bullet-entry.md"
    text = target.read_text(encoding="utf-8")
    target.write_text(text.rstrip() + "\n\n- Missing metadata.\n", encoding="utf-8")

    assert write_concept_pages(tmp_path, [concept], timestamp="2026-05-15T10:00:00Z")

    updated = target.read_text(encoding="utf-8")
    assert updated.count("_source: source-card://alpha") == 1
    assert "- Missing metadata." in updated
    assert "_at: 2026-05-15T10:00:00Z  _source: source-card://alpha" not in updated


def test_write_query_pages_keep_v3_compatible_metadata(tmp_path: Path) -> None:
    concept = _merged_concept_with_evidence("query-compatible")

    written = write_query_pages(
        tmp_path,
        [concept],
        timestamp="2026-05-14T10:00:00Z",
    )

    assert written
    text = (tmp_path / "queries" / "how-should-query-compatible-be-used.md").read_text(encoding="utf-8")
    assert "page_type: query" in text
    assert "compiler_version: concept-article-v3" in text
    assert "## Evidence" in text

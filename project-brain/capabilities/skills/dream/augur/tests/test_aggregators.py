"""Tests for dream-orphans / dream-stale-pages / dream-merge-candidates.

Per Augur skill-test convention (memory: feedback-skill-test-convention), the
target module is loaded via importlib.util.spec_from_file_location, never via
a dotted module path.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "aggregators.py"
_SPEC = importlib.util.spec_from_file_location("dream_aggregators", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)

_FIXTURES_PATH = Path(__file__).resolve().parent / "_fixtures.py"
_FIX_SPEC = importlib.util.spec_from_file_location("dream_test_fixtures", _FIXTURES_PATH)
assert _FIX_SPEC and _FIX_SPEC.loader
_fix = importlib.util.module_from_spec(_FIX_SPEC)
_FIX_SPEC.loader.exec_module(_fix)


@pytest.fixture
def fixture_vault(tmp_path: Path) -> Path:
    return _fix.build_fixture_vault(tmp_path)


@pytest.fixture
def fixture_graph_cache(tmp_path: Path) -> Path:
    return _fix.build_fixture_graph_cache(tmp_path)


# ----------------------------------------------------------------------------
# dream-orphans
# ----------------------------------------------------------------------------


def test_dream_orphans_flags_pages_with_no_inbound_edges_and_low_timeline(
    fixture_vault: Path, fixture_graph_cache: Path
):
    """Pages with 0 inbound edges AND fewer than `max_timeline_entries` timeline
    entries are flagged. Anchor pages with strong inbound edges are not."""
    result = mod.dream_orphans(
        vault_root=fixture_vault,
        cache_root=fixture_graph_cache,
        max_timeline_entries=3,
    )

    flagged_slugs = {entry["slug"] for entry in result["flagged"]}
    # The orphan fixture page has 0 inbound + 1 timeline entry → flagged.
    assert "wiki-orphan" in flagged_slugs
    # The anchor fixture page has 5 inbound edges → not flagged regardless of timeline.
    assert "wiki-anchor" not in flagged_slugs


def test_dream_orphans_is_flag_only_does_not_write(
    fixture_vault: Path, fixture_graph_cache: Path
):
    """dream-orphans must not delete or rewrite any vault file."""
    snapshot = {p: p.stat().st_mtime_ns for p in fixture_vault.rglob("*.md")}
    mod.dream_orphans(
        vault_root=fixture_vault,
        cache_root=fixture_graph_cache,
        max_timeline_entries=3,
    )
    for path, mtime in snapshot.items():
        assert path.exists(), f"{path} was deleted"
        assert path.stat().st_mtime_ns == mtime, f"{path} was rewritten"


def test_dream_orphans_records_inbound_and_timeline_counts(
    fixture_vault: Path, fixture_graph_cache: Path
):
    """Flagged entries must carry the inbound edge + timeline counts for the
    report renderer (dream-report-write) to display."""
    result = mod.dream_orphans(
        vault_root=fixture_vault,
        cache_root=fixture_graph_cache,
        max_timeline_entries=3,
    )

    by_slug = {entry["slug"]: entry for entry in result["flagged"]}
    assert by_slug["wiki-orphan"]["inbound_edges"] == 0
    assert by_slug["wiki-orphan"]["timeline_entries"] == 1


def test_dream_orphans_respects_threshold(
    fixture_vault: Path, fixture_graph_cache: Path
):
    """At threshold=0, every page with at least one timeline entry should
    escape the orphan flag regardless of inbound edges."""
    result = mod.dream_orphans(
        vault_root=fixture_vault,
        cache_root=fixture_graph_cache,
        max_timeline_entries=0,
    )
    assert result["flagged"] == []


def test_dream_orphans_handles_missing_cache_gracefully(
    fixture_vault: Path, tmp_path: Path
):
    """When the graph cache is absent, every page reads as 0 inbound edges; the
    threshold check still gates whether they're flagged."""
    empty_cache = tmp_path / "no-cache"
    result = mod.dream_orphans(
        vault_root=fixture_vault,
        cache_root=empty_cache,
        max_timeline_entries=10,
    )
    # All pages with <10 timeline entries land in the flagged set since cache
    # is absent → every wiki page has 0 inbound.
    flagged_slugs = {entry["slug"] for entry in result["flagged"]}
    assert "wiki-orphan" in flagged_slugs
    assert "wiki-anchor" in flagged_slugs  # even the anchor — no cache means 0 inbound


# ----------------------------------------------------------------------------
# dream-stale-pages
# ----------------------------------------------------------------------------


def test_dream_stale_pages_flags_when_timeline_recent_but_compiled_truth_old(
    fixture_vault: Path,
):
    """A page whose newest timeline _at: is newer than its _last_compiled_at:
    by more than ``gap_days`` is flagged. The wiki-stale fixture has compiled
    truth 60 days old and timeline 1 day old → 59-day gap, flagged at default 14."""
    result = mod.dream_stale_pages(vault_root=fixture_vault, gap_days=14)
    flagged_slugs = {entry["slug"] for entry in result["flagged"]}
    assert "wiki-stale" in flagged_slugs
    # wiki-anchor has fresher compiled truth than timeline → not stale
    assert "wiki-anchor" not in flagged_slugs


def test_dream_stale_pages_records_gap_days(fixture_vault: Path):
    """Flagged entries must carry the gap so the report can sort and display it."""
    result = mod.dream_stale_pages(vault_root=fixture_vault, gap_days=14)
    by_slug = {entry["slug"]: entry for entry in result["flagged"]}
    stale_entry = by_slug["wiki-stale"]
    # 60 days compiled, 1 day newest timeline → gap ~59
    assert stale_entry["gap_days"] >= 50
    assert "latest_timeline_at" in stale_entry
    assert "last_compiled_at" in stale_entry


def test_dream_stale_pages_ignores_pages_without_compiled_at(
    fixture_vault: Path, tmp_path: Path
):
    """A wiki page that has no ``_last_compiled_at:`` frontmatter has no anchor
    point for "is the compiled truth lagging?" — we skip rather than guess."""
    no_compiled = fixture_vault / "wiki" / "wiki-no-compiled.md"
    no_compiled.write_text(
        "---\nslug: wiki-no-compiled\n---\n\n## Compiled Truth\n\nBody.\n\n"
        "## Timeline\n\n- _at: 2026-01-01T00:00:00Z  _source: vault://x.md\n",
        encoding="utf-8",
    )
    result = mod.dream_stale_pages(vault_root=fixture_vault, gap_days=14)
    flagged_slugs = {entry["slug"] for entry in result["flagged"]}
    assert "wiki-no-compiled" not in flagged_slugs


def test_dream_stale_pages_respects_threshold(fixture_vault: Path):
    """At gap_days=0 every page with newer timeline than compiled gets flagged.
    At gap_days=10000 nothing is flagged."""
    high = mod.dream_stale_pages(vault_root=fixture_vault, gap_days=10000)
    assert high["flagged"] == []


# ----------------------------------------------------------------------------
# dream-merge-candidates
# ----------------------------------------------------------------------------


def test_dream_merge_candidates_uses_ingest_concept_merge_similarity(
    fixture_vault: Path,
):
    """The two near-duplicate pages in the fixture share canonical title +
    alias, which exceeds the wiki_concept_merge near-duplicate threshold
    (≥3 shared tokens, ≥0.67 Jaccard). They should appear as one candidate
    pair; the unrelated pages must not."""
    result = mod.dream_merge_candidates(vault_root=fixture_vault)
    pairs = {
        tuple(sorted([entry["left_slug"], entry["right_slug"]]))
        for entry in result["candidates"]
    }
    expected = ("federated-knowledge-graph", "federated-knowledge-graphs")
    assert tuple(sorted(expected)) in pairs
    # The anchor and orphan pages should NOT form a pair with anything.
    for pair in pairs:
        assert "wiki-anchor" not in pair
        assert "wiki-orphan" not in pair


def test_dream_merge_candidates_is_flag_only(fixture_vault: Path):
    """Merge-candidates is a proposal layer; it must not rewrite or delete."""
    snapshot = {p: p.stat().st_mtime_ns for p in fixture_vault.rglob("*.md")}
    mod.dream_merge_candidates(vault_root=fixture_vault)
    for path, mtime in snapshot.items():
        assert path.exists()
        assert path.stat().st_mtime_ns == mtime


def test_dream_merge_candidates_survives_shadowed_top_level_skills_package(
    fixture_vault: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """The aggregator dynamically loads ingest helpers even when another
    test package has already claimed the top-level ``skills`` module."""
    shadow = types.ModuleType("skills")
    shadow.__path__ = ["/tmp/not-augur-skills"]
    monkeypatch.setitem(sys.modules, "skills", shadow)
    monkeypatch.delitem(sys.modules, "_dream_loaded_wiki_concept_merge", raising=False)

    result = mod.dream_merge_candidates(vault_root=fixture_vault)

    pairs = {
        tuple(sorted([entry["left_slug"], entry["right_slug"]]))
        for entry in result["candidates"]
    }
    assert ("federated-knowledge-graph", "federated-knowledge-graphs") in pairs

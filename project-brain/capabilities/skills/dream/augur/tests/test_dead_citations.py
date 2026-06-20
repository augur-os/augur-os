"""Tests for dream-dead-citations (ADR-744 task 5).

Scans every wiki page's `## Timeline` section for `_source:` URIs that resolve
to nothing. Three schemes are handled:

- ``vault://<path>``        → resolved against ``<vault_root>/<path>``
- ``source-card://<id>``    → resolved against ``<vault_root>/source-cards/<id>.md``
- ``graph://<entity_id>``   → resolved against ``edges.jsonl`` in the graph cache
                              (entity is "live" if it appears as src OR dst in any edge)
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dead_citations.py"
_SPEC = importlib.util.spec_from_file_location("dream_dead_citations", _MODULE_PATH)
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


def test_flags_dead_vault_uri(fixture_vault: Path, fixture_graph_cache: Path):
    """The orphan fixture page cites vault://nonexistent-page.md (missing file)."""
    result = mod.dream_dead_citations(
        vault_root=fixture_vault, cache_root=fixture_graph_cache
    )
    flagged = {entry["source_uri"] for entry in result["flagged"]}
    assert "vault://nonexistent-page.md" in flagged


def test_flags_dead_source_card(fixture_vault: Path, fixture_graph_cache: Path):
    """The stale fixture page cites source-card://missing-card (no card file)."""
    result = mod.dream_dead_citations(
        vault_root=fixture_vault, cache_root=fixture_graph_cache
    )
    flagged = {entry["source_uri"] for entry in result["flagged"]}
    assert "source-card://missing-card" in flagged


def test_does_not_flag_live_uris(fixture_vault: Path, fixture_graph_cache: Path):
    """Live vault, source-card, and graph URIs must NOT appear in the flagged set."""
    result = mod.dream_dead_citations(
        vault_root=fixture_vault, cache_root=fixture_graph_cache
    )
    flagged = {entry["source_uri"] for entry in result["flagged"]}
    assert "vault://notes/existing-note.md" not in flagged
    assert "source-card://live-card" not in flagged
    assert "graph://wiki-anchor" not in flagged


def test_records_page_slug_scheme_and_reason(
    fixture_vault: Path, fixture_graph_cache: Path
):
    """Each flagged entry must carry enough provenance for the dream report."""
    result = mod.dream_dead_citations(
        vault_root=fixture_vault, cache_root=fixture_graph_cache
    )
    entries = result["flagged"]
    assert entries, "expected at least one dead-citation entry"
    for entry in entries:
        assert entry["page_slug"]
        assert entry["scheme"] in {"vault", "source-card", "graph"}
        assert entry["reason"] == "missing"
        assert entry["source_uri"].startswith(entry["scheme"] + "://")
        assert entry["timeline_at"]


def test_handles_missing_graph_cache_gracefully(
    fixture_vault: Path, tmp_path: Path
):
    """No cache file means every graph:// URI reads as dead — but the function
    still runs and reports through dead vault:// / source-card:// entries."""
    empty_cache = tmp_path / "empty"
    result = mod.dream_dead_citations(
        vault_root=fixture_vault, cache_root=empty_cache
    )
    flagged_schemes = {entry["scheme"] for entry in result["flagged"]}
    # vault:// dead and source-card:// dead are still detected
    assert "vault" in flagged_schemes
    assert "source-card" in flagged_schemes
    # graph:// URIs all read as dead when cache is empty
    assert "graph" in flagged_schemes

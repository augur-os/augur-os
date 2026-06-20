from pathlib import Path

from src.lib.index.sources import RipgrepSource
from src.lib.index.unified_search import _collect_active_search_hits, _to_rg_pattern

_QUERY = "run-demo-readiness-live-wow"


def _large_notes_folder(tmp_path: Path) -> tuple[Path, Path]:
    """200 early-sorting weak-match fillers + one late-sorting full slug-match.

    Fillers contain only one query term ("demo"), so they match the OR pattern
    (creating collection pressure) but score low. The target matches every term
    in both content and filename, so once collected it scores highest.
    """
    d = tmp_path / "notes"
    d.mkdir()
    for i in range(200):  # many earlier-sorting, weakly-matching files
        (d / f"2026-01-{i:03d}-filler.md").write_text("demo notes\n")
    target = d / "2026-12-31-prompt-run-demo-readiness-live-wow.md"
    target.write_text("run demo readiness live wow\n")
    return d, target


def test_recent_file_in_large_folder_is_collected(tmp_path: Path):
    d, target = _large_notes_folder(tmp_path)
    hits = _collect_active_search_hits(_to_rg_pattern(_QUERY), [d])
    files = {h.get("file", "") for h in hits}
    assert any(str(target) in f for f in files), "newest matching file must reach the candidate pool"


def test_ripgrep_source_collects_deeper_than_limit(tmp_path: Path):
    """Guards the load-bearing fix site (sources.py): RipgrepSource must collect a
    candidate pool deeper than `limit`, else a strong match that sorts late by file
    path is truncated before scoring. With a multi-term query _score_hits ranks the
    full-match target above the weak fillers, so it must appear once collected deep.
    (End-to-end behavior for the hyphenated slug query is covered by the real-data
    verification in the plan — the full pipeline adds BM25 + the basename re-ranker.)"""
    d, target = _large_notes_folder(tmp_path)
    hits = RipgrepSource([d]).search("run demo readiness live wow", limit=50)
    files = {hit.doc_id for hit in hits}
    assert any(str(target) in f for f in files), "late-sorting full-match target must survive RipgrepSource's limit cut"

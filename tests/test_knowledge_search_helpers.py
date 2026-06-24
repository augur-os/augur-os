"""Unit tests for src.lib.knowledge._search_helpers.

Exercises the pure / deterministic search helpers: tokenization, query
intent detection, category mapping, scoring, ranking/dedup, frontmatter
reading, and filename-match scoring. All filesystem access is isolated to
tmp_path; the real vault/index is never touched.
"""

from __future__ import annotations

from pathlib import Path

from src.lib.knowledge._search_helpers import (
    DEFAULT_SCOPES,
    VALID_SCOPES,
    _SearchSource,
    _browse_index_lookup_intent,
    _current_work_intent,
    _dedup_key,
    _document_query_intent,
    _hit_source_path,
    _normalize_filename_query,
    _parse_timestamp,
    _query_terms,
    _rag_index_match_score,
    _rag_relative_category,
    _rank_and_dedup_hits,
    _ranking_score,
    _read_frontmatter,
    _recency_score,
    _tokenize_search_text,
)


# ── constants ─────────────────────────────────────────────────────────────────


def test_scope_constants() -> None:
    assert "memory" in VALID_SCOPES
    assert "rag_index" in VALID_SCOPES
    # Every default scope must be a valid scope.
    assert set(DEFAULT_SCOPES) <= VALID_SCOPES


# ── _hit_source_path ──────────────────────────────────────────────────────────


def test_hit_source_path_prefers_top_level_source_path() -> None:
    hit = {"source_path": "/a/b.md", "file": "/x/y.md"}
    assert _hit_source_path(hit) == "/a/b.md"


def test_hit_source_path_falls_back_to_metadata_then_file() -> None:
    assert _hit_source_path({"metadata": {"source_path": "/m/n.md"}}) == "/m/n.md"
    assert _hit_source_path({"file": "/f.md"}) == "/f.md"
    assert _hit_source_path({"path": "/p.md"}) == "/p.md"
    assert _hit_source_path({}) == ""


# ── tokenization / query helpers ──────────────────────────────────────────────


def test_tokenize_lowercases_and_splits_alnum() -> None:
    assert _tokenize_search_text("Hello, World-42!") == ["hello", "world", "42"]


def test_query_terms_drops_stopwords() -> None:
    assert _query_terms("find the pitch deck for me") == ["pitch", "deck"]


def test_current_work_intent() -> None:
    assert _current_work_intent("what am I working on now") is True
    assert _current_work_intent("history of rome") is False


def test_document_query_intent() -> None:
    assert _document_query_intent("show me the latest deck") is True
    assert _document_query_intent("recent thoughts") is False


# ── _rag_relative_category ────────────────────────────────────────────────────


def test_rag_relative_category_maps_family_dir() -> None:
    assert _rag_relative_category("wiki/concepts/foo.md") == "wiki"
    assert _rag_relative_category("decisions/adr-001.md") == "adrs"
    assert _rag_relative_category("documents/x.md") == "documents"


def test_rag_relative_category_handles_chunks_prefix() -> None:
    assert _rag_relative_category("chunks/skills/foo.md") == "skills"


def test_rag_relative_category_unknown_returns_none() -> None:
    assert _rag_relative_category("totally/unknown/path.md") is None
    assert _rag_relative_category("") is None


# ── _parse_timestamp ──────────────────────────────────────────────────────────


def test_parse_timestamp_iso_with_z_suffix() -> None:
    ts = _parse_timestamp("2026-01-01T00:00:00Z")
    assert isinstance(ts, float)
    # Same instant expressed with explicit offset must match.
    assert ts == _parse_timestamp("2026-01-01T00:00:00+00:00")


def test_parse_timestamp_invalid_and_empty() -> None:
    assert _parse_timestamp("not-a-date") is None
    assert _parse_timestamp("") is None
    assert _parse_timestamp(None) is None


# ── _recency_score ────────────────────────────────────────────────────────────


def test_recency_score_none_is_zero() -> None:
    assert _recency_score(None, True) == 0.0


def test_recency_score_fresh_authoritative() -> None:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).timestamp()
    assert _recency_score(now, True) == 100.0


def test_recency_score_non_authoritative_capped() -> None:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).timestamp()
    # Fresh but non-authoritative is capped at 10.
    assert _recency_score(now, False) == 10.0


def test_recency_score_old_is_zero() -> None:
    from datetime import datetime, timezone

    old = datetime.now(timezone.utc).timestamp() - 200 * 86_400
    assert _recency_score(old, True) == 0.0


# ── _read_frontmatter ─────────────────────────────────────────────────────────


def test_read_frontmatter_parses_yaml(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text("---\ntitle: Hello\ncount: 3\n---\nbody\n", encoding="utf-8")
    meta = _read_frontmatter(str(md))
    assert meta["title"] == "Hello"
    assert meta["count"] == 3


def test_read_frontmatter_non_markdown_returns_empty(tmp_path: Path) -> None:
    txt = tmp_path / "doc.txt"
    txt.write_text("---\ntitle: x\n---\n", encoding="utf-8")
    assert _read_frontmatter(str(txt)) == {}


def test_read_frontmatter_no_frontmatter_returns_empty(tmp_path: Path) -> None:
    md = tmp_path / "plain.md"
    md.write_text("just text, no frontmatter\n", encoding="utf-8")
    assert _read_frontmatter(str(md)) == {}


def test_read_frontmatter_missing_file_returns_empty(tmp_path: Path) -> None:
    assert _read_frontmatter(str(tmp_path / "nope.md")) == {}


# ── _normalize_filename_query / _browse_index_lookup_intent ───────────────────


def test_normalize_filename_query_strips_quotes_and_lowercases() -> None:
    assert _normalize_filename_query("  'My File.PDF' ") == "my file.pdf"
    assert _normalize_filename_query("a\\b") == "a/b"


def test_browse_index_lookup_intent_detects_paths_and_extensions() -> None:
    assert _browse_index_lookup_intent("folder/file.md") is True
    assert _browse_index_lookup_intent("report-2026-01-15") is True
    assert _browse_index_lookup_intent("my-long-file-name") is True
    assert _browse_index_lookup_intent("document.pdf") is True


def test_browse_index_lookup_intent_rejects_short_or_prose() -> None:
    assert _browse_index_lookup_intent("short") is False  # < 8 chars
    assert _browse_index_lookup_intent("what is the meaning") is False


# ── _rag_index_match_score ────────────────────────────────────────────────────


def test_rag_index_match_score_exact_filename_match(tmp_path: Path) -> None:
    index_path = tmp_path / "quarterly-report.md"
    score = _rag_index_match_score("quarterly-report.md", {}, index_path)
    # Full normalized equality against index_path.name -> 500.
    assert score == 500.0


def test_rag_index_match_score_substring_match(tmp_path: Path) -> None:
    index_path = tmp_path / "2026-quarterly-report-final.md"
    score = _rag_index_match_score("quarterly-report", {}, index_path)
    assert score >= 250.0


def test_rag_index_match_score_no_match_is_zero(tmp_path: Path) -> None:
    index_path = tmp_path / "unrelated.md"
    assert _rag_index_match_score("quarterly-report", {}, index_path) == 0.0


# ── _ranking_score ────────────────────────────────────────────────────────────


def test_ranking_score_rewards_basename_term_hits() -> None:
    hit_match = {"file": "/x/quarterly.md", "content": "the quarterly report"}
    hit_nomatch = {"file": "/x/random.md", "content": "unrelated content"}
    assert _ranking_score(hit_match, "quarterly") > _ranking_score(hit_nomatch, "quarterly")


def test_ranking_score_penalizes_meta_paths() -> None:
    normal = {"file": "/x/doc.md", "content": "alpha"}
    meta = {"file": "/x/_meta/doc.md", "content": "alpha"}
    assert _ranking_score(meta, "alpha") < _ranking_score(normal, "alpha")


def test_ranking_score_rag_scope_bonus() -> None:
    base = {"file": "/x/doc.md", "content": "alpha", "score": 1.0}
    rag = {"file": "/x/doc.md", "content": "alpha", "score": 1.0, "scope": "rag"}
    assert _ranking_score(rag, "alpha") == _ranking_score(base, "alpha") + 3.0


# ── _dedup_key / _rank_and_dedup_hits ─────────────────────────────────────────


def test_dedup_key_prefers_source_path() -> None:
    assert _dedup_key({"source_path": "/a.md", "file": "/b.md"}) == "/a.md"
    assert _dedup_key({"file": "/b.md"}) == "/b.md"
    assert _dedup_key({"doc_id": "id-1"}) == "id-1"


def test_rank_and_dedup_removes_duplicate_source_paths() -> None:
    hits = [
        {"file": "/x/a.md", "source_path": "/real/a.md", "content": "alpha alpha"},
        {"file": "/x/a-copy.md", "source_path": "/real/a.md", "content": "alpha"},
        {"file": "/x/b.md", "source_path": "/real/b.md", "content": "beta"},
    ]
    result = _rank_and_dedup_hits(hits, "alpha", limit=10)
    source_paths = [_dedup_key(h) for h in result]
    # The duplicate /real/a.md must appear only once.
    assert source_paths.count("/real/a.md") == 1
    assert "/real/b.md" in source_paths


def test_rank_and_dedup_respects_limit() -> None:
    hits = [
        {"file": f"/x/{i}.md", "source_path": f"/real/{i}.md", "content": "alpha"}
        for i in range(5)
    ]
    result = _rank_and_dedup_hits(hits, "alpha", limit=2)
    assert len(result) == 2


# ── _SearchSource dataclass ───────────────────────────────────────────────────


def test_search_source_defaults_and_frozen() -> None:
    src = _SearchSource(path=Path("/tmp/x"))
    assert src.brain_id is None
    assert src.search_kind == "source"
    src2 = _SearchSource(path=Path("/tmp/x"), brain_id="b1", brain_tier="project")
    assert src2.brain_id == "b1"
    assert src2.brain_tier == "project"

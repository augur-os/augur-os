"""Determinism contract for `_collect_rg_hits`.

`_collect_rg_hits` runs ripgrep with a fast PARALLEL walk (no `--sort path`)
and reproduces the deterministic ordering in Python by sorting hits on
(path, line) before applying the `max_hits` cutoff. These tests pin that
contract — ordering must be path-sorted, stable across runs, and the cutoff
must keep the sorted prefix — so retrieval and ADR-742 eval replay stay
reproducible even though ripgrep itself emits matches in parallel order.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.index.unified_search import _collect_rg_hits, _rg_binary

pytestmark = pytest.mark.skipif(_rg_binary() is None, reason="ripgrep not installed")


def _make_corpus(root: Path) -> None:
    # Created in deliberately non-alphabetical order to prove we sort, not
    # rely on filesystem/walk order.
    (root / "c.md").write_text("needle one\nneedle two\n", encoding="utf-8")
    (root / "a.md").write_text("needle alpha\n", encoding="utf-8")
    (root / "b.md").write_text("filler\nneedle beta\n", encoding="utf-8")
    (root / "sub").mkdir()
    (root / "sub" / "d.md").write_text("needle deep\n", encoding="utf-8")


def _seq(hits: list[dict]) -> list[tuple[str, int]]:
    return [(h["file"], int(h["line"])) for h in hits]


def test_rg_hits_are_path_then_line_sorted(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    hits = _collect_rg_hits("needle", [], [tmp_path], max_hits=100)
    seq = _seq(hits)
    assert seq == sorted(seq), f"hits not (path, line) sorted: {seq}"
    # All five matches present (c.md contributes two lines).
    assert len(seq) == 5


def test_rg_hits_deterministic_across_runs(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    first = _seq(_collect_rg_hits("needle", [], [tmp_path], max_hits=100))
    second = _seq(_collect_rg_hits("needle", [], [tmp_path], max_hits=100))
    assert first == second


def test_max_hits_keeps_deterministic_sorted_prefix(tmp_path: Path) -> None:
    _make_corpus(tmp_path)
    full = _seq(_collect_rg_hits("needle", [], [tmp_path], max_hits=100))
    capped = _seq(_collect_rg_hits("needle", [], [tmp_path], max_hits=2))
    assert capped == full[:2], "cutoff must keep the path-sorted prefix"

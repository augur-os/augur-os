"""Unit tests for src.lib.knowledge._ripgrep (RipgrepMixin).

Targets the module's own logic in isolation -- command construction, ripgrep
--json parsing, the timeout/no-rg error paths, and the pure-Python fallback
search -- by instantiating a minimal concrete subclass of the mixin and
mocking the subprocess invocation.

These complement (not duplicate) the skill-side
project-brain/.../test_search_hardening.py tests, which exercise
``_ripgrep_search`` only through the full ``MemorySearcher`` and never assert
on the command built, the early no-path return, the TimeoutExpired branch, the
FileNotFoundError -> fallback dispatch, or ``_fallback_search`` directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

import pytest

from src.lib.knowledge._ripgrep import RipgrepMixin


class _Searcher(RipgrepMixin):
    """Minimal concrete host for the mixin under test."""


@pytest.fixture
def searcher() -> _Searcher:
    return _Searcher()


def _match_line(path: str, line_number: int, content: str, submatches=None) -> str:
    """Build one ripgrep ``--json`` 'match' record."""
    return json.dumps(
        {
            "type": "match",
            "data": {
                "path": {"text": path},
                "line_number": line_number,
                "lines": {"text": content},
                "submatches": submatches if submatches is not None else [],
            },
        }
    )


# ---------------------------------------------------------------------------
# Early exit: nonexistent path
# ---------------------------------------------------------------------------


def test_returns_empty_when_path_missing(searcher, tmp_path):
    """A path that does not exist short-circuits to [] without invoking rg."""
    missing = tmp_path / "nope"
    with patch("src.lib.knowledge._ripgrep.subprocess_run") as mock_run:
        result = searcher._ripgrep_search("anything", missing)
    assert result == []
    mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# Command construction
# ---------------------------------------------------------------------------


def test_command_includes_json_case_insensitive_and_context(searcher, tmp_path):
    """Default invocation builds: rg --json -i -C <n> <escaped-query> <path>."""
    target = tmp_path / "notes"
    target.mkdir()
    with patch("src.lib.knowledge._ripgrep.subprocess_run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=1)
        searcher._ripgrep_search("hello", target, context_lines=3)

    cmd = mock_run.call_args.args[0]
    assert cmd[0] == "rg"
    assert "--json" in cmd
    assert "-i" in cmd
    # -C must be immediately followed by the stringified context count.
    assert cmd[cmd.index("-C") + 1] == "3"
    # Query and path are the final two positional args.
    assert cmd[-2] == "hello"
    assert cmd[-1] == str(target)


def test_command_omits_case_flag_when_case_sensitive(searcher, tmp_path):
    """case_insensitive=False drops the -i flag."""
    target = tmp_path / "notes"
    target.mkdir()
    with patch("src.lib.knowledge._ripgrep.subprocess_run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=1)
        searcher._ripgrep_search("hello", target, case_insensitive=False)
    cmd = mock_run.call_args.args[0]
    assert "-i" not in cmd


def test_command_omits_context_flag_when_zero(searcher, tmp_path):
    """context_lines<=0 drops the -C flag entirely."""
    target = tmp_path / "notes"
    target.mkdir()
    with patch("src.lib.knowledge._ripgrep.subprocess_run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=1)
        searcher._ripgrep_search("hello", target, context_lines=0)
    cmd = mock_run.call_args.args[0]
    assert "-C" not in cmd


def test_query_regex_metacharacters_are_escaped(searcher, tmp_path):
    """Regex metacharacters in the query are re.escape'd before reaching rg.

    Prevents a user query like ``a.b*`` from being interpreted as a pattern.
    """
    target = tmp_path / "notes"
    target.mkdir()
    with patch("src.lib.knowledge._ripgrep.subprocess_run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=1)
        searcher._ripgrep_search("a.b*c(", target)
    cmd = mock_run.call_args.args[0]
    passed_query = cmd[-2]
    # The literal dot/star/paren must be backslash-escaped, not raw.
    assert "\\." in passed_query
    assert "\\(" in passed_query
    assert passed_query != "a.b*c("


def test_subprocess_called_with_capture_and_timeout(searcher, tmp_path):
    """rg is run captured, in text mode, with a finite timeout."""
    target = tmp_path / "notes"
    target.mkdir()
    with patch("src.lib.knowledge._ripgrep.subprocess_run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=1)
        searcher._ripgrep_search("hello", target)
    kwargs = mock_run.call_args.kwargs
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["timeout"] == 30


# ---------------------------------------------------------------------------
# JSON match parsing
# ---------------------------------------------------------------------------


def test_parses_match_and_normalizes_path(searcher, tmp_path):
    """A match record yields normalized absolute path, line, stripped content."""
    real_file = tmp_path / "doc.md"
    real_file.write_text("some content\n")
    target = tmp_path
    out = _match_line(str(real_file), 7, "  matched text  ", submatches=[{"start": 0}])

    with patch("src.lib.knowledge._ripgrep.subprocess_run") as mock_run:
        mock_run.return_value = MagicMock(stdout=out, returncode=0)
        results = searcher._ripgrep_search("matched", target)

    assert len(results) == 1
    r = results[0]
    # _normalize_path resolves to the absolute, symlink-free form.
    assert r["path"] == str(real_file.resolve())
    assert r["line_number"] == 7
    assert r["content"] == "matched text"  # whitespace stripped
    assert r["submatches"] == [{"start": 0}]


def test_ignores_non_match_record_types(searcher, tmp_path):
    """Only type=='match' records are collected; begin/end/context skipped."""
    target = tmp_path
    begin = json.dumps({"type": "begin", "data": {"path": {"text": "/x.md"}}})
    end = json.dumps({"type": "end", "data": {}})
    match = _match_line("/x.md", 1, "keep me")
    out = "\n".join([begin, match, end])

    with patch("src.lib.knowledge._ripgrep.subprocess_run") as mock_run:
        mock_run.return_value = MagicMock(stdout=out, returncode=0)
        results = searcher._ripgrep_search("keep", target)

    assert len(results) == 1
    assert results[0]["content"] == "keep me"


def test_skips_malformed_lines_keeps_valid(searcher, tmp_path):
    """Invalid JSON lines are skipped; valid matches still returned."""
    target = tmp_path
    valid = _match_line("/x.md", 2, "valid")
    out = f"garbage not json\n{valid}\ntrailing{{"

    with patch("src.lib.knowledge._ripgrep.subprocess_run") as mock_run:
        mock_run.return_value = MagicMock(stdout=out, returncode=0)
        results = searcher._ripgrep_search("valid", target)

    assert len(results) == 1
    assert results[0]["content"] == "valid"


def test_blank_path_falls_back_to_raw(searcher, tmp_path):
    """When path text is empty, _normalize_path(\"\")-> falls back to raw value.

    _normalize_path('') resolves to cwd (truthy), so the result is a string,
    never None -- the ``or raw_path`` guard keeps the key present.
    """
    target = tmp_path
    out = _match_line("", 1, "content")
    with patch("src.lib.knowledge._ripgrep.subprocess_run") as mock_run:
        mock_run.return_value = MagicMock(stdout=out, returncode=0)
        results = searcher._ripgrep_search("content", target)
    assert len(results) == 1
    assert results[0]["path"] is not None


def test_empty_stdout_yields_no_matches(searcher, tmp_path):
    """Empty rg output (no matches) returns []."""
    target = tmp_path
    with patch("src.lib.knowledge._ripgrep.subprocess_run") as mock_run:
        mock_run.return_value = MagicMock(stdout="   \n  ", returncode=1)
        results = searcher._ripgrep_search("nomatch", target)
    assert results == []


# ---------------------------------------------------------------------------
# Error paths: timeout, rg-not-found -> fallback
# ---------------------------------------------------------------------------


def test_timeout_returns_empty_and_logs(searcher, tmp_path):
    """TimeoutExpired is caught, [] returned, warning logged."""
    target = tmp_path
    with patch("src.lib.knowledge._ripgrep.subprocess_run", side_effect=TimeoutExpired("rg", 30)):
        with patch("src.lib.knowledge._ripgrep.logger") as mock_logger:
            results = searcher._ripgrep_search("slow", target)
    assert results == []
    assert mock_logger.warning.called


def test_missing_rg_dispatches_to_fallback(searcher, tmp_path):
    """FileNotFoundError (rg binary absent) routes to _fallback_search."""
    target = tmp_path
    sentinel = [{"path": "/x", "line_number": 1, "content": "fb", "submatches": []}]
    with patch("src.lib.knowledge._ripgrep.subprocess_run", side_effect=FileNotFoundError):
        with patch.object(searcher, "_fallback_search", return_value=sentinel) as mock_fb:
            results = searcher._ripgrep_search("q", target)
    mock_fb.assert_called_once_with("q", target)
    assert results is sentinel


# ---------------------------------------------------------------------------
# _fallback_search: pure-Python search
# ---------------------------------------------------------------------------


def test_fallback_searches_single_file(searcher, tmp_path):
    """When path is a file, only that file is scanned, line-by-line."""
    f = tmp_path / "single.md"
    f.write_text("first line\nsecond NEEDLE line\nthird line\n")
    results = searcher._fallback_search("needle", f)

    assert len(results) == 1
    r = results[0]
    assert r["line_number"] == 2
    assert r["content"] == "second NEEDLE line"
    assert r["path"] == str(f.resolve())
    assert r["submatches"] == []


def test_fallback_is_case_insensitive(searcher, tmp_path):
    """Fallback matching ignores case (re.IGNORECASE)."""
    f = tmp_path / "a.md"
    f.write_text("Augur is Local-First\n")
    results = searcher._fallback_search("LOCAL-FIRST", f)
    assert len(results) == 1
    assert results[0]["line_number"] == 1


def test_fallback_escapes_query_metacharacters(searcher, tmp_path):
    """Query metacharacters are treated literally, not as regex."""
    f = tmp_path / "a.md"
    f.write_text("version 1.2.3 shipped\nversion 1x2y3 noise\n")
    # As a regex, '1.2.3' would match '1x2y3'; escaped, it must not.
    results = searcher._fallback_search("1.2.3", f)
    assert len(results) == 1
    assert results[0]["line_number"] == 1


def test_fallback_recurses_markdown_only(searcher, tmp_path):
    """Directory scan globs **/*.md and skips non-markdown files."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "top.md").write_text("alpha TARGET\n")
    (tmp_path / "sub" / "nested.md").write_text("beta\nTARGET deep\n")
    (tmp_path / "ignore.txt").write_text("TARGET in txt\n")

    results = searcher._fallback_search("target", tmp_path)

    found_paths = {Path(r["path"]).name for r in results}
    assert "top.md" in found_paths
    assert "nested.md" in found_paths
    # Non-markdown file is excluded by the **/*.md glob.
    assert "ignore.txt" not in found_paths
    assert len(results) == 2


def test_fallback_multiple_matches_in_one_file(searcher, tmp_path):
    """Every matching line in a file produces a result with its line number."""
    f = tmp_path / "multi.md"
    f.write_text("hit one\nmiss\nhit two\nhit three\n")
    results = searcher._fallback_search("hit", f)
    assert [r["line_number"] for r in results] == [1, 3, 4]


def test_fallback_skips_unreadable_files(searcher, tmp_path):
    """A file that raises on read is skipped; other files still scanned."""
    good = tmp_path / "good.md"
    good.write_text("MATCH here\n")
    bad = tmp_path / "bad.md"
    bad.write_text("MATCH there\n")

    real_read_text = Path.read_text

    def flaky_read_text(self, *args, **kwargs):
        if self.name == "bad.md":
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "boom")
        return real_read_text(self, *args, **kwargs)

    with patch.object(Path, "read_text", flaky_read_text):
        results = searcher._fallback_search("match", tmp_path)

    names = {Path(r["path"]).name for r in results}
    assert names == {"good.md"}


def test_fallback_no_match_returns_empty(searcher, tmp_path):
    """No matching lines yields an empty list."""
    f = tmp_path / "a.md"
    f.write_text("nothing relevant here\n")
    assert searcher._fallback_search("absent", f) == []

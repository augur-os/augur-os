"""Tests for ci_failure_analyzer.py — traceback parsing and bug report creation."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import ci_failure_analyzer as cfa


# ---------------------------------------------------------------------------
# parse_traceback
# ---------------------------------------------------------------------------


class TestParseTraceback:
    def test_extracts_file_and_line(self):
        log = (
            'Traceback (most recent call last):\n'
            f'  File "{Path.cwd()}/plugins/dev/scripts/foo.py", line 42, in main\n'
            '    raise ValueError("bad")\n'
            'ValueError: bad\n'
        )
        fpath, lineno, err = cfa.parse_traceback(log)
        assert fpath is not None
        assert lineno == 42
        assert "ValueError" in err

    def test_returns_none_when_no_traceback(self):
        log = "Everything is fine. No errors here."
        fpath, lineno, err = cfa.parse_traceback(log)
        assert fpath is None
        assert lineno is None

    def test_ignores_site_packages(self):
        log = (
            '  File "/usr/lib/python3.11/site-plugins/requests/api.py", line 10, in get\n'
            '    return session.request()\n'
            'ConnectionError: failed\n'
        )
        fpath, lineno, err = cfa.parse_traceback(log)
        # site-plugins paths are filtered, but /usr/lib paths are also filtered
        assert fpath is None

    def test_picks_last_candidate(self):
        cwd = str(Path.cwd())
        log = (
            f'  File "{cwd}/src/lib/utils.py", line 10, in helper\n'
            '    process()\n'
            f'  File "{cwd}/plugins/dev/scripts/main.py", line 25, in run\n'
            '    call_api()\n'
            'RuntimeError: API down\n'
        )
        fpath, lineno, err = cfa.parse_traceback(log)
        assert lineno == 25  # Last candidate wins
        assert "RuntimeError" in err


# ---------------------------------------------------------------------------
# run_gh_command
# ---------------------------------------------------------------------------


class TestRunGhCommand:
    @patch.object(cfa, "_run_command")
    def test_returns_stdout_on_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="output data", returncode=0)
        result = cfa.run_gh_command(["run", "view", "123"])
        assert result == "output data"

    @patch.object(cfa, "_run_command")
    def test_returns_none_on_failure(self, mock_run):
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "gh", stderr="not found")
        result = cfa.run_gh_command(["run", "view", "999"])
        assert result is None


# ---------------------------------------------------------------------------
# create_backlog_item
# ---------------------------------------------------------------------------


class TestCreateBacklogItem:
    @patch("src.config.paths.get_runtime_dir")
    def test_creates_bug_file(self, mock_runtime, tmp_path):
        mock_runtime.return_value = tmp_path

        result = cfa.create_backlog_item(
            run_id="12345",
            job_name="test-job",
            fpath="src/lib/foo.py",
            lineno=42,
            err="ValueError: bad",
            content="x = 1/0",
        )

        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "12345" in content
        assert "ValueError: bad" in content
        assert "src/lib/foo.py" in content

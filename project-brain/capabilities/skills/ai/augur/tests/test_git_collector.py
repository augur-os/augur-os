"""Tests for the git signal collector."""

import sys
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts" / "ops" / "agent_digest")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import pytest

from collect_git_signals import (
    collect,
    match_patterns,
    parse_git_diff_files,
)


@pytest.fixture
def patterns() -> list[dict]:
    return [
        {"id": "rule_11_no_fs", "regex": r"import\s+(fs|\{\s*readFile)", "scope": "apps/dashboard/", "directive": "no_fs_in_dashboard"},
        {"id": "rule_5_no_suppression", "regex": r"(@ts-ignore|eslint-disable|@pytest\.mark\.skip)", "scope": None, "directive": "no_suppression"},
    ]


def test_match_fs_import(patterns):
    diff_line = "+import fs from 'node:fs'"
    file_path = "apps/dashboard/lib/utils.ts"
    matches = match_patterns(diff_line, file_path, patterns)
    assert len(matches) == 1
    assert matches[0]["directive"] == "no_fs_in_dashboard"


def test_match_readfile_import(patterns):
    diff_line = "+import { readFile } from 'fs/promises'"
    file_path = "apps/dashboard/api/route.ts"
    matches = match_patterns(diff_line, file_path, patterns)
    assert len(matches) == 1
    assert matches[0]["directive"] == "no_fs_in_dashboard"


def test_no_match_outside_scope(patterns):
    diff_line = "+import fs from 'node:fs'"
    file_path = "scripts/build.ts"
    matches = match_patterns(diff_line, file_path, patterns)
    assert len(matches) == 0


def test_match_ts_ignore(patterns):
    diff_line = "+// @ts-ignore"
    file_path = "src/lib/helper.ts"
    matches = match_patterns(diff_line, file_path, patterns)
    assert len(matches) == 1
    assert matches[0]["directive"] == "no_suppression"


def test_no_match_removed_line(patterns):
    diff_line = "-import fs from 'node:fs'"
    file_path = "apps/dashboard/lib/utils.ts"
    matches = match_patterns(diff_line, file_path, patterns)
    assert len(matches) == 0


def test_parse_git_diff_files():
    diff_output = """diff --git a/apps/dashboard/lib/utils.ts b/apps/dashboard/lib/utils.ts
--- a/apps/dashboard/lib/utils.ts
+++ b/apps/dashboard/lib/utils.ts
@@ -1,3 +1,4 @@
+import fs from 'node:fs'
 export function util() {}"""
    files = parse_git_diff_files(diff_output)
    assert "apps/dashboard/lib/utils.ts" in files


def test_parse_git_diff_files_handles_missing_stdout():
    assert parse_git_diff_files(None) == {}


def test_collect_skips_diff_entries_with_missing_stdout(tmp_path, monkeypatch):
    patterns_path = tmp_path / "patterns.yaml"
    patterns_path.write_text(
        "patterns:\n"
        "  - id: rule_11_no_fs\n"
        "    regex: \"import\\\\s+(fs|\\\\{\\\\s*readFile)\"\n"
        "    scope: \"apps/dashboard/\"\n"
        "    directive: no_fs_in_dashboard\n"
    )

    class Result:
        def __init__(self, stdout: str | None, returncode: int = 0):
            self.stdout = stdout
            self.returncode = returncode

    calls = {"count": 0}
    kwargs_seen = []

    def fake_run(*args, **kwargs):
        calls["count"] += 1
        kwargs_seen.append(kwargs)
        if calls["count"] == 1:
            return Result("abc123\n")
        return Result(None)

    monkeypatch.setattr("collect_git_signals.subprocess.run", fake_run)

    events = collect(tmp_path, patterns_path)

    assert events == []
    assert all(kwargs["text"] for kwargs in kwargs_seen)
    assert all(kwargs["encoding"] == "utf-8" for kwargs in kwargs_seen)
    assert all(kwargs["errors"] == "replace" for kwargs in kwargs_seen)

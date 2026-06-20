"""Tests for hunt_silent_failures.py — silent-failure pattern detection in diffs.

Note: the bare-except / empty-catch snippets below are inert fixture data fed
to the diff scanner to verify it FLAGS those patterns — they are never
executed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import hunt_silent_failures as hsf  # noqa: E402


class TestIsCodeFile:
    def test_code_files(self):
        assert hsf._is_code_file("main.py") is True
        assert hsf._is_code_file("component.tsx") is True
        assert hsf._is_code_file("deploy.sh") is True

    def test_non_code_files(self):
        assert hsf._is_code_file("README.md") is False
        assert hsf._is_code_file("data.json") is False


class TestParseAddedEntries:
    def test_basic_diff(self):
        diff = (
            "diff --git a/main.py b/main.py\n"
            "+++ b/main.py\n"
            "@@ -10,0 +11,3 @@\n"
            "+    try:\n"
            "+        do_thing()\n"
            "+    except:\n"
        )
        entries = hsf._parse_added_entries(diff)
        assert len(entries) == 3
        assert entries[0]["file"] == "main.py"
        assert entries[0]["line"] == 11

    def test_ignores_non_code_files(self):
        diff = (
            "diff --git a/README.md b/README.md\n"
            "+++ b/README.md\n"
            "@@ -1,0 +2,1 @@\n"
            "+except:\n"
        )
        assert hsf._parse_added_entries(diff) == []


class TestScanSilentFailures:
    def test_flags_bare_except_as_high(self):
        entries = [{"file": "a.py", "line": 5, "text": "    except:"}]
        findings = hsf._scan_silent_failures(entries)
        assert any(f["severity"] == "high" for f in findings)

    def test_flags_except_pass(self):
        entries = [{"file": "a.py", "line": 5, "text": "    except ValueError: pass"}]
        findings = hsf._scan_silent_failures(entries)
        assert any("Silent exception" in f["message"] for f in findings)

    def test_flags_empty_js_catch(self):
        entries = [{"file": "a.ts", "line": 9, "text": "catch (e) {}"}]
        findings = hsf._scan_silent_failures(entries)
        assert any(f["severity"] == "high" for f in findings)

    def test_clean_lines_produce_no_findings(self):
        entries = [{"file": "a.py", "line": 1, "text": "value = compute(x)"}]
        assert hsf._scan_silent_failures(entries) == []


class TestCli:
    def test_help_exits_zero(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "hunt_silent_failures.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0
        assert "--commit" in proc.stdout

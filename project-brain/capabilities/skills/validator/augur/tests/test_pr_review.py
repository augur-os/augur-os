"""Tests for pr_review.py — heuristic local PR-style review.

Note: the `os.system(...)` / `shell=True` strings below are inert fixture
data fed to the diff analyzer to verify it FLAGS those patterns — they are
never executed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pr_review  # noqa: E402


class TestParseAddedEntries:
    def test_basic_diff(self):
        diff = (
            "diff --git a/main.py b/main.py\n"
            "+++ b/main.py\n"
            "@@ -10,0 +11,2 @@\n"
            "+import os\n"
            "+os.system('boom')\n"
        )
        entries = pr_review._parse_added_entries(diff)
        assert len(entries) == 2
        assert entries[0]["file"] == "main.py"
        assert entries[0]["line"] == 11
        assert entries[1]["line"] == 12

    def test_ignores_non_code_files(self):
        diff = (
            "diff --git a/README.md b/README.md\n"
            "+++ b/README.md\n"
            "@@ -1,0 +2,1 @@\n"
            "+except:\n"
        )
        assert pr_review._parse_added_entries(diff) == []


class TestAnalyzeFindings:
    def test_flags_shell_true_as_high_security(self):
        entries = [{"file": "run.py", "line": 3, "text": "subprocess.run(cmd, shell=True)"}]
        findings = pr_review._analyze_findings(["run.py", "tests/test_run.py"], entries)
        assert any(f["severity"] == "high" and f["category"] == "security" for f in findings)

    def test_flags_code_without_tests(self):
        findings = pr_review._analyze_findings(["src/feature.py"], [])
        assert any(f["category"] == "testing" for f in findings)

    def test_clean_diff_with_tests_has_no_findings(self):
        entries = [{"file": "src/feature.py", "line": 1, "text": "x = compute(y)"}]
        findings = pr_review._analyze_findings(
            ["src/feature.py", "tests/test_feature.py"], entries
        )
        assert findings == []


class TestSummarizeGates:
    def test_high_security_finding_fails_security_gate(self):
        findings = [{"severity": "high", "category": "security", "message": "m"}]
        gates = pr_review._summarize_gates(findings)
        assert gates["security"]["status"] == "FAIL"

    def test_no_findings_passes_all_gates(self):
        gates = pr_review._summarize_gates([])
        assert all(g["status"] == "PASS" for g in gates.values())


class TestCli:
    def test_help_exits_zero(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "pr_review.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0
        assert "--commit" in proc.stdout

    def test_reviews_head_of_this_repo(self):
        repo_root = Path(__file__).resolve().parents[6]
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "pr_review.py"), "--commit", "HEAD", "--path", str(repo_root)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        report = json.loads(proc.stdout)
        assert report["verdict"] in {"APPROVE", "REQUEST_CHANGES"}
        assert "findings" in report and "gates" in report

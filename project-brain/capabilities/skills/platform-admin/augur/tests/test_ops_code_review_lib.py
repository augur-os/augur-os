"""Tests for platform-admin/scripts/ops/code_review_lib.py — shared code-review helpers."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

# Import the module under test
import importlib.util
import sys

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "code_review_lib.py"
SPEC = importlib.util.spec_from_file_location("code_review_lib_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
sys.modules["code_review_lib_under_test"] = mod
SPEC.loader.exec_module(mod)

CODE_REVIEW_DIFFICULTY_SPEC = mod.CODE_REVIEW_DIFFICULTY_SPEC
_git_changed_files = mod._git_changed_files
_git_diff_stat = mod._git_diff_stat
_lint_targets = mod._lint_targets
_needs_tsc_check = mod._needs_tsc_check
_run_lint_check = mod._run_lint_check
_run_tsc_check = mod._run_tsc_check
_snapshot_changed_files = mod._snapshot_changed_files
fix_code_review = mod.fix_code_review
scan_code_review = mod.scan_code_review


# ---------------------------------------------------------------------------
# _git_diff_stat
# ---------------------------------------------------------------------------

class TestGitDiffStat:
    @patch("code_review_lib_under_test.subprocess.run")
    def test_returns_stdout_on_success(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="  3 files changed\n")
        result = _git_diff_stat(tmp_path)
        assert result == "3 files changed"
        mock_run.assert_called_once()

    @patch("code_review_lib_under_test.subprocess.run")
    def test_returns_empty_on_failure(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stdout="error")
        assert _git_diff_stat(tmp_path) == ""

    @patch("code_review_lib_under_test.subprocess.run")
    def test_extended_mode_uses_head_tilde(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="diff\n")
        _git_diff_stat(tmp_path, extended=True)
        cmd = mock_run.call_args[0][0]
        assert "HEAD~3" in cmd


# ---------------------------------------------------------------------------
# _git_changed_files
# ---------------------------------------------------------------------------

class TestGitChangedFiles:
    @patch("code_review_lib_under_test.subprocess.run")
    def test_returns_file_list(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="a.ts\nb.tsx\n")
        result = _git_changed_files(tmp_path)
        assert result == ["a.ts", "b.tsx"]

    @patch("code_review_lib_under_test.subprocess.run")
    def test_returns_empty_list_on_failure(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=128, stdout="")
        assert _git_changed_files(tmp_path) == []

    @patch("code_review_lib_under_test.subprocess.run")
    def test_strips_blank_lines(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="a.ts\n\n  \nb.ts\n")
        result = _git_changed_files(tmp_path)
        assert result == ["a.ts", "b.ts"]


# ---------------------------------------------------------------------------
# _lint_targets
# ---------------------------------------------------------------------------

class TestLintTargets:
    def test_returns_empty_for_none(self, tmp_path):
        assert _lint_targets(tmp_path, None) == []

    def test_returns_empty_for_empty_set(self, tmp_path):
        assert _lint_targets(tmp_path, set()) == []

    def test_filters_to_lintable_suffixes(self, tmp_path):
        (tmp_path / "a.ts").write_text("x")
        (tmp_path / "b.py").write_text("x")
        (tmp_path / "c.tsx").write_text("x")
        result = _lint_targets(tmp_path, {"a.ts", "b.py", "c.tsx"})
        assert "a.ts" in result
        assert "c.tsx" in result
        assert "b.py" not in result

    def test_skips_nonexistent_files(self, tmp_path):
        result = _lint_targets(tmp_path, {"missing.ts"})
        assert result == []


# ---------------------------------------------------------------------------
# _needs_tsc_check
# ---------------------------------------------------------------------------

class TestNeedsTscCheck:
    def test_false_for_none(self):
        assert _needs_tsc_check(None) is False

    def test_false_for_empty(self):
        assert _needs_tsc_check(set()) is False

    def test_true_for_ts_file(self):
        assert _needs_tsc_check({"component.ts"}) is True

    def test_true_for_tsx_file(self):
        assert _needs_tsc_check({"page.tsx"}) is True

    def test_true_for_trigger_file(self):
        assert _needs_tsc_check({"tsconfig.json"}) is True

    def test_false_for_irrelevant(self):
        assert _needs_tsc_check({"readme.md", "style.css"}) is False


# ---------------------------------------------------------------------------
# _snapshot_changed_files
# ---------------------------------------------------------------------------

class TestSnapshotChangedFiles:
    def test_returns_dirty_files_from_snapshot(self):
        ctx = OpsContext(shared_snapshot={"git_dirty_files": ["a.py", "b.ts"]})
        assert _snapshot_changed_files(ctx) == ["a.py", "b.ts"]

    def test_returns_empty_when_no_snapshot(self):
        ctx = OpsContext(shared_snapshot={})
        assert _snapshot_changed_files(ctx) == []

    def test_returns_empty_when_snapshot_not_dict(self):
        ctx = OpsContext(shared_snapshot="not a dict")
        assert _snapshot_changed_files(ctx) == []

    def test_filters_blank_entries(self):
        ctx = OpsContext(shared_snapshot={"git_dirty_files": ["a.py", "", "  "]})
        assert _snapshot_changed_files(ctx) == ["a.py"]


# ---------------------------------------------------------------------------
# scan_code_review
# ---------------------------------------------------------------------------

class TestScanCodeReview:
    def test_no_changes_returns_info(self, tmp_path):
        ctx = OpsContext(project_root=tmp_path, difficulty=1)
        result = scan_code_review(
            ctx,
            git_changed_files=lambda *a, **kw: [],
            git_diff_stat=lambda *a, **kw: "",
            run_tsc_check=lambda *a, **kw: [],
            run_lint_check=lambda *a, **kw: [],
            snapshot_changed_files=lambda c: [],
            needs_tsc_check=lambda p: False,
        )
        assert isinstance(result, ScanResult)
        assert result.severity == "info"
        assert result.issues == []

    def test_d0_surface_only_classifies(self, tmp_path):
        ctx = OpsContext(project_root=tmp_path, difficulty=0)
        result = scan_code_review(
            ctx,
            git_changed_files=lambda *a, **kw: [],
            git_diff_stat=lambda *a, **kw: "",
            run_tsc_check=lambda *a, **kw: [],
            run_lint_check=lambda *a, **kw: [],
            snapshot_changed_files=lambda c: ["apps/dashboard/x.ts", "src/lib.py"],
            needs_tsc_check=lambda p: False,
        )
        assert "surface review" in result.summary
        assert "2 files" in result.summary

    def test_d1_with_lint_errors(self, tmp_path):
        dashboard = tmp_path / "apps" / "dashboard"
        dashboard.mkdir(parents=True)
        ctx = OpsContext(project_root=tmp_path, difficulty=1)
        result = scan_code_review(
            ctx,
            git_changed_files=lambda *a, **kw: ["apps/dashboard/page.tsx"],
            git_diff_stat=lambda *a, **kw: "1 file",
            run_tsc_check=lambda d: [],
            run_lint_check=lambda d, changed_paths=None: [{"rule": "no-unused-vars"}],
            snapshot_changed_files=lambda c: [],
            needs_tsc_check=lambda p: False,
        )
        assert result.severity == "warning"
        assert len(result.issues) == 1


# ---------------------------------------------------------------------------
# fix_code_review
# ---------------------------------------------------------------------------

class TestFixCodeReview:
    def test_dry_run(self, tmp_path):
        ctx = OpsContext(project_root=tmp_path, dry_run=True)
        result = fix_code_review(ctx, [{"tsc_errors": [], "lint_errors": []}])
        assert isinstance(result, FixResult)
        assert result.success is True
        assert "Dry run" in result.summary

    @patch("code_review_lib_under_test.write_report")
    def test_writes_report(self, mock_write, tmp_path):
        mock_write.return_value = tmp_path / "report.json"
        ctx = OpsContext(project_root=tmp_path)
        issues = [{"changed_files": ["a.ts"], "diff_stat": "", "tsc_errors": [], "lint_errors": [{"rule": "x"}]}]
        result = fix_code_review(ctx, issues)
        assert result.success is True
        mock_write.assert_called_once()


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

def test_difficulty_spec_has_all_levels():
    for level in range(5):
        assert level in CODE_REVIEW_DIFFICULTY_SPEC

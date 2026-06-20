"""Tests for auto-self-heal ops module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_test_ctx


def _ctx(tmp_path: Path, **kwargs) -> OpsContext:
    return make_test_ctx(tmp_path, **kwargs)


class TestScanWithoutHealer:
    """Tests when ai_self_healer is not importable."""

    def test_scan_returns_valid_scan_result_when_healer_missing(self, tmp_path: Path):
        from skills.daemon.scripts.ops import self_heal

        with patch.object(self_heal, "healer", None):
            result = self_heal.scan(_ctx(tmp_path))

        assert isinstance(result, ScanResult)
        assert len(result.issues) == 1
        assert result.issues[0]["kind"] == "scanner-defect"
        assert result.severity == "error"
        assert result.health == "broken"
        assert "not importable" in result.summary

    def test_fix_returns_failure_when_healer_missing(self, tmp_path: Path):
        from skills.daemon.scripts.ops import self_heal

        with patch.object(self_heal, "healer", None):
            result = self_heal.fix(_ctx(tmp_path), [{"entry_key": "abc123"}])

        assert isinstance(result, FixResult)
        assert result.success is False
        assert "not importable" in result.summary


class TestScanWithHealer:
    """Tests with a mocked healer adapter."""

    def _make_finding(self, key: str = "test-key", severity: str = "high",
                      message: str = "test error", file: str = "test.py"):
        f = MagicMock()
        f.dedup_key = key
        f.severity = severity
        f.message = message
        f.file = file
        return f

    def test_scan_no_findings_returns_clean(self, tmp_path: Path):
        from skills.daemon.scripts.ops import self_heal

        mock_healer = MagicMock()
        mock_healer.scan_for_errors.return_value = []

        with patch.object(self_heal, "healer", mock_healer):
            result = self_heal.scan(_ctx(tmp_path))

        assert isinstance(result, ScanResult)
        assert result.issues == []
        assert result.severity == "info"
        assert "No runtime errors" in result.summary

    def test_scan_with_findings_returns_issues(self, tmp_path: Path):
        from skills.daemon.scripts.ops import self_heal

        finding = self._make_finding(severity="critical")
        mock_healer = MagicMock()
        mock_healer.scan_for_errors.return_value = [finding]

        with patch.object(self_heal, "healer", mock_healer):
            result = self_heal.scan(_ctx(tmp_path))

        assert len(result.issues) == 1
        assert result.issues[0]["entry_key"] == "test-key"
        assert result.issues[0]["category"] == "import-fixes"
        assert result.severity == "error"

    def test_scan_filters_by_min_severity(self, tmp_path: Path):
        from skills.daemon.scripts.ops import self_heal

        low_finding = self._make_finding(key="low-1", severity="low")
        high_finding = self._make_finding(key="high-1", severity="high")
        mock_healer = MagicMock()
        mock_healer.scan_for_errors.return_value = [low_finding, high_finding]

        ctx = _ctx(tmp_path, config={"min_severity": "high"})
        with patch.object(self_heal, "healer", mock_healer):
            result = self_heal.scan(ctx)

        assert len(result.issues) == 1
        assert result.issues[0]["entry_key"] == "high-1"

    def test_scan_handles_exception_gracefully(self, tmp_path: Path):
        from skills.daemon.scripts.ops import self_heal

        mock_healer = MagicMock()
        mock_healer.scan_for_errors.side_effect = RuntimeError("scan failed")

        with patch.object(self_heal, "healer", mock_healer):
            result = self_heal.scan(_ctx(tmp_path))

        assert isinstance(result, ScanResult)
        assert result.issues == []
        assert "scan raised" in result.summary.lower() or "Healer scan raised" in result.summary


class TestFix:
    """Tests for the fix() function."""

    def test_fix_dry_run_skips_actual_work(self, tmp_path: Path):
        from skills.daemon.scripts.ops import self_heal

        mock_healer = MagicMock()
        with patch.object(self_heal, "healer", mock_healer):
            result = self_heal.fix(
                _ctx(tmp_path, dry_run=True),
                [{"entry_key": "abc"}],
            )

        assert result.success is True
        assert "Dry run" in result.summary
        mock_healer.fix_entry.assert_not_called()

    def test_fix_skips_issues_without_entry_key(self, tmp_path: Path):
        from skills.daemon.scripts.ops import self_heal

        mock_healer = MagicMock()
        with patch.object(self_heal, "healer", mock_healer):
            result = self_heal.fix(_ctx(tmp_path), [{"no_key": True}])

        assert isinstance(result, FixResult)
        mock_healer.fix_entry.assert_not_called()


class TestModuleInterface:
    """Verify the module satisfies the OpsCommand protocol."""

    def test_has_name(self):
        from skills.daemon.scripts.ops import self_heal
        assert self_heal.name == "auto-self-heal"

    def test_has_scan_callable(self):
        from skills.daemon.scripts.ops import self_heal
        assert callable(self_heal.scan)

    def test_has_fix_callable(self):
        from skills.daemon.scripts.ops import self_heal
        assert callable(self_heal.fix)


class TestWorktreeGate:
    """ADR-572: worktree scan is validation-only and fix never mutates."""

    @staticmethod
    def _git(repo: Path, *args: str) -> None:
        import subprocess
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True, capture_output=True, text=True,
        )

    def _make_repo_with_worktree(self, tmp_path: Path) -> tuple[Path, Path]:
        repo = tmp_path / "main"
        repo.mkdir()
        self._git(repo, "init", "-b", "main")
        self._git(repo, "config", "user.name", "Test")
        self._git(repo, "config", "user.email", "test@example.com")
        (repo / "README.md").write_text("hi\n", encoding="utf-8")
        self._git(repo, "add", "README.md")
        self._git(repo, "commit", "-m", "init")
        worktree = tmp_path / "wt-feature"
        self._git(repo, "worktree", "add", "-b", "feature", str(worktree))
        return repo, worktree

    def _make_finding(self):
        f = MagicMock()
        f.dedup_key = "worktree-key"
        f.severity = "high"
        f.message = "worktree dashboard error"
        f.file = "apps/dashboard/app/page.tsx"
        return f

    def test_scan_reports_validation_only_when_project_root_is_a_linked_worktree(self, tmp_path: Path):
        from skills.daemon.scripts.ops import self_heal

        _, worktree = self._make_repo_with_worktree(tmp_path)
        mock_healer = MagicMock()
        mock_healer.scan_for_errors.return_value = [self._make_finding()]
        with patch.object(self_heal, "healer", mock_healer):
            result = self_heal.scan(_ctx(worktree))

        assert isinstance(result, ScanResult)
        assert len(result.issues) == 1
        assert result.issues[0]["entry_key"] == "worktree-key"
        assert result.issues[0]["worktree_validation_only"] is True
        assert result.severity == "warning"
        assert "validation-only worktree mode" in result.summary

    def test_scan_runs_when_project_root_is_main_checkout(self, tmp_path: Path):
        from skills.daemon.scripts.ops import self_heal

        repo, _ = self._make_repo_with_worktree(tmp_path)
        with patch.object(self_heal, "healer", None):
            result = self_heal.scan(_ctx(repo))

        # Healer is None so we hit the existing scanner-defect path,
        # NOT the gate skip — proves gate let it through.
        assert result.severity == "error"
        assert result.health == "broken"

    def test_fix_reports_validation_only_when_project_root_is_a_linked_worktree(self, tmp_path: Path):
        from skills.daemon.scripts.ops import self_heal

        _, worktree = self._make_repo_with_worktree(tmp_path)
        result = self_heal.fix(_ctx(worktree), [{"entry_key": "abc"}])

        assert isinstance(result, FixResult)
        assert result.success is True
        assert result.fix_type == "report"
        assert result.changes == []
        assert result.actions == [
            {
                "entry_key": "abc",
                "skipped": True,
                "reason": "validation-only worktree mode",
            }
        ]
        assert "validation-only" in result.summary

    def test_scan_runs_when_project_root_is_not_a_git_repo(self, tmp_path: Path):
        # Fail-open: non-git scratch dir does not trip the gate.
        from skills.daemon.scripts.ops import self_heal

        with patch.object(self_heal, "healer", None):
            result = self_heal.scan(_ctx(tmp_path))

        assert result.severity == "error"  # hit existing healer-missing path
        assert result.health == "broken"

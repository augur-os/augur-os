"""Tests for auto-git-health scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "git_health.py"
_SPEC = importlib.util.spec_from_file_location("git_health_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-git-health"


def test_scan_not_a_git_repo(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []
    assert "Not a git repo" in result.summary


def test_scan_healthy_size(tmp_path: Path) -> None:
    """scan reports info when .git size is below threshold."""
    (tmp_path / ".git").mkdir()
    with patch.object(mod, "get_dir_size", return_value=50.0):
        result = mod.scan(_ctx(tmp_path))
    assert result.issues == []
    assert result.severity == "info"
    assert "healthy" in result.summary


def test_scan_large_size(tmp_path: Path) -> None:
    """scan reports warning when .git exceeds threshold."""
    (tmp_path / ".git").mkdir()
    with patch.object(mod, "get_dir_size", return_value=500.0):
        result = mod.scan(_ctx(tmp_path))
    assert result.severity == "warning"
    assert "500" in result.summary


def test_fix_dry_run(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path, dry_run=True), [{"action": "git-gc", "size_mb": 100}])
    assert isinstance(result, FixResult)
    assert result.success is True
    assert "Dry run" in result.summary


def test_scan_without_git_optimize_reports_degraded(tmp_path: Path) -> None:
    """A loop that cannot load its dependency must not report green."""
    (tmp_path / ".git").mkdir()
    with patch.object(mod, "get_dir_size", None):
        result = mod.scan(_ctx(tmp_path))
    assert result.issues == []
    assert "not available" in result.summary
    assert result.severity == "warning"
    assert result.health == "degraded"


def test_fix_without_git_optimize(tmp_path: Path) -> None:
    with patch.object(mod, "run_git_gc", None):
        result = mod.fix(_ctx(tmp_path), [{"action": "git-gc", "size_mb": 100}])
    assert result.success is False
    assert "not available" in result.summary


def test_fix_runs_gc_successfully(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    with (
        patch.object(mod, "run_git_gc", return_value=None),
        patch.object(mod, "get_dir_size", side_effect=[200.0, 150.0]),
    ):
        result = mod.fix(_ctx(tmp_path), [{"action": "git-gc", "size_mb": 200}])
    assert result.success is True
    assert "200" in result.summary
    assert "150" in result.summary


def test_fix_handles_gc_exception(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    def exploding_gc(path):
        raise RuntimeError("gc exploded")

    with (
        patch.object(mod, "run_git_gc", exploding_gc),
        patch.object(mod, "get_dir_size", return_value=200.0),
    ):
        result = mod.fix(_ctx(tmp_path), [{"action": "git-gc", "size_mb": 200}])
    assert result.success is False
    assert "failed" in result.summary.lower()

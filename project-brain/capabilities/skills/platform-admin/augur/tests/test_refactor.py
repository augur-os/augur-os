"""Tests for auto-refactor scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "refactor.py"
_SPEC = importlib.util.spec_from_file_location("refactor_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-refactor"


def test_scan_returns_empty(tmp_path: Path) -> None:
    """Scan is a no-op shim."""
    result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []
    assert "no autonomous scanner" in result.summary


def test_fix_dry_run(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path, dry_run=True), [{"detail": "refactor-x"}])
    assert isinstance(result, FixResult)
    assert result.success is True
    assert "Dry run" in result.summary


def test_fix_no_issues(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path), [])
    assert result.success is True
    assert "No refactor issues" in result.summary


def test_fix_queues_issues(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path), [{"detail": "a"}, {"detail": "b"}])
    assert result.success is True
    assert "Queued 2" in result.summary

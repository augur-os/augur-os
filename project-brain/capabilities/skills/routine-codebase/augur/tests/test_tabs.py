"""Tests for auto-tabs scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "tabs.py"
_SPEC = importlib.util.spec_from_file_location("tabs_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-tabs"


def test_scan_returns_empty(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []
    assert "no autonomous scanner" in result.summary


def test_fix_dry_run(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path, dry_run=True), [{"tab": "a"}])
    assert isinstance(result, FixResult)
    assert result.success is True
    assert "Dry run" in result.summary


def test_fix_no_issues(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path), [])
    assert result.success is True
    assert "No tab issues" in result.summary


def test_fix_queues_issues(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path), [{"tab": "a"}, {"tab": "b"}, {"tab": "c"}])
    assert result.success is True
    assert "Queued 3" in result.summary
    assert result.actions[0]["count"] == 3

"""Tests for auto-test-coverage scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "test_coverage_ops.py"
_SPEC = importlib.util.spec_from_file_location("test_coverage_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-test-coverage"


def test_scan_returns_scan_result(tmp_path: Path) -> None:
    """scan delegates to scan_test_coverage."""
    with patch.object(mod, "scan_test_coverage", return_value=ScanResult(issues=[], summary="ok")):
        result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)


def test_fix_returns_fix_result(tmp_path: Path) -> None:
    """fix delegates to fix_test_coverage."""
    with patch.object(mod, "fix_test_coverage", return_value=FixResult(success=True, summary="ok")):
        result = mod.fix(_ctx(tmp_path), [])
    assert isinstance(result, FixResult)


def test_has_difficulty_spec() -> None:
    assert hasattr(mod, "DIFFICULTY_SPEC")
    assert isinstance(mod.DIFFICULTY_SPEC, dict)


def test_has_coverage_threshold() -> None:
    assert hasattr(mod, "_COVERAGE_THRESHOLD")
    assert isinstance(mod._COVERAGE_THRESHOLD, (int, float))

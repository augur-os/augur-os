"""Tests for auto-lint scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "lint.py"
_SPEC = importlib.util.spec_from_file_location("lint_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-lint"


def test_scan_returns_scan_result(tmp_path: Path) -> None:
    """scan delegates to scan_lint."""
    with patch.object(mod, "scan_lint", return_value=ScanResult(issues=[], summary="ok")):
        result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)


def test_fix_returns_fix_result(tmp_path: Path) -> None:
    """fix delegates to fix_lint."""
    with patch.object(mod, "fix_lint", return_value=FixResult(success=True, summary="ok")):
        result = mod.fix(_ctx(tmp_path), [])
    assert isinstance(result, FixResult)


def test_has_difficulty_spec() -> None:
    assert hasattr(mod, "DIFFICULTY_SPEC")
    assert isinstance(mod.DIFFICULTY_SPEC, dict)

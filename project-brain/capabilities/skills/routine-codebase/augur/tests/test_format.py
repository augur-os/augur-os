"""Tests for auto-format scan/fix protocol."""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "format.py"
_SPEC = importlib.util.spec_from_file_location("format_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-format"


def test_scan_no_formatting_issues(tmp_path: Path) -> None:
    """scan reports clean when prettier returns 0."""
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=completed):
        result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []
    assert "No formatting" in result.summary


def test_scan_formatting_issues_found(tmp_path: Path) -> None:
    """scan reports issues when prettier returns non-zero."""
    completed = subprocess.CompletedProcess(args=[], returncode=1, stdout="src/foo.ts\n", stderr="")
    with patch("subprocess.run", return_value=completed):
        result = mod.scan(_ctx(tmp_path))
    assert len(result.issues) == 1
    assert result.severity == "warning"


def test_scan_prettier_not_available(tmp_path: Path) -> None:
    """scan handles missing prettier gracefully."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = mod.scan(_ctx(tmp_path))
    assert result.issues == []
    assert result.health == "broken"


def test_fix_dry_run(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path, dry_run=True), [{"action": "auto-format"}])
    assert isinstance(result, FixResult)
    assert result.success is True
    assert "Dry run" in result.summary

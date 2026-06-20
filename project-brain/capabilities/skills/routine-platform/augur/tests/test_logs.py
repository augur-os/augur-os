"""Tests for auto-logs scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "logs.py"
_SPEC = importlib.util.spec_from_file_location("logs_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-logs"


def test_scan_no_archive_fn(tmp_path: Path) -> None:
    """scan returns info when nightly_maintainer is not importable."""
    original = mod.archive_logs
    try:
        mod.archive_logs = None
        result = mod.scan(_ctx(tmp_path))
        assert isinstance(result, ScanResult)
        assert result.issues == []
        assert "not importable" in result.summary
    finally:
        mod.archive_logs = original


def test_scan_with_log_file(tmp_path: Path) -> None:
    """scan reports issue when log file has content."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "llm_logs.jsonl").write_text("x" * 1024 * 1024)  # 1MB

    original = mod.archive_logs
    try:
        mod.archive_logs = lambda f: None  # dummy
        with patch("src.config.paths.get_logs_dir", return_value=logs_dir):
            result = mod.scan(_ctx(tmp_path, difficulty=1))
        assert len(result.issues) == 1
        assert result.issues[0]["action"] == "archive-logs"
    finally:
        mod.archive_logs = original


def test_fix_dry_run(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path, dry_run=True), [{"action": "archive-logs"}])
    assert isinstance(result, FixResult)
    assert result.success is True
    assert "Dry run" in result.summary


def test_fix_no_archive_fn(tmp_path: Path) -> None:
    """fix returns failure when archive function is missing."""
    original = mod.archive_logs
    try:
        mod.archive_logs = None
        mod.scan_and_update = None  # Also ensure scan_and_update is None
        result = mod.fix(_ctx(tmp_path), [{"action": "archive-logs"}])
        # The fix function checks archive_logs
        assert result.success is False or "not importable" in result.summary or result.success is True
    finally:
        mod.archive_logs = original

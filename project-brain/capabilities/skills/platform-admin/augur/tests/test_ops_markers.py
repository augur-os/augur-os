"""Tests for auto-markers ops module."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_test_ctx

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load_ops_module(module_name: str):
    module_path = SCRIPTS_DIR / "ops" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"_platform_admin_ops_{module_name}",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


markers = _load_ops_module("markers")


def _ctx(tmp_path: Path, **kwargs) -> OpsContext:
    return make_test_ctx(tmp_path, **kwargs)


class TestScan:
    def test_scan_without_scanner_returns_broken_health(self, tmp_path: Path):
        with patch.object(markers, "scan_and_update", None):
            result = markers.scan(_ctx(tmp_path))

        assert isinstance(result, ScanResult)
        assert result.issues == []
        assert result.health == "broken"
        assert "not importable" in result.summary

    def test_scan_d0_with_scanner_returns_verified(self, tmp_path: Path):
        with patch.object(markers, "scan_and_update", lambda: None):
            result = markers.scan(_ctx(tmp_path, difficulty=0))

        assert result.issues == []
        assert result.health == "verified"

    def test_scan_d1_returns_scan_action_when_report_missing(self, tmp_path: Path, monkeypatch):
        with (
            patch.object(markers, "scan_and_update", lambda: None),
            patch.object(markers, "collect_log_positions", return_value={"a.log": 10}),
            patch.object(markers, "scan_all_logs", return_value={"k1": object()}),
            patch.object(markers, "compute_error_fingerprint", return_value="fresh"),
            patch.object(markers, "load_scan_state", return_value={"fingerprint": "stale", "log_positions": {"a.log": 0}}),
        ):
            result = markers.scan(_ctx(tmp_path, difficulty=1))

        assert len(result.issues) == 1
        assert result.issues[0]["action"] == "scan-runtime-markers"
        # d1 should include TODO_BUG, TODO_CLEANUP, FIXME, HACK, XXX
        patterns = result.issues[0]["patterns"]
        assert "TODO_BUG" in patterns
        assert "FIXME" in patterns

    def test_scan_d2_includes_extended_patterns(self, tmp_path: Path, monkeypatch):
        with (
            patch.object(markers, "scan_and_update", lambda: None),
            patch.object(markers, "collect_log_positions", return_value={"a.log": 10}),
            patch.object(markers, "scan_all_logs", return_value={"k1": object()}),
            patch.object(markers, "compute_error_fingerprint", return_value="fresh"),
            patch.object(markers, "load_scan_state", return_value={"fingerprint": "stale", "log_positions": {"a.log": 0}}),
        ):
            result = markers.scan(_ctx(tmp_path, difficulty=2))

        patterns = result.issues[0]["patterns"]
        assert "workaround" in patterns
        assert "DEPRECATED" in patterns

    def test_scan_returns_clean_when_fingerprint_unchanged(self, tmp_path: Path):
        with (
            patch.object(markers, "scan_and_update", lambda: None),
            patch.object(markers, "collect_log_positions", return_value={"a.log": 10}),
            patch.object(markers, "scan_all_logs", return_value={}),
            patch.object(markers, "compute_error_fingerprint", return_value="same"),
            patch.object(markers, "load_scan_state", return_value={"fingerprint": "same", "log_positions": {"a.log": 10}}),
        ):
            result = markers.scan(_ctx(tmp_path, difficulty=1))

        assert result.issues == []
        assert result.health == "verified"
        assert "no new runtime log activity" in result.summary.lower()


class TestFix:
    def test_fix_without_scanner(self, tmp_path: Path):
        with patch.object(markers, "scan_and_update", None):
            result = markers.fix(_ctx(tmp_path), [{"action": "scan-runtime-markers"}])

        assert isinstance(result, FixResult)
        assert result.success is False

    def test_fix_dry_run(self, tmp_path: Path):
        with patch.object(markers, "scan_and_update", lambda: None):
            result = markers.fix(
                _ctx(tmp_path, dry_run=True),
                [{"action": "scan-runtime-markers"}],
            )

        assert result.success is True
        assert "Dry run" in result.summary

    def test_fix_calls_scan_and_update(self, tmp_path: Path):
        mock_scanner = lambda: {"changed": True}
        with patch.object(markers, "scan_and_update", mock_scanner):
            result = markers.fix(_ctx(tmp_path), [{"action": "scan-runtime-markers"}])

        assert result.success is True
        assert "scanned" in result.summary.lower() or "updated" in result.summary.lower()

    def test_fix_handles_scanner_exception(self, tmp_path: Path):
        def failing_scanner():
            raise RuntimeError("scan exploded")

        with patch.object(markers, "scan_and_update", failing_scanner):
            result = markers.fix(_ctx(tmp_path), [{"action": "scan"}])

        assert result.success is False
        assert "failed" in result.summary.lower()

    def test_fix_reports_unchanged_when_fingerprint_same(self, tmp_path: Path):
        with patch.object(markers, "scan_and_update", lambda: {"changed": False}):
            result = markers.fix(_ctx(tmp_path), [{"action": "scan"}])

        assert result.success is True
        assert "unchanged" in result.summary.lower()


class TestModuleInterface:
    def test_has_name(self):
        assert markers.name == "auto-markers"

    def test_has_scan_callable(self):
        assert callable(markers.scan)

    def test_has_fix_callable(self):
        assert callable(markers.fix)

    def test_has_difficulty_spec(self):
        assert 0 in markers.DIFFICULTY_SPEC
        assert 4 in markers.DIFFICULTY_SPEC

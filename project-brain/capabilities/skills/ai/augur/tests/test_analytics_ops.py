"""Tests for ops/analytics.py — LLM usage analytics generation.

Validates the auto-analytics ops command: detecting when analytics need
regeneration based on log freshness, and generating usage summaries from
LLM execution log files.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.lib.ops_protocol import OpsContext

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "analytics.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location("ai_analytics", SCRIPT_PATH)
analytics = importlib.util.module_from_spec(_spec)
sys.modules["ai_analytics"] = analytics
assert _spec.loader is not None
_spec.loader.exec_module(analytics)


def _make_ctx(tmp_path: Path, **overrides) -> OpsContext:
    defaults = {"project_root": tmp_path, "difficulty": 0, "dry_run": False}
    defaults.update(overrides)
    return OpsContext(**defaults)


# ---------------------------------------------------------------------------
# Module-level sanity
# ---------------------------------------------------------------------------


class TestModuleInterface:
    def test_name_attribute(self):
        assert analytics.name == "auto-analytics"

    def test_scan_is_callable(self):
        assert callable(analytics.scan)

    def test_fix_is_callable(self):
        assert callable(analytics.fix)


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------


class TestScan:
    def test_no_log_file_returns_info(self, tmp_path: Path):
        with patch.object(analytics, "get_logs_dir", return_value=tmp_path / "logs"), \
             patch.object(analytics, "get_runtime_dir", return_value=tmp_path / "runtime"):
            ctx = _make_ctx(tmp_path)
            result = analytics.scan(ctx)
            assert result.severity == "info"
            assert result.issues == []
            assert "No LLM logs" in result.summary

    def test_log_exists_no_summary_returns_issue(self, tmp_path: Path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        log_file = logs_dir / "llm_logs.jsonl"
        log_file.write_text(
            json.dumps({"provider": "openai", "cost": 0.01, "total_tokens": 100}) + "\n",
            encoding="utf-8",
        )

        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir()

        with patch.object(analytics, "get_logs_dir", return_value=logs_dir), \
             patch.object(analytics, "get_runtime_dir", return_value=runtime_dir):
            ctx = _make_ctx(tmp_path)
            result = analytics.scan(ctx)
            assert len(result.issues) == 1
            assert result.issues[0]["action"] == "generate-analytics"

    def test_summary_newer_than_log_returns_current(self, tmp_path: Path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        log_file = logs_dir / "llm_logs.jsonl"
        log_file.write_text('{"provider":"test"}\n', encoding="utf-8")

        runtime_dir = tmp_path / "runtime"
        stats_dir = runtime_dir / "stats"
        stats_dir.mkdir(parents=True)
        summary_file = stats_dir / "usage_summary.json"
        # Write summary *after* log
        time.sleep(0.05)
        summary_file.write_text('{"total_requests":1}', encoding="utf-8")

        with patch.object(analytics, "get_logs_dir", return_value=logs_dir), \
             patch.object(analytics, "get_runtime_dir", return_value=runtime_dir):
            ctx = _make_ctx(tmp_path)
            result = analytics.scan(ctx)
            assert result.issues == []
            assert "current" in result.summary.lower()


# ---------------------------------------------------------------------------
# _generate_analytics
# ---------------------------------------------------------------------------


class TestGenerateAnalytics:
    def test_no_log_returns_message(self, tmp_path: Path):
        fake_log = tmp_path / "nonexistent.jsonl"
        with patch("src.config.paths.get_runtime_dir", return_value=tmp_path / "runtime"):
            result = analytics._generate_analytics(fake_log)
            assert "No log file" in result

    def test_valid_log_entries_are_aggregated(self, tmp_path: Path):
        log_file = tmp_path / "llm_logs.jsonl"
        entries = [
            {"provider": "openai", "model": "gpt-4", "cost": 0.05, "total_tokens": 500, "success": True},
            {"provider": "openai", "model": "gpt-4", "cost": 0.03, "total_tokens": 300, "success": True},
            {"provider": "anthropic", "model": "claude", "cost": 0.02, "total_tokens": 200, "success": False},
        ]
        log_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")

        runtime_dir = tmp_path / "runtime"
        with patch("src.config.paths.get_runtime_dir", return_value=runtime_dir):
            result = analytics._generate_analytics(log_file)
            assert "3 requests" in result
            # Verify summary file was written
            summary = runtime_dir / "stats" / "usage_summary.json"
            assert summary.exists()
            data = json.loads(summary.read_text())
            assert data["total_requests"] == 3
            assert data["errors"] == 1

    def test_malformed_lines_are_skipped(self, tmp_path: Path):
        log_file = tmp_path / "llm_logs.jsonl"
        log_file.write_text(
            'not json\n{"provider":"x","cost":0.01,"total_tokens":10}\n',
            encoding="utf-8",
        )

        runtime_dir = tmp_path / "runtime"
        with patch("src.config.paths.get_runtime_dir", return_value=runtime_dir):
            result = analytics._generate_analytics(log_file)
            assert "1 requests" in result


# ---------------------------------------------------------------------------
# Fix
# ---------------------------------------------------------------------------


class TestFix:
    def test_dry_run(self, tmp_path: Path):
        ctx = _make_ctx(tmp_path, dry_run=True)
        result = analytics.fix(ctx, [{"action": "generate-analytics"}])
        assert result.success is True
        assert "Dry run" in result.summary

    def test_fix_calls_generate(self, tmp_path: Path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        log_file = logs_dir / "llm_logs.jsonl"
        log_file.write_text(
            json.dumps({"provider": "test", "cost": 0.0, "total_tokens": 0}) + "\n",
            encoding="utf-8",
        )
        runtime_dir = tmp_path / "runtime"

        with patch("src.config.paths.get_logs_dir", return_value=logs_dir), \
             patch("src.config.paths.get_runtime_dir", return_value=runtime_dir):
            ctx = _make_ctx(tmp_path)
            result = analytics.fix(ctx, [{"action": "generate-analytics"}])
            assert result.success is True
            assert "generated" in result.summary.lower()

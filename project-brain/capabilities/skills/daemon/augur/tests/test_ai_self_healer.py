"""
Tests for AI Self-Healer (ADR-076).

Covers: config loading, scanner (rg + python), dedup registry,
LLM classification, severity routing, TODO creation, headless fix,
fix lock, notifications, CLI modes, and full pipeline integration.
"""
# TODO_CLEANUP: This file is 1765 lines — consider splitting into smaller modules

from __future__ import annotations

import importlib
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Setup import path ──────────────────────────────────────────────────────

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Keep real PyYAML loaded to avoid cross-test pollution.
importlib.import_module("yaml")

import ai_self_healer as healer  # noqa: E402 — must import after sys.modules mock


@pytest.fixture(autouse=True)
def _bind_ai_self_healer_module():
    """Keep lazy imports inside self_heal helpers bound to this module instance."""
    original = sys.modules.get("ai_self_healer")
    sys.modules["ai_self_healer"] = healer
    yield
    if original is None:
        sys.modules.pop("ai_self_healer", None)
    else:
        sys.modules["ai_self_healer"] = original

# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def default_config():
    """Minimal valid config dict."""
    return {
        "enabled": True,
        "scan_interval_minutes": 5,
        "scan_targets": [
            {
                "path": "logs/*.log",
                "patterns": ["ERROR", "FATAL"],
            }
        ],
        "llm": {
            "cli": "auto",
            "classify_flags": ["--print", "--max-turns", "1"],
            "fix_flags": ["--print", "--max-turns", "10"],
            "classify_timeout_s": 30,
            "fix_timeout_s": 300,
        },
        "fix": {
            "max_fix_attempts": 3,
            "complexity_abort_threshold": 7,
            "auto_commit": True,
            "commit_prefix": "fix(self-heal):",
            "log_context_lines": 30,
            "severity_profiles": {
                "critical": {
                    "max_turns": 25,
                    "max_files_modified": 5,
                    "complexity_abort_threshold": 9,
                    "timeout_s": 600,
                },
                "high": {
                    "max_turns": 15,
                    "max_files_modified": 3,
                    "complexity_abort_threshold": 7,
                    "timeout_s": 300,
                },
            },
        },
        "routing": {
            "critical": "fix",
            "high": "fix",
            "medium": "todo",
            "low": "todo",
        },
        "notifications": {
            "on_detect": True,
            "on_fix_start": True,
            "on_fix_success": True,
            "on_fix_failure": True,
            "on_abort": True,
        },
    }


@pytest.fixture
def sample_entry():
    """A sample RegistryEntry."""
    return healer.RegistryEntry(
        dedup_key="abc123",
        message="TypeError: Cannot read property 'map' of undefined",
        file="daemon.stderr.log",
        severity="high",
        category="integration",
        status="new",
        first_seen="2026-02-11T10:00:00",
        last_seen="2026-02-11T10:00:00",
        occurrences=1,
    )


@pytest.fixture
def tmp_runtime(tmp_path):
    """Set up tmp dirs and monkey-patch module paths."""
    logs = tmp_path / "logs"
    logs.mkdir()
    locks = tmp_path / "locks"
    locks.mkdir()

    # Patch module-level paths
    orig_runtime = healer.RUNTIME_DIR
    orig_logs = healer.LOGS_DIR
    orig_registry = healer.REGISTRY_FILE
    orig_tech_debt = healer.TECH_DEBT_FILE
    orig_fix_lock = healer.FIX_LOCK_FILE

    healer.RUNTIME_DIR = tmp_path
    healer.LOGS_DIR = logs
    healer.REGISTRY_FILE = tmp_path / "self_heal_registry.json"
    healer.TECH_DEBT_FILE = tmp_path / "tech_debt.md"
    healer.FIX_LOCK_FILE = locks / "self_heal_fix.lock"

    yield tmp_path

    healer.RUNTIME_DIR = orig_runtime
    healer.LOGS_DIR = orig_logs
    healer.REGISTRY_FILE = orig_registry
    healer.TECH_DEBT_FILE = orig_tech_debt
    healer.FIX_LOCK_FILE = orig_fix_lock


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG LOADING
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigLoading:
    """Tests for load_config and _deep_merge."""

    def test_deep_merge_basic(self):
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 99}, "e": 5}
        result = healer._deep_merge(base, override)
        assert result == {"a": 1, "b": {"c": 99, "d": 3}, "e": 5}

    def test_deep_merge_non_dict_override(self):
        base = {"a": {"nested": True}}
        override = {"a": "replaced"}
        result = healer._deep_merge(base, override)
        assert result["a"] == "replaced"

    @patch.object(healer, "PLUGIN_CONFIG")
    @patch.object(healer, "USER_CONFIG")
    @patch.object(healer, "SCAN_TARGETS_STATE")
    def test_load_config_plugin_only(self, mock_state, mock_user, mock_plugin, tmp_path):
        config_file = tmp_path / "self_heal.yaml"
        config_file.write_text("enabled: true\nscan_interval_minutes: 10\n")

        mock_plugin.exists.return_value = True
        mock_plugin.read_text.return_value = config_file.read_text()
        mock_user.exists.return_value = False
        mock_state.exists.return_value = False

        with patch("yaml.safe_load", return_value={"enabled": True, "scan_interval_minutes": 10}):
            config = healer.load_config()
        assert config["enabled"] is True
        assert config["scan_interval_minutes"] == 10

    @patch.object(healer, "PLUGIN_CONFIG")
    @patch.object(healer, "USER_CONFIG")
    @patch.object(healer, "SCAN_TARGETS_STATE")
    def test_load_config_with_user_override(self, mock_state, mock_user, mock_plugin, tmp_path):
        mock_plugin.exists.return_value = True
        mock_plugin.read_text.return_value = ""
        mock_user.exists.return_value = True
        mock_user.read_text.return_value = ""
        mock_state.exists.return_value = False

        # First call for plugin, second for user
        with patch(
            "yaml.safe_load",
            side_effect=[
                {"enabled": True, "scan_interval_minutes": 5},
                {"scan_interval_minutes": 10},
            ],
        ):
            config = healer.load_config()
        assert config["scan_interval_minutes"] == 10

    @patch.object(healer, "PLUGIN_CONFIG")
    @patch.object(healer, "USER_CONFIG")
    @patch.object(healer, "SCAN_TARGETS_STATE")
    def test_load_config_missing_both(self, mock_state, mock_user, mock_plugin):
        mock_plugin.exists.return_value = False
        mock_user.exists.return_value = False
        mock_state.exists.return_value = False
        config = healer.load_config()
        assert config == {}

    @patch.object(healer, "PLUGIN_CONFIG")
    @patch.object(healer, "USER_CONFIG")
    @patch.object(healer, "SCAN_TARGETS_STATE")
    def test_load_config_loads_scan_targets_from_state(self, mock_state, mock_user, mock_plugin):
        """ADR-466: discovered_scan_targets loaded from state dir, not config."""
        mock_plugin.exists.return_value = False
        mock_user.exists.return_value = False
        mock_state.exists.return_value = True
        mock_state.read_text.return_value = (
            "discovered_scan_targets:\n"
            "- path: logs/test/**/*.log\n"
            "  patterns: [ERROR]\n"
        )

        config = healer.load_config()
        assert len(config.get("discovered_scan_targets", [])) == 1
        assert config["discovered_scan_targets"][0]["path"] == "logs/test/**/*.log"

    @patch.object(healer, "PLUGIN_CONFIG")
    @patch.object(healer, "USER_CONFIG")
    @patch.object(healer, "SCAN_TARGETS_STATE")
    def test_load_config_strips_discovered_from_user_config(self, mock_state, mock_user, mock_plugin):
        """ADR-466: discovered_scan_targets in user config are ignored."""
        mock_plugin.exists.return_value = False
        mock_user.exists.return_value = True
        mock_user.read_text.return_value = (
            "routing:\n  critical: fix\n"
            "discovered_scan_targets:\n"
            "- path: stale/target\n"
        )
        mock_state.exists.return_value = False

        config = healer.load_config()
        assert "discovered_scan_targets" not in config


# ═══════════════════════════════════════════════════════════════════════════════
# SCANNER
# ═══════════════════════════════════════════════════════════════════════════════


class TestScanner:
    """Tests for scan_logs and scan_runtime."""

    def test_generate_dedup_key_deterministic(self):
        key1 = healer._generate_dedup_key("Error at line 42", "app.log")
        key2 = healer._generate_dedup_key("Error at line 42", "app.log")
        assert key1 == key2

    def test_generate_dedup_key_normalizes_numbers(self):
        key1 = healer._generate_dedup_key("Error at line 42", "app.log")
        key2 = healer._generate_dedup_key("Error at line 99", "app.log")
        assert key1 == key2  # Numbers normalized to N

    def test_generate_dedup_key_different_files(self):
        key1 = healer._generate_dedup_key("Error", "a.log")
        key2 = healer._generate_dedup_key("Error", "b.log")
        assert key1 != key2

    def test_generate_dedup_key_collapses_rotated_service_logs(self):
        msg = "[svc] Transient API error [MagicMock] retrying in 4s (WARNING)"
        key1 = healer._generate_dedup_key(msg, "logs/unified_daemon/12-00_57270.log")
        key2 = healer._generate_dedup_key(msg, "logs/unified_daemon/12-00_60521.log")
        assert key1 == key2

    def test_generate_dedup_key_normalizes_hex_and_uuid(self):
        key1 = healer._generate_dedup_key(
            "RuntimeError token=0x7ffabc0011 id=8a4ca129-8b6c-4ca0-bc7e-aab0f4fd83d2",
            "service.log",
        )
        key2 = healer._generate_dedup_key(
            "RuntimeError token=0x9ffdee9999 id=0fd5bb90-0918-42bf-a16b-80a3e73f28ac",
            "service.log",
        )
        assert key1 == key2

    def test_resolve_scan_target_path_maps_runtime_labels(self, tmp_runtime):
        resolved_logs = healer._resolve_scan_target_path("logs/*.log")
        resolved_state = healer._resolve_scan_target_path("state/self_heal_events.jsonl")

        assert resolved_logs == str(healer.LOGS_DIR / "*.log")
        assert resolved_state == str(healer.RUNTIME_DIR / "self_heal_events.jsonl")

    def test_canonical_source_for_dedup_relativizes_external_log_paths(self, tmp_runtime):
        service_dir = healer.LOGS_DIR / "unified_daemon"
        service_dir.mkdir(parents=True, exist_ok=True)
        log_path = service_dir / "12-00_57270.log"
        log_path.write_text("ERROR boom\n")

        source = healer._canonical_source_for_dedup(str(log_path))

        assert source == "logs/unified_daemon"

    def test_scan_logs_finds_errors(self, tmp_path):
        log = tmp_path / "test.log"
        log.write_text("INFO all good\nERROR something broke\nWARN meh\n")

        targets = [{"path": str(log), "patterns": ["ERROR"]}]

        with patch.object(healer, "PROJECT_ROOT", tmp_path):
            findings, watermarks = healer.scan_logs(targets)

        assert len(findings) == 1
        assert "something broke" in findings[0].message

    def test_scan_logs_empty_log(self, tmp_path):
        log = tmp_path / "empty.log"
        log.write_text("")

        targets = [{"path": str(log), "patterns": ["ERROR"]}]
        with patch.object(healer, "PROJECT_ROOT", tmp_path):
            findings, _ = healer.scan_logs(targets)
        assert findings == []

    def test_scan_logs_no_match(self, tmp_path):
        log = tmp_path / "clean.log"
        log.write_text("INFO everything fine\nDEBUG details\n")

        targets = [{"path": str(log), "patterns": ["ERROR", "FATAL"]}]
        with patch.object(healer, "PROJECT_ROOT", tmp_path):
            findings, _ = healer.scan_logs(targets)
        assert findings == []

    def test_scan_logs_multiple_targets(self, tmp_path):
        log1 = tmp_path / "a.log"
        log1.write_text("ERROR first\n")
        log2 = tmp_path / "b.log"
        log2.write_text("FATAL second\n")

        targets = [
            {"path": str(log1), "patterns": ["ERROR"]},
            {"path": str(log2), "patterns": ["FATAL"]},
        ]
        with patch.object(healer, "PROJECT_ROOT", tmp_path):
            findings, _ = healer.scan_logs(targets)
        assert len(findings) == 2

    def test_scan_logs_parses_output(self, tmp_path):
        log = tmp_path / "test.log"
        log.write_text("line 1\nline 2\nline 3\nline 4\nERROR boom\n")

        targets = [{"path": str(log), "patterns": ["ERROR"]}]
        with patch.object(healer, "PROJECT_ROOT", tmp_path):
            findings, _ = healer.scan_logs(targets)

        assert len(findings) == 1
        assert "ERROR boom" in findings[0].message

    def test_scan_logs_uses_runtime_log_mapping(self, tmp_runtime):
        log = healer.LOGS_DIR / "mapped.log"
        log.write_text("ERROR mapped failure\n")

        findings, _ = healer.scan_logs([{"path": "logs/*.log", "patterns": ["ERROR"]}])

        assert len(findings) == 1
        assert findings[0].file == "logs/mapped.log"

    def test_scan_logs_incremental(self, tmp_path):
        """scan_logs should only return NEW lines (watermark-aware)."""
        log = tmp_path / "test.log"
        log.write_text("ERROR first\n")

        targets = [{"path": str(log), "patterns": ["ERROR"]}]
        with patch.object(healer, "PROJECT_ROOT", tmp_path):
            # First scan picks up the error
            findings1, wm1 = healer.scan_logs(targets)
            assert len(findings1) == 1
            # Persist watermarks so second scan sees them
            healer._save_watermarks_atomic(wm1)

            # Second scan with no new content returns nothing
            findings2, _ = healer.scan_logs(targets)
            assert findings2 == []

    @patch.object(healer, "scan_logs")
    def test_scan_runtime_calls_scan_logs(self, mock_scan):
        mock_scan.return_value = ([], {})
        config = {"scan_targets": [{"path": "*.log", "patterns": ["ERROR"]}], "max_log_age_hours": 0}
        healer.scan_runtime(config)
        mock_scan.assert_called_once()

    @patch.object(healer, "check_runtime_prerequisite_health")
    @patch.object(healer, "check_mcp_config_health")
    @patch.object(healer, "scan_logs")
    def test_scan_runtime_includes_mcp_config_findings(
        self,
        mock_scan,
        mock_config_health,
        mock_runtime_health,
    ):
        mock_scan.return_value = ([], {})
        mock_runtime_health.return_value = []
        mock_config_health.return_value = [
            healer.ErrorFinding(
                dedup_key="mcp123",
                message="mcp_config:stale_client_config -- Claude Desktop points to a missing Augur root.",
                file="mcp-config:claudeDesktop",
            )
        ]

        findings = healer.scan_runtime(
            {"scan_targets": [{"path": "*.log", "patterns": ["ERROR"]}], "max_log_age_hours": 0}
        )

        assert [finding.dedup_key for finding in findings] == ["mcp123"]

    def test_runtime_prerequisite_health_reports_missing_project_python(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'augur-test'\n")

        with patch.object(healer, "PROJECT_ROOT", tmp_path):
            findings = healer.check_runtime_prerequisite_health()

        assert len(findings) == 1
        assert findings[0].file == "runtime-prereq:mcp-python"
        assert "mcp_runtime:project_python_missing" in findings[0].message
        assert getattr(findings[0], "severity") == "high"

    def test_runtime_prerequisite_health_reports_missing_dashboard_dependencies(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'augur-test'\n")
        python_path = tmp_path / ".venv" / "bin" / "python3"
        python_path.parent.mkdir(parents=True)
        python_path.write_text("#!/bin/sh\n")
        dashboard = tmp_path / "apps" / "dashboard"
        dashboard.mkdir(parents=True)
        (dashboard / "package.json").write_text('{"name":"dashboard"}\n')

        with patch.object(healer, "PROJECT_ROOT", tmp_path):
            findings = healer.check_runtime_prerequisite_health()

        assert len(findings) == 1
        assert findings[0].file == "runtime-prereq:dashboard"
        assert "Cannot find package 'esbuild'" in findings[0].message
        assert getattr(findings[0], "severity") == "high"

    @patch.object(healer, "check_runtime_prerequisite_health")
    @patch.object(healer, "check_mcp_config_health")
    @patch.object(healer, "scan_logs")
    def test_scan_runtime_includes_runtime_prerequisite_findings(
        self,
        mock_scan,
        mock_config_health,
        mock_runtime_health,
    ):
        mock_scan.return_value = ([], {})
        mock_config_health.return_value = []
        mock_runtime_health.return_value = [
            healer.ErrorFinding(
                dedup_key="runtime123",
                message="mcp_runtime:project_python_missing -- No such file or directory: .venv/bin/python3",
                file="runtime-prereq:mcp-python",
            )
        ]

        findings = healer.scan_runtime(
            {"scan_targets": [{"path": "*.log", "patterns": ["ERROR"]}], "max_log_age_hours": 0}
        )

        assert [finding.dedup_key for finding in findings] == ["runtime123"]

    def test_scan_runtime_no_targets(self):
        assert healer.scan_runtime({}) == []
        assert healer.scan_runtime({"scan_targets": []}) == []

    def test_filter_stale_logs(self, tmp_path):
        """Only files modified within max_age_hours are included."""

        fresh = tmp_path / "fresh.log"
        fresh.write_text("ERROR fresh\n")

        stale = tmp_path / "stale.log"
        stale.write_text("ERROR stale\n")
        # Set mtime to 48 hours ago
        old_time = time.time() - (48 * 3600)
        os.utime(stale, (old_time, old_time))

        targets = [{"path": str(tmp_path / "*.log"), "patterns": ["ERROR"]}]
        with patch.object(healer, "PROJECT_ROOT", tmp_path):
            filtered = healer._filter_stale_logs(targets, max_age_hours=24)

        # Only fresh.log should be included
        assert len(filtered) == 1
        assert "fresh.log" in filtered[0]["path"]

    def test_filter_stale_logs_zero_returns_all(self):
        """max_age_hours=0 disables filtering."""
        targets = [{"path": "*.log", "patterns": ["ERROR"]}]
        result = healer._filter_stale_logs(targets, max_age_hours=0)
        assert result == targets

    def test_scan_runtime_respects_max_log_age(self, tmp_path):
        """scan_runtime with max_log_age_hours filters stale files."""

        fresh = tmp_path / "fresh.log"
        fresh.write_text("ERROR found\n")

        stale = tmp_path / "stale.log"
        stale.write_text("ERROR old\n")
        old_time = time.time() - (48 * 3600)
        os.utime(stale, (old_time, old_time))

        config = {
            "scan_targets": [{"path": str(tmp_path / "*.log"), "patterns": ["ERROR"]}],
            "max_log_age_hours": 24,
        }
        with (
            patch.object(healer, "PROJECT_ROOT", tmp_path),
            patch.object(healer, "check_mcp_config_health", return_value=[]),
        ):
            findings = healer.scan_runtime(config)

        # Should only find error in fresh.log
        assert len(findings) >= 1
        assert all("fresh.log" in f.file for f in findings)

    def test_discover_untracked_logs_scans_external_logs_dir(self, tmp_runtime, monkeypatch):
        external_logs = tmp_runtime.parent / "external-logs"
        service_dir = external_logs / "unified_daemon" / "latest"
        service_dir.mkdir(parents=True)
        (service_dir / "errors_91311.log").write_text("ERROR external failure\n")

        monkeypatch.setattr(healer, "LOGS_DIR", external_logs)

        discovered = healer.discover_untracked_logs(
            {
                "scan_targets": [],
                "discovered_scan_targets": [],
            }
        )

        assert any(target["path"] == "logs/unified_daemon/**/*.log" for target in discovered)


# ═══════════════════════════════════════════════════════════════════════════════
# DEDUP REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════


class TestDedupRegistry:
    """Tests for load/save registry and dedup logic."""

    def test_load_empty_registry(self, tmp_runtime):
        registry = healer.load_registry()
        assert registry == {}

    def test_save_and_load_registry(self, tmp_runtime):
        entry = healer.RegistryEntry(
            dedup_key="test123",
            message="Test error",
            file="test.log",
            status="new",
        )
        healer.save_registry({"test123": entry})

        loaded = healer.load_registry()
        assert "test123" in loaded
        assert loaded["test123"].message == "Test error"

    def test_registry_entry_roundtrip(self, sample_entry):
        d = sample_entry.to_dict()
        restored = healer.RegistryEntry.from_dict(d)
        assert restored.dedup_key == sample_entry.dedup_key
        assert restored.severity == sample_entry.severity

    def test_dedup_new_issue(self):
        registry: dict[str, healer.RegistryEntry] = {}
        finding = healer.ErrorFinding(
            dedup_key="new1",
            message="New error",
            file="app.log",
            timestamp=datetime.now().isoformat(),
        )
        actionable = healer.deduplicate_findings([finding], registry)
        assert len(actionable) == 1
        assert "new1" in registry
        assert registry["new1"].status == "new"

    def test_dedup_duplicate_suppressed(self):
        registry = {
            "dup1": healer.RegistryEntry(
                dedup_key="dup1",
                message="Known error",
                file="app.log",
                status="new",
                occurrences=5,
            )
        }
        finding = healer.ErrorFinding(
            dedup_key="dup1",
            message="Known error",
            file="app.log",
            timestamp=datetime.now().isoformat(),
        )
        actionable = healer.deduplicate_findings([finding], registry)
        assert len(actionable) == 0
        assert registry["dup1"].occurrences == 6

    def test_dedup_fixing_skipped(self):
        registry = {
            "fix1": healer.RegistryEntry(
                dedup_key="fix1",
                message="Being fixed",
                file="app.log",
                status="fixing",
            )
        }
        finding = healer.ErrorFinding(
            dedup_key="fix1",
            message="Being fixed",
            file="app.log",
            timestamp=datetime.now().isoformat(),
        )
        actionable = healer.deduplicate_findings([finding], registry)
        assert len(actionable) == 0

    def test_dedup_regression_detected(self):
        now = datetime.now()
        registry = {
            "reg1": healer.RegistryEntry(
                dedup_key="reg1",
                message="Was fixed",
                file="app.log",
                status="fixed",
                fix_result="resolved",
                last_seen=(now - timedelta(minutes=30)).isoformat(),
            )
        }
        finding = healer.ErrorFinding(
            dedup_key="reg1",
            message="Was fixed",
            file="app.log",
            timestamp=now.isoformat(),
        )
        actionable = healer.deduplicate_findings([finding], registry)
        assert len(actionable) == 1
        assert registry["reg1"].status == "new"
        assert registry["reg1"].fix_result == "regression"

    def test_dedup_failed_retry(self):
        registry = {
            "fail1": healer.RegistryEntry(
                dedup_key="fail1",
                message="Failed fix",
                file="app.log",
                status="failed",
                fix_attempts=1,
            )
        }
        finding = healer.ErrorFinding(
            dedup_key="fail1",
            message="Failed fix",
            file="app.log",
            timestamp=datetime.now().isoformat(),
        )
        actionable = healer.deduplicate_findings([finding], registry)
        assert len(actionable) == 1
        assert registry["fail1"].status == "new"

    def test_dedup_abandoned_after_max_attempts(self, default_config):
        registry = {
            "max1": healer.RegistryEntry(
                dedup_key="max1",
                message="Exhausted",
                file="app.log",
                status="failed",
                fix_attempts=3,  # matches max_fix_attempts=3
            )
        }
        finding = healer.ErrorFinding(
            dedup_key="max1",
            message="Exhausted",
            file="app.log",
            timestamp=datetime.now().isoformat(),
        )
        actionable = healer.deduplicate_findings([finding], registry, default_config)
        assert len(actionable) == 0
        assert registry["max1"].status == "abandoned"

    def test_dedup_abandoned_stays_abandoned(self):
        registry = {
            "abn1": healer.RegistryEntry(
                dedup_key="abn1",
                message="Abandoned",
                file="app.log",
                status="abandoned",
            )
        }
        finding = healer.ErrorFinding(
            dedup_key="abn1",
            message="Abandoned",
            file="app.log",
            timestamp=datetime.now().isoformat(),
        )
        actionable = healer.deduplicate_findings([finding], registry)
        assert len(actionable) == 0

    def test_dedup_escalation_medium_to_high(self, default_config):
        """Medium issue recurring past threshold escalates to high."""
        registry = {
            "med1": healer.RegistryEntry(
                dedup_key="med1",
                message="Stale PID",
                file="mcp.log",
                severity="medium",
                status="abandoned",
                occurrences=2,  # Will become 3 after finding
            )
        }
        finding = healer.ErrorFinding(
            dedup_key="med1",
            message="Stale PID",
            file="mcp.log",
            timestamp=datetime.now().isoformat(),
        )
        # threshold=3, occurrences will be 3 after increment
        actionable = healer.deduplicate_findings([finding], registry, default_config)
        assert len(actionable) == 1
        assert registry["med1"].severity == "high"
        assert registry["med1"].status == "new"
        assert registry["med1"].fix_attempts == 0

    def test_dedup_escalation_below_threshold(self, default_config):
        """Medium issue below threshold stays abandoned."""
        registry = {
            "med2": healer.RegistryEntry(
                dedup_key="med2",
                message="Minor warning",
                file="app.log",
                severity="medium",
                status="abandoned",
                occurrences=1,  # Will become 2, still below 3
            )
        }
        finding = healer.ErrorFinding(
            dedup_key="med2",
            message="Minor warning",
            file="app.log",
            timestamp=datetime.now().isoformat(),
        )
        actionable = healer.deduplicate_findings([finding], registry, default_config)
        assert len(actionable) == 0
        assert registry["med2"].severity == "medium"

    def test_dedup_escalation_classifying_medium(self, default_config):
        """Medium issue in classifying state escalates when recurring past threshold."""
        registry = {
            "med3": healer.RegistryEntry(
                dedup_key="med3",
                message="Recurring warning",
                file="app.log",
                severity="medium",
                status="classifying",
                occurrences=2,
            )
        }
        finding = healer.ErrorFinding(
            dedup_key="med3",
            message="Recurring warning",
            file="app.log",
            timestamp=datetime.now().isoformat(),
        )
        actionable = healer.deduplicate_findings([finding], registry, default_config)
        assert len(actionable) == 1
        assert registry["med3"].severity == "high"
        assert registry["med3"].status == "new"

    def test_dedup_high_not_escalated(self, default_config):
        """High issues don't get escalated (already high)."""
        registry = {
            "hi1": healer.RegistryEntry(
                dedup_key="hi1",
                message="Broken feature",
                file="app.log",
                severity="high",
                status="abandoned",
                occurrences=10,
            )
        }
        finding = healer.ErrorFinding(
            dedup_key="hi1",
            message="Broken feature",
            file="app.log",
            timestamp=datetime.now().isoformat(),
        )
        actionable = healer.deduplicate_findings([finding], registry, default_config)
        assert len(actionable) == 0
        assert registry["hi1"].severity == "high"

    def test_dedup_dismissed_never_requeued(self, default_config):
        """Dismissed (transient) issues are never re-queued."""
        registry = {
            "d1": healer.RegistryEntry(
                dedup_key="d1",
                message="PID lock conflict",
                file="daemon.log",
                severity="transient",
                status="dismissed",
                occurrences=5,
                fix_result="transient_runtime_issue",
            )
        }
        finding = healer.ErrorFinding(
            dedup_key="d1",
            message="PID lock conflict",
            file="daemon.log",
            timestamp=datetime.now().isoformat(),
        )
        actionable = healer.deduplicate_findings([finding], registry, default_config)
        assert len(actionable) == 0
        assert registry["d1"].status == "dismissed"
        assert registry["d1"].occurrences == 6  # Count updated but not re-queued

    def test_compact_dismissed_registry_entries_merges_rotated_duplicates(self):
        now = datetime.now().isoformat()
        registry = {
            "a1": healer.RegistryEntry(
                dedup_key="a1",
                message="Transient API error [MagicMock] retrying in 4s (WARNING)",
                file="logs/unified_daemon/12-00_57270.log",
                status="dismissed",
                occurrences=2,
                first_seen=now,
                last_seen=now,
            ),
            "b2": healer.RegistryEntry(
                dedup_key="b2",
                message="Transient API error [MagicMock] retrying in 9s (WARNING)",
                file="logs/unified_daemon/12-00_60521.log",
                status="dismissed",
                occurrences=3,
                first_seen=now,
                last_seen=now,
            ),
        }

        compacted, removed = healer.compact_dismissed_registry_entries(registry)
        assert removed == 1
        assert len(compacted) == 1
        merged = next(iter(compacted.values()))
        assert merged.status == "dismissed"
        assert merged.occurrences == 5

    def test_compact_dismissed_registry_entries_keeps_non_dismissed(self):
        now = datetime.now().isoformat()
        registry = {
            "n1": healer.RegistryEntry(
                dedup_key="n1",
                message="TypeError: boom",
                file="logs/unified_daemon/12-00_70000.log",
                status="new",
                occurrences=1,
                first_seen=now,
                last_seen=now,
            ),
            "d1": healer.RegistryEntry(
                dedup_key="d1",
                message="Transient API error [MagicMock] retrying in 4s (WARNING)",
                file="logs/unified_daemon/12-00_57270.log",
                status="dismissed",
                occurrences=1,
                first_seen=now,
                last_seen=now,
            ),
            "d2": healer.RegistryEntry(
                dedup_key="d2",
                message="Transient API error [MagicMock] retrying in 5s (WARNING)",
                file="logs/unified_daemon/12-00_60521.log",
                status="dismissed",
                occurrences=1,
                first_seen=now,
                last_seen=now,
            ),
        }

        compacted, removed = healer.compact_dismissed_registry_entries(registry)
        assert removed == 1
        assert "n1" in compacted
        assert compacted["n1"].status == "new"


# ═══════════════════════════════════════════════════════════════════════════════
# LLM CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestClassification:
    """Tests for classify_issue and _parse_llm_json."""

    def test_parse_llm_json_clean(self):
        result = healer._parse_llm_json('{"severity": "high", "category": "ux"}')
        assert result["severity"] == "high"

    def test_parse_llm_json_with_markdown_fence(self):
        output = '```json\n{"severity": "critical", "category": "security"}\n```'
        result = healer._parse_llm_json(output)
        assert result["severity"] == "critical"

    def test_parse_llm_json_embedded_in_text(self):
        output = 'Here is my analysis:\n{"severity": "low", "category": "performance"}\nDone.'
        result = healer._parse_llm_json(output)
        assert result["severity"] == "low"

    def test_parse_llm_json_invalid(self):
        assert healer._parse_llm_json("no json here") is None
        assert healer._parse_llm_json("") is None
        assert healer._parse_llm_json("{broken") is None

    @patch.object(healer, "resolve_cli", return_value=None)
    def test_classify_no_cli(self, mock_cli, sample_entry, default_config):
        result = healer.classify_issue(sample_entry, default_config)
        assert result is None

    @patch("ai_self_healer.subprocess.run")
    def test_classify_success(self, mock_run, sample_entry, default_config):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"severity": "critical", "category": "integration", "summary": "map on undefined", "likely_file": "app.js", "suggested_approach": "null check"}',
        )
        result = healer.classify_issue(sample_entry, default_config, cli_path="/usr/bin/claude")
        assert result["severity"] == "critical"
        assert result["category"] == "integration"

    @patch("ai_self_healer.subprocess.run")
    def test_classify_cli_failure(self, mock_run, sample_entry, default_config):
        mock_run.return_value = MagicMock(returncode=1, stderr="CLI error")
        result = healer.classify_issue(sample_entry, default_config, cli_path="/usr/bin/claude")
        assert result is None

    @patch("ai_self_healer.subprocess.run")
    def test_classify_timeout(self, mock_run, sample_entry, default_config):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=30)
        result = healer.classify_issue(sample_entry, default_config, cli_path="/usr/bin/claude")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# CLI RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════════


class TestCLIResolution:
    """Tests for resolve_cli."""

    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_resolve_explicit_cli(self, mock_which):
        config = {"llm": {"cli": "claude"}}
        assert healer.resolve_cli(config) == "/usr/bin/claude"

    @patch("shutil.which", return_value=None)
    def test_resolve_explicit_cli_not_found(self, mock_which):
        config = {"llm": {"cli": "nonexistent"}}
        assert healer.resolve_cli(config) is None

    @patch("shutil.which", side_effect=lambda x, path=None: "/usr/bin/kimi" if x == "kimi" else None)
    @patch.object(healer, "LLM_CONFIG")
    def test_resolve_auto_from_installed(self, mock_llm_config, mock_which):
        mock_llm_config.exists.return_value = False
        config = {"llm": {"cli": "auto"}}
        # claude not found, kimi found
        assert healer.resolve_cli(config) == "/usr/bin/kimi"


# ═══════════════════════════════════════════════════════════════════════════════
# SEVERITY ROUTING
# ═══════════════════════════════════════════════════════════════════════════════


class TestSeverityRouting:
    """Tests for route_issue."""

    def test_route_critical_to_fix(self, sample_entry, default_config):
        sample_entry.severity = "critical"
        assert healer.route_issue(sample_entry, default_config) == "fix"

    def test_route_high_to_fix(self, sample_entry, default_config):
        sample_entry.severity = "high"
        assert healer.route_issue(sample_entry, default_config) == "fix"

    def test_route_medium_to_todo(self, sample_entry, default_config):
        sample_entry.severity = "medium"
        assert healer.route_issue(sample_entry, default_config) == "todo"

    def test_route_low_to_todo(self, sample_entry, default_config):
        sample_entry.severity = "low"
        assert healer.route_issue(sample_entry, default_config) == "todo"

    def test_route_unknown_defaults_to_todo(self, sample_entry, default_config):
        sample_entry.severity = "unknown"
        assert healer.route_issue(sample_entry, default_config) == "todo"


# ═══════════════════════════════════════════════════════════════════════════════
# TODO MARKER CREATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestTodoMarkerCreation:
    """Tests for create_todo_marker and _format_marker."""

    def test_format_marker_high(self, sample_entry):
        sample_entry.severity = "high"
        marker = healer._format_marker(sample_entry)
        assert "TODO_BUG(integration/high)" in marker
        assert "TypeError" in marker

    def test_format_marker_medium(self, sample_entry):
        sample_entry.severity = "medium"
        marker = healer._format_marker(sample_entry)
        assert "TODO_IMPROVE(integration)" in marker

    def test_create_todo_new_file(self, tmp_runtime, sample_entry):
        healer.create_todo_marker(sample_entry)
        content = healer.TECH_DEBT_FILE.read_text()
        assert sample_entry.dedup_key in content
        assert "TODO_BUG" in content

    def test_create_todo_dedup_updates_count(self, tmp_runtime, sample_entry):
        # Create initial marker
        sample_entry.occurrences = 1
        healer.create_todo_marker(sample_entry)

        # Update occurrences and create again
        sample_entry.occurrences = 5
        healer.create_todo_marker(sample_entry)

        content = healer.TECH_DEBT_FILE.read_text()
        # Verify count was updated (not 1 anymore)
        assert f"key:{sample_entry.dedup_key} count:5" in content
        # Should only appear once (deduped)
        assert content.count(f"key:{sample_entry.dedup_key}") == 1

    def test_create_todo_different_keys_append(self, tmp_runtime):
        entry1 = healer.RegistryEntry(
            dedup_key="aaa111",
            message="Error A",
            file="a.log",
            severity="medium",
            category="ux",
        )
        entry2 = healer.RegistryEntry(
            dedup_key="bbb222",
            message="Error B",
            file="b.log",
            severity="low",
            category="performance",
        )
        healer.create_todo_marker(entry1)
        healer.create_todo_marker(entry2)

        content = healer.TECH_DEBT_FILE.read_text()
        assert "aaa111" in content
        assert "bbb222" in content


# ═══════════════════════════════════════════════════════════════════════════════
# HEADLESS FIX
# ═══════════════════════════════════════════════════════════════════════════════


class TestHeadlessFix:
    """Tests for invoke_headless_fix, fix lock, context gathering, retry loop."""

    @patch.object(healer, "resolve_cli", return_value=None)
    def test_fix_no_cli(self, mock_cli, sample_entry, default_config):
        result = healer.invoke_headless_fix(sample_entry, default_config, cli_path=None)
        assert result["success"] is False
        assert "No CLI" in result["output"]

    @patch.object(healer, "_check_for_fix_commit", return_value="a1b2c3d")
    @patch.object(healer, "_gather_log_context", return_value="1: ERROR line here")
    @patch("ai_self_healer.subprocess.run")
    def test_fix_success_first_attempt(self, mock_run, mock_ctx, mock_commit, sample_entry, default_config):
        mock_run.return_value = MagicMock(returncode=0, stdout="Fixed the issue.\n")
        result = healer.invoke_headless_fix(sample_entry, default_config, cli_path="/usr/bin/claude")
        assert result["success"] is True
        assert result["commit"] == "a1b2c3d"
        assert result["aborted"] is False
        # Should only call CLI once (success on first attempt)
        assert mock_run.call_count == 1

    @patch.object(healer, "_check_for_fix_commit", side_effect=[None, "b2c3d4e"])
    @patch.object(healer, "_gather_log_context", return_value="1: ERROR line here")
    @patch("ai_self_healer.subprocess.run")
    def test_fix_success_on_retry(self, mock_run, mock_ctx, mock_commit, sample_entry, default_config):
        """First attempt no commit, second attempt succeeds."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Working on fix.\n")
        result = healer.invoke_headless_fix(sample_entry, default_config, cli_path="/usr/bin/claude")
        assert result["success"] is True
        assert result["commit"] == "b2c3d4e"
        # CLI called twice (attempt 1 + retry)
        assert mock_run.call_count == 2

    @patch.object(healer, "_check_for_fix_commit", return_value=None)
    @patch.object(healer, "_gather_log_context", return_value="1: ERROR line here")
    @patch("ai_self_healer.subprocess.run")
    def test_fix_all_attempts_exhausted(self, mock_run, mock_ctx, mock_commit, sample_entry, default_config):
        """All retry attempts fail to produce a commit — stagnation detected."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Analyzed but no fix.\n")
        result = healer.invoke_headless_fix(sample_entry, default_config, cli_path="/usr/bin/claude")
        assert result["success"] is False
        # Stagnation detection aborts early when consecutive outputs are identical
        assert "Stagnant" in result["output"] or ("All" in result["output"] and "failed" in result["output"])

    @patch.object(healer, "_gather_log_context", return_value="1: ERROR line here")
    @patch("ai_self_healer.subprocess.run")
    def test_fix_aborted_complex(self, mock_run, mock_ctx, sample_entry, default_config):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="This is too complex. ABORT_COMPLEX\n",
        )
        result = healer.invoke_headless_fix(sample_entry, default_config, cli_path="/usr/bin/claude")
        assert result["aborted"] is True
        assert result["success"] is False
        # Should NOT retry after ABORT_COMPLEX
        assert mock_run.call_count == 1

    @patch.object(healer, "_gather_log_context", return_value="1: ERROR line here")
    @patch("ai_self_healer.subprocess.run")
    def test_fix_timeout_retries(self, mock_run, mock_ctx, sample_entry, default_config):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=300)
        result = healer.invoke_headless_fix(sample_entry, default_config, cli_path="/usr/bin/claude")
        assert result["success"] is False
        assert "failed" in result["output"]

    @patch.object(healer, "_gather_log_context", return_value="1: ERROR line here")
    @patch("ai_self_healer.subprocess.run")
    def test_fix_exception_aborts(self, mock_run, mock_ctx, sample_entry, default_config):
        """A non-timeout exception stops retrying immediately."""
        mock_run.side_effect = RuntimeError("unexpected crash")
        result = healer.invoke_headless_fix(sample_entry, default_config, cli_path="/usr/bin/claude")
        assert result["success"] is False
        assert "unexpected crash" in result["output"]
        assert mock_run.call_count == 1

    def test_gather_log_context_found(self, tmp_runtime, sample_entry):
        """Context gathering reads lines around the error."""
        log_file = healer.LOGS_DIR / sample_entry.file
        log_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"line {i}" for i in range(50)]
        lines[25] = sample_entry.message
        log_file.write_text("\n".join(lines))

        ctx = healer._gather_log_context(sample_entry, {"fix": {"log_context_lines": 10}})
        assert sample_entry.message in ctx

    def test_gather_log_context_missing_file(self, tmp_runtime, sample_entry):
        ctx = healer._gather_log_context(sample_entry, {})
        assert "not found" in ctx

    def test_severity_profile_critical(self, default_config):
        entry = healer.RegistryEntry(dedup_key="x", message="crash", file="a.log", severity="critical")
        profile = healer._get_severity_profile(entry, default_config)
        assert profile["max_turns"] >= 20
        assert profile["timeout"] >= 600

    def test_severity_profile_high(self, default_config):
        entry = healer.RegistryEntry(dedup_key="x", message="broken", file="a.log", severity="high")
        profile = healer._get_severity_profile(entry, default_config)
        assert profile["max_turns"] >= 15
        assert profile["timeout"] >= 300

    def test_severity_profile_default(self, default_config):
        entry = healer.RegistryEntry(dedup_key="x", message="warn", file="a.log", severity="medium")
        profile = healer._get_severity_profile(entry, default_config)
        assert profile["max_turns"] == 10  # default fallback


class TestFixLock:
    """Tests for acquire/release fix lock."""

    def test_acquire_lock(self, tmp_runtime):
        assert healer.acquire_fix_lock("test_issue") is True
        assert healer.FIX_LOCK_FILE.exists()

    def test_lock_blocks_second_acquire(self, tmp_runtime):
        healer.acquire_fix_lock("issue1")
        assert healer.acquire_fix_lock("issue2") is False

    def test_release_lock(self, tmp_runtime):
        healer.acquire_fix_lock("test")
        healer.release_fix_lock()
        assert not healer.FIX_LOCK_FILE.exists()

    def test_stale_lock_removed(self, tmp_runtime):
        # Create a stale lock (>10 min ago)
        old_time = (datetime.now() - timedelta(minutes=15)).isoformat()
        lock_data = {"issue_key": "old", "started": old_time, "pid": 99999}
        healer.FIX_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        healer.FIX_LOCK_FILE.write_text(json.dumps(lock_data))

        assert healer.acquire_fix_lock("new_issue") is True

    def test_release_nonexistent_lock(self, tmp_runtime):
        # Should not raise
        healer.release_fix_lock()


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotifications:
    """Tests for _notify."""

    @patch.object(healer, "NotificationService", None)
    def test_notify_no_service_logs(self, default_config):
        # Should not raise, just log
        healer._notify("test message", default_config, event="on_detect")

    @patch.object(healer, "NotificationService")
    def test_notify_calls_service(self, mock_svc_cls, default_config):
        mock_svc = MagicMock()
        mock_svc_cls.return_value = mock_svc

        healer._notify("test message", default_config, event="on_detect")
        mock_svc.notify.assert_called_once()

    def test_notify_disabled_event(self, default_config):
        default_config["notifications"]["on_detect"] = False
        # Should return early without error
        healer._notify("test", default_config, event="on_detect")


# ═══════════════════════════════════════════════════════════════════════════════
# FULL PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════


class TestPipeline:
    """Integration tests for run_pipeline."""

    def test_pipeline_disabled(self, default_config):
        default_config["enabled"] = False
        summary = healer.run_pipeline(default_config)
        assert summary["scanned"] == 0

    @patch.object(healer, "scan_runtime", return_value=[])
    def test_pipeline_no_findings(self, mock_scan, default_config):
        summary = healer.run_pipeline(default_config)
        assert summary["scanned"] == 0
        assert summary["new_issues"] == 0

    @patch.object(healer, "_notify")
    @patch.object(healer, "resolve_cli", return_value=None)
    @patch.object(healer, "scan_runtime")
    def test_pipeline_creates_todo_when_no_cli(self, mock_scan, mock_cli, mock_notify, default_config, tmp_runtime):
        finding = healer.ErrorFinding(
            dedup_key="pipe1",
            message="ERROR: something failed",
            file="test.log",
            timestamp=datetime.now().isoformat(),
        )
        mock_scan.return_value = [finding]

        summary = healer.run_pipeline(default_config)
        assert summary["new_issues"] == 1
        assert summary["todos_created"] == 1
        assert summary["fixes_attempted"] == 0

    @patch.object(healer, "_notify")
    @patch.object(healer, "invoke_headless_fix")
    @patch.object(healer, "classify_issue")
    @patch.object(healer, "resolve_cli", return_value="/usr/bin/claude")
    @patch.object(healer, "scan_runtime")
    def test_pipeline_fix_success(
        self, mock_scan, mock_cli, mock_classify, mock_fix, mock_notify, default_config, tmp_runtime
    ):
        finding = healer.ErrorFinding(
            dedup_key="fix1",
            message="FATAL crash",
            file="daemon.log",
            timestamp=datetime.now().isoformat(),
        )
        mock_scan.return_value = [finding]
        mock_classify.return_value = {
            "severity": "critical",
            "category": "integration",
            "summary": "crash",
            "suggested_approach": "fix it",
        }
        mock_fix.return_value = {
            "success": True,
            "aborted": False,
            "output": "Fixed. Commit: abc1234",
            "commit": "abc1234",
        }

        summary = healer.run_pipeline(default_config)
        assert summary["fixes_attempted"] == 1
        assert summary["fixes_succeeded"] == 1

        # Check registry was updated
        registry = healer.load_registry()
        assert "fix1" in registry
        assert registry["fix1"].status == "fixed"
        assert registry["fix1"].fix_commit == "abc1234"

    @patch.object(healer, "_notify")
    @patch.object(healer, "invoke_headless_fix")
    @patch.object(healer, "classify_issue")
    @patch.object(healer, "resolve_cli", return_value="/usr/bin/claude")
    @patch.object(healer, "scan_runtime")
    def test_pipeline_fix_aborted(
        self, mock_scan, mock_cli, mock_classify, mock_fix, mock_notify, default_config, tmp_runtime
    ):
        finding = healer.ErrorFinding(
            dedup_key="abt1",
            message="Complex error",
            file="daemon.log",
            timestamp=datetime.now().isoformat(),
        )
        mock_scan.return_value = [finding]
        mock_classify.return_value = {
            "severity": "high",
            "category": "integration",
            "summary": "complex",
            "suggested_approach": "refactor",
        }
        mock_fix.return_value = {
            "success": False,
            "aborted": True,
            "output": "ABORT_COMPLEX",
        }

        summary = healer.run_pipeline(default_config)
        assert summary["fixes_attempted"] == 1
        assert summary["fixes_succeeded"] == 0
        assert summary["todos_created"] == 1

        registry = healer.load_registry()
        assert registry["abt1"].status == "abandoned"

    @patch.object(healer, "_notify")
    @patch.object(healer, "classify_issue")
    @patch.object(healer, "resolve_cli", return_value="/usr/bin/claude")
    @patch.object(healer, "scan_runtime")
    def test_pipeline_medium_creates_todo(
        self, mock_scan, mock_cli, mock_classify, mock_notify, default_config, tmp_runtime
    ):
        finding = healer.ErrorFinding(
            dedup_key="med1",
            message="WARNING: slow response",
            file="mcp.log",
            timestamp=datetime.now().isoformat(),
        )
        mock_scan.return_value = [finding]
        mock_classify.return_value = {
            "severity": "medium",
            "category": "performance",
            "summary": "slow",
            "suggested_approach": "optimize",
        }

        summary = healer.run_pipeline(default_config)
        assert summary["todos_created"] == 1
        assert summary["fixes_attempted"] == 0

        # Verify TODO marker was created
        content = healer.TECH_DEBT_FILE.read_text()
        assert "med1" in content

    @patch.object(healer, "_notify")
    @patch.object(healer, "classify_issue")
    @patch.object(healer, "resolve_cli", return_value="/usr/bin/claude")
    @patch.object(healer, "scan_runtime")
    def test_pipeline_transient_dismissed(
        self, mock_scan, mock_cli, mock_classify, mock_notify, default_config, tmp_runtime
    ):
        """Transient issues are dismissed — no fix, no TODO."""
        finding = healer.ErrorFinding(
            dedup_key="trans1",
            message="Another MCP server instance is already running (PID 12345)",
            file="augur_mcp.log",
            timestamp=datetime.now().isoformat(),
        )
        mock_scan.return_value = [finding]
        mock_classify.return_value = {
            "severity": "transient",
            "category": "runtime",
            "summary": "PID lock conflict",
            "suggested_approach": "Restart service",
        }

        # Add transient→dismiss to config routing
        default_config["routing"]["transient"] = "dismiss"
        summary = healer.run_pipeline(default_config)

        assert summary["fixes_attempted"] == 0
        assert summary["todos_created"] == 0
        assert summary.get("dismissed", 0) == 1

        # Verify entry is dismissed in registry
        registry = healer.load_registry()
        assert registry["trans1"].status == "dismissed"
        assert registry["trans1"].fix_result == "transient_runtime_issue"

        # Verify NO on_detect notification was sent for the transient issue
        on_detect_calls = [c for c in mock_notify.call_args_list if len(c.args) >= 1 and "Detected" in str(c.args[0])]
        assert len(on_detect_calls) == 0, (
            f"on_detect notification should NOT fire for dismissed issues, " f"but got: {on_detect_calls}"
        )

    @patch.object(healer, "_notify")
    @patch.object(healer, "classify_issue")
    @patch.object(healer, "resolve_cli", return_value="/usr/bin/claude")
    @patch.object(healer, "scan_runtime")
    def test_pipeline_actionable_issue_sends_on_detect(
        self, mock_scan, mock_cli, mock_classify, mock_notify, default_config, tmp_runtime
    ):
        """Non-transient issues DO get on_detect notification."""
        finding = healer.ErrorFinding(
            dedup_key="high1",
            message="FileNotFoundError: /data/missing.yaml",
            file="daemon.log",
            timestamp=datetime.now().isoformat(),
        )
        mock_scan.return_value = [finding]
        mock_classify.return_value = {
            "severity": "high",
            "category": "integration",
            "summary": "Missing file",
            "suggested_approach": "Fix path",
        }

        healer.run_pipeline(default_config)

        # Verify on_detect notification WAS sent for the actionable issue
        on_detect_calls = [c for c in mock_notify.call_args_list if len(c.args) >= 1 and "Detected" in str(c.args[0])]
        assert len(on_detect_calls) == 1, (
            f"Expected exactly 1 on_detect notification for actionable issue, " f"got {len(on_detect_calls)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CLI MODES
# ═══════════════════════════════════════════════════════════════════════════════


class TestCLIModes:
    """Tests for cmd_scan and cmd_status."""

    @patch.object(healer, "run_pipeline")
    @patch.object(healer, "load_config")
    def test_cmd_scan(self, mock_config, mock_pipeline, capsys):
        mock_config.return_value = {"enabled": True}
        mock_pipeline.return_value = {
            "scanned": 5,
            "new_issues": 2,
            "classified": 2,
            "fixes_attempted": 1,
            "fixes_succeeded": 1,
            "todos_created": 1,
            "timestamp": "2026-02-11T10:00:00",
        }
        ret = healer.cmd_scan()
        assert ret == 0
        output = capsys.readouterr().out
        assert "Scan Complete" in output

    def test_cmd_status_empty(self, tmp_runtime, capsys):
        ret = healer.cmd_status()
        assert ret == 0
        output = capsys.readouterr().out
        assert "No issues" in output

    def test_cmd_status_with_entries(self, tmp_runtime, capsys):
        registry = {
            "a1": healer.RegistryEntry(
                dedup_key="a1",
                message="Error A",
                file="a.log",
                severity="high",
                status="fixed",
            ),
            "b2": healer.RegistryEntry(
                dedup_key="b2",
                message="Error B",
                file="b.log",
                severity="medium",
                status="new",
            ),
        }
        healer.save_registry(registry)

        ret = healer.cmd_status()
        assert ret == 0
        output = capsys.readouterr().out
        assert "Total issues: 2" in output
        assert "fixed" in output
        assert "new" in output


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════


class TestMain:
    """Tests for main() CLI parsing."""

    @patch.object(healer, "cmd_scan", return_value=0)
    def test_main_default_scan(self, mock_scan):
        with patch("sys.argv", ["ai_self_healer.py"]):
            ret = healer.main()
        assert ret == 0
        mock_scan.assert_called_once()

    @patch.object(healer, "cmd_status", return_value=0)
    def test_main_status(self, mock_status):
        with patch("sys.argv", ["ai_self_healer.py", "--status"]):
            ret = healer.main()
        assert ret == 0
        mock_status.assert_called_once()

    @patch.object(healer, "cmd_scan", return_value=0)
    def test_main_scan_flag(self, mock_scan):
        with patch("sys.argv", ["ai_self_healer.py", "--scan"]):
            ret = healer.main()
        assert ret == 0

    @patch.object(healer, "monitor_loop")
    @patch.object(healer, "load_config", return_value={"enabled": True})
    def test_main_loop_flag(self, mock_config, mock_loop):
        with patch("sys.argv", ["ai_self_healer.py", "--loop"]):
            ret = healer.main()
        assert ret == 0
        mock_loop.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL COVERAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Tests for edge cases, error handlers, and import fallbacks."""

    def test_error_finding_to_dict(self):
        finding = healer.ErrorFinding(
            dedup_key="x1",
            message="test",
            file="f.log",
            line=10,
            timestamp="2026-01-01",
        )
        d = finding.to_dict()
        assert d["dedup_key"] == "x1"
        assert d["line"] == 10

    def test_scan_logs_empty_patterns(self, tmp_path):
        targets = [{"path": str(tmp_path / "*.log"), "patterns": []}]
        with patch.object(healer, "PROJECT_ROOT", tmp_path):
            findings, _ = healer.scan_logs(targets)
        assert findings == []

    def test_scan_logs_no_matching_files(self, tmp_path):
        targets = [{"path": str(tmp_path / "nonexistent*.log"), "patterns": ["ERROR"]}]
        with patch.object(healer, "PROJECT_ROOT", tmp_path):
            findings, _ = healer.scan_logs(targets)
        assert findings == []

    def test_scan_logs_no_matches(self, tmp_path):
        log = tmp_path / "test.log"
        log.write_text("no matches here\njust normal logs\n")
        targets = [{"path": str(log), "patterns": ["ERROR"]}]
        with patch.object(healer, "PROJECT_ROOT", tmp_path):
            findings, _ = healer.scan_logs(targets)
        assert findings == []

    def test_scan_logs_no_line_number(self, tmp_path):
        log = tmp_path / "test.log"
        log.write_text("ERROR raw line without number")
        targets = [{"path": str(log), "patterns": ["ERROR"]}]
        with patch.object(healer, "PROJECT_ROOT", tmp_path):
            findings, _ = healer.scan_logs(targets)
        assert len(findings) == 1
        assert "ERROR raw line without number" in findings[0].message

    def test_scan_logs_empty_patterns_second(self, tmp_path):
        targets = [{"path": str(tmp_path / "*.log"), "patterns": []}]
        with patch.object(healer, "PROJECT_ROOT", tmp_path):
            findings, _ = healer.scan_logs(targets)
        assert findings == []

    def test_save_watermarks_atomic(self, tmp_path):
        """Atomic watermark save should write valid JSON recoverable after crash."""
        wm_file = tmp_path / "test_watermarks.json"
        log_file = tmp_path / "test.log"
        log_file.write_text("ERROR persisted\n")
        with patch.object(healer, "_WATERMARK_FILE", wm_file):
            healer._save_watermarks_atomic({str(log_file): 42})
            assert wm_file.exists()
            loaded = json.loads(wm_file.read_text())
            assert loaded == {str(log_file): 42}
            # Temp file should be cleaned up
            assert not wm_file.with_suffix(".tmp").exists()

    def test_load_registry_corrupt_json(self, tmp_runtime):
        healer.REGISTRY_FILE.write_text("not valid json{{{")
        registry = healer.load_registry()
        assert registry == {}

    def test_config_load_plugin_exception(self, tmp_path):
        with patch.object(healer, "PLUGIN_CONFIG") as mock_p, \
             patch.object(healer, "USER_CONFIG") as mock_u, \
             patch.object(healer, "SCAN_TARGETS_STATE") as mock_s:
            mock_p.exists.return_value = True
            mock_p.read_text.side_effect = OSError("disk error")
            mock_u.exists.return_value = False
            mock_s.exists.return_value = False
            config = healer.load_config()
        assert config == {}

    def test_config_load_user_exception(self, tmp_path):
        with patch("yaml.safe_load", return_value={"enabled": True}):
            with patch.object(healer, "PLUGIN_CONFIG") as mock_p, \
                 patch.object(healer, "USER_CONFIG") as mock_u, \
                 patch.object(healer, "SCAN_TARGETS_STATE") as mock_s:
                mock_p.exists.return_value = True
                mock_p.read_text.return_value = "enabled: true"
                mock_u.exists.return_value = True
                mock_u.read_text.side_effect = OSError("disk error")
                mock_s.exists.return_value = False
                config = healer.load_config()
        assert config.get("enabled") is True

    def test_resolve_cli_auto_from_canonical_resolver(self):
        config = {"llm": {"cli": "auto"}}
        with patch("src.lib.llm_retry.resolve_cli", return_value="/usr/bin/kimi"):
            result = healer.resolve_cli(config)
        assert result == "/usr/bin/kimi"

    @patch.object(healer, "LLM_CONFIG")
    def test_resolve_cli_auto_llm_yaml_exception(self, mock_llm_config):
        mock_llm_config.exists.return_value = True
        mock_llm_config.read_text.side_effect = OSError("nope")
        config = {"llm": {"cli": "auto"}}
        with patch("shutil.which", side_effect=lambda x, path=None: "/usr/bin/claude" if x == "claude" else None):
            result = healer.resolve_cli(config)
        assert result == "/usr/bin/claude"

    @patch("shutil.which", return_value=None)
    @patch.object(healer, "LLM_CONFIG")
    def test_resolve_cli_auto_nothing_found(self, mock_llm_config, mock_which):
        mock_llm_config.exists.return_value = False
        config = {"llm": {"cli": "auto"}}
        result = healer.resolve_cli(config)
        assert result is None

    @patch("ai_self_healer.subprocess.run")
    def test_classify_generic_exception(self, mock_run, sample_entry, default_config):
        mock_run.side_effect = RuntimeError("unexpected")
        result = healer.classify_issue(sample_entry, default_config, cli_path="/usr/bin/claude")
        assert result is None

    @patch.object(healer, "_gather_log_context", return_value="1: ERROR")
    @patch("ai_self_healer.subprocess.run")
    def test_fix_generic_exception(self, mock_run, mock_ctx, sample_entry, default_config):
        mock_run.side_effect = RuntimeError("unexpected")
        result = healer.invoke_headless_fix(sample_entry, default_config, cli_path="/usr/bin/claude")
        assert result["success"] is False
        assert "unexpected" in result["output"]

    def test_fix_lock_corrupt_json(self, tmp_runtime):
        healer.FIX_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        healer.FIX_LOCK_FILE.write_text("not json")
        # Should remove corrupt lock and acquire
        assert healer.acquire_fix_lock("test") is True

    @patch.object(healer, "NotificationService")
    def test_notify_service_exception(self, mock_svc_cls, default_config):
        mock_svc = MagicMock()
        mock_svc.notify.side_effect = RuntimeError("notify boom")
        mock_svc_cls.return_value = mock_svc
        # Should not raise
        healer._notify("test", default_config, event="on_detect")

    @patch.object(healer, "_notify")
    @patch.object(healer, "invoke_headless_fix")
    @patch.object(healer, "classify_issue")
    @patch.object(healer, "resolve_cli", return_value="/usr/bin/claude")
    @patch.object(healer, "scan_runtime")
    def test_pipeline_fix_failure(
        self, mock_scan, mock_cli, mock_classify, mock_fix, mock_notify, default_config, tmp_runtime
    ):
        finding = healer.ErrorFinding(
            dedup_key="fail1",
            message="FATAL crash",
            file="daemon.log",
            timestamp=datetime.now().isoformat(),
        )
        mock_scan.return_value = [finding]
        mock_classify.return_value = {
            "severity": "critical",
            "category": "integration",
            "summary": "crash",
            "suggested_approach": "fix it",
        }
        mock_fix.return_value = {
            "success": False,
            "aborted": False,
            "output": "could not fix",
        }

        summary = healer.run_pipeline(default_config)
        assert summary["fixes_attempted"] == 1
        assert summary["fixes_succeeded"] == 0
        assert summary["todos_created"] == 1

        registry = healer.load_registry()
        assert registry["fail1"].status == "failed"

    @patch.object(healer, "_notify")
    @patch.object(healer, "acquire_fix_lock", return_value=False)
    @patch.object(healer, "classify_issue")
    @patch.object(healer, "resolve_cli", return_value="/usr/bin/claude")
    @patch.object(healer, "scan_runtime")
    def test_pipeline_fix_lock_held(
        self, mock_scan, mock_cli, mock_classify, mock_lock, mock_notify, default_config, tmp_runtime
    ):
        finding = healer.ErrorFinding(
            dedup_key="lock1",
            message="FATAL crash",
            file="daemon.log",
            timestamp=datetime.now().isoformat(),
        )
        mock_scan.return_value = [finding]
        mock_classify.return_value = {
            "severity": "critical",
            "category": "integration",
            "summary": "crash",
            "suggested_approach": "fix it",
        }

        summary = healer.run_pipeline(default_config)
        # Fix was skipped due to lock
        assert summary["fixes_attempted"] == 0

    @patch.object(healer, "_notify")
    @patch.object(healer, "classify_issue", return_value=None)
    @patch.object(healer, "resolve_cli", return_value="/usr/bin/claude")
    @patch.object(healer, "scan_runtime")
    def test_pipeline_classify_failure_defaults_to_medium(
        self, mock_scan, mock_cli, mock_classify, mock_notify, default_config, tmp_runtime
    ):
        finding = healer.ErrorFinding(
            dedup_key="cfail1",
            message="ERROR: something",
            file="daemon.log",
            timestamp=datetime.now().isoformat(),
        )
        mock_scan.return_value = [finding]

        summary = healer.run_pipeline(default_config)
        # classify returned None → defaults to medium → todo
        assert summary["todos_created"] == 1

        registry = healer.load_registry()
        assert registry["cfail1"].severity == "medium"

    @patch.object(healer, "run_pipeline")
    @patch.object(healer, "load_config", return_value={"scan_interval_minutes": 0.001})
    def test_monitor_loop_runs_once(self, mock_config, mock_pipeline):
        """Test monitor_loop executes pipeline at least once."""
        call_count = 0

        def pipeline_side_effect(config):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise KeyboardInterrupt()
            return {"new_issues": 0}

        mock_pipeline.side_effect = pipeline_side_effect

        config = {"scan_interval_minutes": 0.001}
        # monitor_loop runs forever, so we break via exception
        with pytest.raises(KeyboardInterrupt):
            healer.monitor_loop(config)
        assert call_count >= 1

    @patch.object(healer, "run_pipeline")
    @patch.object(healer, "load_config", return_value={"scan_interval_minutes": 0.001})
    def test_monitor_loop_handles_pipeline_error(self, mock_config, mock_pipeline):
        """Test monitor_loop catches pipeline exceptions and continues."""
        call_count = 0

        def pipeline_side_effect(config):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("transient error")
            raise KeyboardInterrupt()

        mock_pipeline.side_effect = pipeline_side_effect

        config = {"scan_interval_minutes": 0.001}
        with pytest.raises(KeyboardInterrupt):
            healer.monitor_loop(config)
        assert call_count >= 2  # Survived the first error

    @patch.object(healer, "scan_runtime")
    def test_pipeline_findings_but_all_deduped(self, mock_scan, default_config, tmp_runtime):
        """All findings already in registry → no actionable items."""
        finding = healer.ErrorFinding(
            dedup_key="known1",
            message="Known error",
            file="app.log",
            timestamp=datetime.now().isoformat(),
        )
        mock_scan.return_value = [finding]

        # Pre-populate registry with same key
        registry = {
            "known1": healer.RegistryEntry(
                dedup_key="known1",
                message="Known error",
                file="app.log",
                status="new",
                occurrences=3,
            )
        }
        healer.save_registry(registry)

        summary = healer.run_pipeline(default_config)
        assert summary["new_issues"] == 0

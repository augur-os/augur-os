"""Tests for notification_service.py -- multi-channel notification service."""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch

import pytest
import yaml

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPTS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "notification_service.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Stub runtime_paths if not already present
import types

_rp = sys.modules.get("runtime_paths")
if not _rp:
    _rp = types.ModuleType("runtime_paths")
    sys.modules["runtime_paths"] = _rp
_rp.get_notification_history_path = lambda: Path("/tmp/augur-test/history.yaml")
_rp.get_notification_pending_path = lambda: Path("/tmp/augur-test/pending.yaml")
_rp.get_notification_preferences_path = lambda: Path("/tmp/augur-test/preferences.yaml")
_rp.get_notifications_runtime_dir = lambda: Path("/tmp/augur-test/notifications")
_rp.get_insights_archive_dir = lambda: Path("/tmp/augur-test/archive")
_rp.get_insights_config_path = lambda: Path("/tmp/augur-test/config.yaml")
_rp.get_insights_path = lambda: Path("/tmp/augur-test/insights.yaml")

_spec = importlib.util.spec_from_file_location("notification_service", SCRIPTS_PATH)
notification_service = importlib.util.module_from_spec(_spec)
sys.modules["notification_service"] = notification_service
assert _spec.loader is not None
_spec.loader.exec_module(notification_service)

NotificationService = notification_service.NotificationService
ScheduledNotification = notification_service.ScheduledNotification
NotificationResult = notification_service.NotificationResult


def test_notification_result_has_backend_field():
    result = NotificationResult(success=True, channel="windows", message="ok", backend="powershell")

    assert result.backend == "powershell"


def test_notification_result_positional_error_compatibility():
    result = NotificationResult(False, "windows", "", "boom")

    assert result.error == "boom"
    assert result.backend == ""


def test_send_windows_reports_winrt_backend_when_plyer_missing(tmp_path):
    service = NotificationService(data_dir=tmp_path / "notif")
    completed = CompletedProcess(args=["powershell"], returncode=0, stdout="AUGUR_BACKEND:winrt\n", stderr="")

    with patch.dict(sys.modules, {"plyer": None}):
        with patch.object(notification_service, "_run_command", return_value=completed):
            result = service._send_windows("ok")

    assert result.success
    assert result.channel == "windows"
    assert result.backend == "winrt"


def test_send_windows_reports_burnttoast_backend_when_marker_present(tmp_path):
    service = NotificationService(data_dir=tmp_path / "notif")
    completed = CompletedProcess(args=["powershell"], returncode=0, stdout="AUGUR_BACKEND:burnttoast\n", stderr="")

    with patch.dict(sys.modules, {"plyer": None}):
        with patch.object(notification_service, "_run_command", return_value=completed):
            result = service._send_windows("ok")

    assert result.success
    assert result.channel == "windows"
    assert result.backend == "burnttoast"


def test_send_windows_reports_powershell_backend_without_marker(tmp_path):
    service = NotificationService(data_dir=tmp_path / "notif")
    completed = CompletedProcess(args=["powershell"], returncode=0, stdout="", stderr="")

    with patch.dict(sys.modules, {"plyer": None}):
        with patch.object(notification_service, "_run_command", return_value=completed):
            result = service._send_windows("ok")

    assert result.success
    assert result.channel == "windows"
    assert result.backend == "powershell"


def test_send_windows_reports_winrt_backend_error_when_powershell_fails(tmp_path):
    service = NotificationService(data_dir=tmp_path / "notif")
    completed = CompletedProcess(args=["powershell"], returncode=1, stdout="AUGUR_BACKEND:winrt\n", stderr="toast failed")

    with patch.dict(sys.modules, {"plyer": None}):
        with patch.object(notification_service, "_run_command", return_value=completed):
            result = service._send_windows("ok")

    assert not result.success
    assert result.backend == "winrt"
    assert "toast failed" in result.error


class TestNotificationService:
    """Tests for the core NotificationService class."""

    def test_init_creates_data_dir(self, tmp_path):
        svc = NotificationService(data_dir=tmp_path / "notif")
        assert (tmp_path / "notif").is_dir()

    def test_send_unknown_channel_returns_error(self, tmp_path):
        svc = NotificationService(data_dir=tmp_path / "notif")
        result = svc.send("test", channel="pigeonpost")
        assert not result.success
        assert "Unknown channel" in result.error

    def test_notify_disabled_returns_error(self, tmp_path):
        prefs_dir = tmp_path / "notif"
        prefs_dir.mkdir()
        prefs_file = prefs_dir / "preferences.yaml"
        prefs_file.write_text(yaml.dump({"enabled": False}))
        svc = NotificationService(data_dir=prefs_dir)
        results = svc.notify("test", category="dashboard")
        assert len(results) == 1
        assert not results[0].success
        assert "disabled" in results[0].error.lower()

    def test_notify_category_disabled(self, tmp_path):
        prefs_dir = tmp_path / "notif"
        prefs_dir.mkdir()
        prefs_file = prefs_dir / "preferences.yaml"
        prefs_file.write_text(yaml.dump({
            "enabled": True,
            "categories": {"mcp": {"enabled": False}},
        }))
        svc = NotificationService(data_dir=prefs_dir)
        results = svc.notify("test", category="mcp")
        assert len(results) == 1
        assert "disabled" in results[0].error.lower()


class TestScheduledNotification:
    """Tests for ScheduledNotification round-trip serialization."""

    def test_round_trip(self):
        n = ScheduledNotification(
            id="abc123",
            message="Follow up",
            channel="system",
            scheduled_for=datetime(2026, 3, 20, 10, 0),
            vertical="career",
        )
        d = n.to_dict()
        n2 = ScheduledNotification.from_dict(d)
        assert n2.id == "abc123"
        assert n2.message == "Follow up"
        assert n2.vertical == "career"
        assert n2.scheduled_for == datetime(2026, 3, 20, 10, 0)


class TestRemind:
    """Tests for scheduling reminders."""

    def test_remind_creates_pending(self, tmp_path):
        svc = NotificationService(data_dir=tmp_path / "notif")
        reminder_id = svc.remind("Follow up", in_minutes=60)
        assert isinstance(reminder_id, str)
        assert len(reminder_id) > 0

        pending = svc.get_pending()
        assert len(pending) == 1
        assert pending[0].message == "Follow up"

    def test_cancel_removes_pending(self, tmp_path):
        svc = NotificationService(data_dir=tmp_path / "notif")
        rid = svc.remind("Cancel me", in_minutes=120)
        assert svc.cancel(rid) is True
        assert len(svc.get_pending()) == 0

    def test_cancel_nonexistent_returns_false(self, tmp_path):
        svc = NotificationService(data_dir=tmp_path / "notif")
        assert svc.cancel("nonexistent-id") is False


class TestQuietHours:
    """Tests for quiet hours checking."""

    def test_quiet_hours_disabled_by_default(self, tmp_path):
        svc = NotificationService(data_dir=tmp_path / "notif")
        assert svc._is_in_quiet_hours() is False

    def test_quiet_hours_active(self, tmp_path):
        prefs_dir = tmp_path / "notif"
        prefs_dir.mkdir()
        prefs_file = prefs_dir / "preferences.yaml"
        # Set quiet hours to cover the entire day to guarantee test works
        prefs_file.write_text(yaml.dump({
            "enabled": True,
            "quiet_hours": {"enabled": True, "start": "00:00", "end": "23:59"},
        }))
        svc = NotificationService(data_dir=prefs_dir)
        assert svc._is_in_quiet_hours() is True

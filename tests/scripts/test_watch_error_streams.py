"""Tests for apps/dashboard/scripts/watch_error_streams.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = PROJECT_ROOT / "apps" / "dashboard" / "scripts" / "watch_error_streams.py"
SPEC = importlib.util.spec_from_file_location("watch_error_streams", MODULE_PATH)
assert SPEC and SPEC.loader
watch_error_streams = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = watch_error_streams
SPEC.loader.exec_module(watch_error_streams)


def test_format_text_line_matches_timeout():
    message = watch_error_streams.format_text_line(
        "dashboard.stderr",
        "POST /api/mcp/context/switch timed out after 60000ms",
    )
    assert message == "[dashboard.stderr] POST /api/mcp/context/switch timed out after 60000ms"


def test_format_text_line_ignores_normal_dev_noise():
    assert (
        watch_error_streams.format_text_line(
            "dashboard.stderr",
            "Compiled /brain in 712ms",
        )
        is None
    )


def test_format_lifecycle_event_highlights_runtime_degrade():
    message = watch_error_streams.format_lifecycle_event(
        {
            "instance_id": "main",
            "actor": "dashboard_monitor",
            "action": "health_check",
            "reason": "runtime degraded: repeated API timeouts",
            "prev_state": "healthy",
            "new_state": "stabilizing",
        }
    )
    assert (
        message
        == "[lifecycle] dashboard_monitor health_check (healthy -> stabilizing): runtime degraded: repeated API timeouts"
    )


def test_lifecycle_event_ignores_other_instances(monkeypatch):
    monkeypatch.setenv("AUGUR_INSTANCE_ID", "worktree:task-1")

    message = watch_error_streams.format_lifecycle_event(
        {
            "instance_id": "main",
            "actor": "dashboard_monitor",
            "action": "recovery_failed",
            "reason": "main recovery failed",
            "prev_state": "starting",
            "new_state": "crashed",
        }
    )

    assert message is None


def test_lifecycle_event_keeps_current_instance(monkeypatch):
    monkeypatch.setenv("AUGUR_INSTANCE_ID", "worktree:task-1")

    message = watch_error_streams.format_lifecycle_event(
        {
            "instance_id": "worktree:task-1",
            "actor": "dashboard_monitor",
            "action": "recovery_failed",
            "reason": "worktree recovery failed",
            "prev_state": "starting",
            "new_state": "crashed",
        }
    )

    assert message == "[lifecycle] dashboard_monitor recovery_failed (starting -> crashed): worktree recovery failed"


def test_format_self_heal_event_surfaces_client_errors():
    message = watch_error_streams.format_self_heal_event(
        {
            "source": "ClientErrorReporter",
            "category": "client-error",
            "severity": "low",
            "message": "Cannot read properties of undefined",
            "context": {
                "fingerprint": "client:error:abc123",
                "url": "/command/self-heal",
            },
        }
    )
    assert (
        message
        == "[client-error] LOW ClientErrorReporter/client-error: Cannot read properties of undefined [fingerprint=client:error:abc123 url=/command/self-heal]"
    )


def test_format_self_heal_event_ignores_low_non_client_events():
    assert (
        watch_error_streams.format_self_heal_event(
            {
                "source": "preflight",
                "category": "service_fallback",
                "severity": "low",
                "message": "using fallback cache",
                "context": {},
            }
        )
        is None
    )

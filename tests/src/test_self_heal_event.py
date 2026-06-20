"""Tests for self-heal event emitter (ADR-084)."""

import json
import os
from unittest.mock import patch

from src.logging.self_heal_event import (
    VALID_CATEGORIES,
    VALID_SEVERITIES,
    emit_heal_event,
)


class TestEmitHealEvent:
    """Core emit_heal_event tests."""

    def test_event_written_to_jsonl(self, tmp_path):
        """Event is written as a single JSONL line to the event file."""
        event_file = tmp_path / "data" / "runtime" / "self_heal_events.jsonl"

        with patch(
            "src.logging.self_heal_event._get_event_file",
            return_value=event_file,
        ):
            (tmp_path / "data" / "runtime").mkdir(parents=True, exist_ok=True)
            emit_heal_event(
                source="test_module",
                category="import_failure",
                severity="high",
                message="Test event",
                context={"key": "value"},
            )

        assert event_file.exists()
        lines = event_file.read_text().strip().splitlines()
        assert len(lines) == 1

        event = json.loads(lines[0])
        assert event["source"] == "test_module"
        assert event["category"] == "import_failure"
        assert event["severity"] == "high"
        assert event["message"] == "Test event"
        assert event["context"] == {"key": "value"}

    def test_schema_has_all_required_fields(self, tmp_path):
        """Event JSON contains all required schema fields."""
        event_file = tmp_path / "data" / "runtime" / "self_heal_events.jsonl"
        (tmp_path / "data" / "runtime").mkdir(parents=True, exist_ok=True)

        with patch(
            "src.logging.self_heal_event._get_event_file",
            return_value=event_file,
        ):
            emit_heal_event(
                source="mcp_server",
                category="path_missing",
                severity="critical",
                message="Missing data dir",
            )

        event = json.loads(event_file.read_text().strip())

        required_fields = {
            "timestamp",
            "source",
            "category",
            "severity",
            "message",
            "context",
            "host",
            "pid",
        }
        assert required_fields == set(event.keys())

    def test_timestamp_is_iso_utc(self, tmp_path):
        """Timestamp is ISO 8601 UTC with milliseconds and Z suffix."""
        event_file = tmp_path / "data" / "runtime" / "self_heal_events.jsonl"
        (tmp_path / "data" / "runtime").mkdir(parents=True, exist_ok=True)

        with patch(
            "src.logging.self_heal_event._get_event_file",
            return_value=event_file,
        ):
            emit_heal_event(
                source="test",
                category="config_missing",
                severity="low",
                message="test",
            )

        event = json.loads(event_file.read_text().strip())
        ts = event["timestamp"]
        assert ts.endswith("Z")
        # Format: 2026-02-12T14:30:00.000Z
        assert len(ts) == 24
        assert ts[4] == "-"
        assert ts[10] == "T"

    def test_pid_is_current_process(self, tmp_path):
        """PID field matches the current process."""
        event_file = tmp_path / "data" / "runtime" / "self_heal_events.jsonl"
        (tmp_path / "data" / "runtime").mkdir(parents=True, exist_ok=True)

        with patch(
            "src.logging.self_heal_event._get_event_file",
            return_value=event_file,
        ):
            emit_heal_event(
                source="test",
                category="import_failure",
                severity="medium",
                message="test",
            )

        event = json.loads(event_file.read_text().strip())
        assert event["pid"] == os.getpid()

    def test_context_defaults_to_empty_dict(self, tmp_path):
        """When context is None, it defaults to empty dict in output."""
        event_file = tmp_path / "data" / "runtime" / "self_heal_events.jsonl"
        (tmp_path / "data" / "runtime").mkdir(parents=True, exist_ok=True)

        with patch(
            "src.logging.self_heal_event._get_event_file",
            return_value=event_file,
        ):
            emit_heal_event(
                source="test",
                category="mcp_failure",
                severity="low",
                message="no context",
            )

        event = json.loads(event_file.read_text().strip())
        assert event["context"] == {}

    def test_multiple_events_append(self, tmp_path):
        """Multiple events are appended as separate JSONL lines."""
        event_file = tmp_path / "data" / "runtime" / "self_heal_events.jsonl"
        (tmp_path / "data" / "runtime").mkdir(parents=True, exist_ok=True)

        with patch(
            "src.logging.self_heal_event._get_event_file",
            return_value=event_file,
        ):
            for i in range(5):
                emit_heal_event(
                    source=f"module_{i}",
                    category="import_failure",
                    severity="low",
                    message=f"Event {i}",
                )

        lines = event_file.read_text().strip().splitlines()
        assert len(lines) == 5

        for i, line in enumerate(lines):
            event = json.loads(line)
            assert event["source"] == f"module_{i}"
            assert event["message"] == f"Event {i}"


class TestNeverRaises:
    """Verify emit_heal_event never raises, even with broken inputs/paths."""

    def test_broken_event_file_path(self):
        """Function does not raise when event file path is unresolvable."""
        with patch(
            "src.logging.self_heal_event._get_event_file",
            return_value=None,
        ):
            # Should not raise — falls back to stderr
            emit_heal_event(
                source="test",
                category="import_failure",
                severity="high",
                message="broken path",
            )

    def test_readonly_directory(self, tmp_path):
        """Function does not raise when directory is read-only."""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        event_file = readonly_dir / "events.jsonl"
        readonly_dir.chmod(0o444)

        try:
            with patch(
                "src.logging.self_heal_event._get_event_file",
                return_value=event_file,
            ):
                # Should not raise
                emit_heal_event(
                    source="test",
                    category="path_missing",
                    severity="critical",
                    message="readonly dir",
                )
        finally:
            readonly_dir.chmod(0o755)

    def test_none_inputs(self):
        """Function does not raise with None inputs (converts to str)."""
        with patch(
            "src.logging.self_heal_event._get_event_file",
            return_value=None,
        ):
            emit_heal_event(
                source=None,
                category=None,
                severity=None,
                message=None,
            )

    def test_exception_in_json_dumps(self, tmp_path):
        """Function does not raise when context contains non-serializable data."""
        event_file = tmp_path / "data" / "runtime" / "self_heal_events.jsonl"
        (tmp_path / "data" / "runtime").mkdir(parents=True, exist_ok=True)

        class Unserializable:
            def __repr__(self):
                raise RuntimeError("bad repr")

        with patch(
            "src.logging.self_heal_event._get_event_file",
            return_value=event_file,
        ):
            # json.dumps with default=str should handle this, but even if
            # it somehow fails, the outer try/except catches it
            emit_heal_event(
                source="test",
                category="import_failure",
                severity="high",
                message="bad context",
                context={"obj": Unserializable()},
            )

    def test_stderr_fallback_on_no_project_root(self, capsys):
        """Falls back to stderr when project root cannot be found."""
        with patch(
            "src.logging.self_heal_event._get_event_file",
            return_value=None,
        ):
            emit_heal_event(
                source="orphan",
                category="path_missing",
                severity="high",
                message="no root",
            )

        captured = capsys.readouterr()
        assert "[self-heal]" in captured.err
        assert "orphan" in captured.err


class TestAtomicWrite:
    """Verify atomic write behavior."""

    def test_temp_file_cleaned_up(self, tmp_path):
        """Temp files are cleaned up after successful write."""
        event_file = tmp_path / "data" / "runtime" / "self_heal_events.jsonl"
        (tmp_path / "data" / "runtime").mkdir(parents=True, exist_ok=True)

        with patch(
            "src.logging.self_heal_event._get_event_file",
            return_value=event_file,
        ):
            emit_heal_event(
                source="test",
                category="import_failure",
                severity="low",
                message="cleanup test",
            )

        # No .tmp files should remain
        tmp_files = list(event_file.parent.glob(".heal_*.tmp"))
        assert len(tmp_files) == 0

    def test_event_file_is_valid_jsonl_after_write(self, tmp_path):
        """Every line in the event file is valid JSON after writes."""
        event_file = tmp_path / "data" / "runtime" / "self_heal_events.jsonl"
        (tmp_path / "data" / "runtime").mkdir(parents=True, exist_ok=True)

        with patch(
            "src.logging.self_heal_event._get_event_file",
            return_value=event_file,
        ):
            for i in range(10):
                emit_heal_event(
                    source="test",
                    category="import_failure",
                    severity="low",
                    message=f"event {i}",
                )

        content = event_file.read_text().strip()
        for line in content.splitlines():
            parsed = json.loads(line)  # should not raise
            assert isinstance(parsed, dict)

    def test_each_line_ends_with_newline(self, tmp_path):
        """Each event line is terminated with a newline."""
        event_file = tmp_path / "data" / "runtime" / "self_heal_events.jsonl"
        (tmp_path / "data" / "runtime").mkdir(parents=True, exist_ok=True)

        with patch(
            "src.logging.self_heal_event._get_event_file",
            return_value=event_file,
        ):
            emit_heal_event(
                source="test",
                category="import_failure",
                severity="low",
                message="newline test",
            )

        content = event_file.read_text()
        assert content.endswith("\n")


class TestValidConstants:
    """Verify category and severity constants are correct."""

    def test_valid_categories(self):
        assert "import_failure" in VALID_CATEGORIES
        assert "path_missing" in VALID_CATEGORIES
        assert "config_missing" in VALID_CATEGORIES
        assert "mcp_failure" in VALID_CATEGORIES
        assert "service_fallback" in VALID_CATEGORIES
        assert len(VALID_CATEGORIES) == 5

    def test_valid_severities(self):
        assert "critical" in VALID_SEVERITIES
        assert "high" in VALID_SEVERITIES
        assert "medium" in VALID_SEVERITIES
        assert "low" in VALID_SEVERITIES
        assert len(VALID_SEVERITIES) == 4

"""Tests for task_utils.py — task parsing, scoring, and availability."""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_task_utils_spec = importlib.util.spec_from_file_location(
    "platform_admin_task_utils",
    SCRIPTS_DIR / "task_utils.py",
)
assert _task_utils_spec is not None and _task_utils_spec.loader is not None
_task_utils = importlib.util.module_from_spec(_task_utils_spec)
sys.modules["platform_admin_task_utils"] = _task_utils
_task_utils_spec.loader.exec_module(_task_utils)

is_task_available = _task_utils.is_task_available
parse_created = _task_utils.parse_created
priority_score = _task_utils.priority_score
read_task = _task_utils.read_task
task_title = _task_utils.task_title
write_task = _task_utils.write_task
task_lock = _task_utils.task_lock


# ---------------------------------------------------------------------------
# priority_score
# ---------------------------------------------------------------------------


class TestPriorityScore:
    def test_critical_is_zero(self):
        assert priority_score("critical") == 0

    def test_high_is_one(self):
        assert priority_score("high") == 1

    def test_medium_is_two(self):
        assert priority_score("medium") == 2

    def test_low_is_three(self):
        assert priority_score("low") == 3

    def test_unknown_is_four(self):
        assert priority_score("unknown") == 4

    def test_case_insensitive(self):
        assert priority_score("HIGH") == 1


# ---------------------------------------------------------------------------
# task_title
# ---------------------------------------------------------------------------


class TestTaskTitle:
    def test_extracts_h1_header(self):
        body = "# My Task\nSome content"
        assert task_title(body) == "My Task"

    def test_returns_default_when_no_header(self):
        body = "No header here"
        assert task_title(body) == "Untitled"

    def test_custom_default(self):
        assert task_title("no header", default="Fallback") == "Fallback"


# ---------------------------------------------------------------------------
# parse_created
# ---------------------------------------------------------------------------


class TestParseCreated:
    def test_iso_format_with_T(self):
        result = parse_created("2026-01-15T10:30:00")
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15

    def test_date_only(self):
        result = parse_created("2026-03-10")
        assert result.year == 2026

    def test_empty_returns_epoch(self):
        result = parse_created("")
        assert result == datetime.fromtimestamp(0)

    def test_garbage_returns_epoch(self):
        result = parse_created("not-a-date")
        assert result == datetime.fromtimestamp(0)


# ---------------------------------------------------------------------------
# read_task / write_task
# ---------------------------------------------------------------------------


class TestReadWriteTask:
    def test_read_frontmatter_and_body(self, tmp_path):
        task_file = tmp_path / "task.md"
        task_file.write_text("---\nstatus: ready\npriority: high\n---\n\n# My Task\nContent")

        fm, body = read_task(task_file)
        assert fm["status"] == "ready"
        assert fm["priority"] == "high"
        assert "My Task" in body

    def test_read_no_frontmatter(self, tmp_path):
        task_file = tmp_path / "task.md"
        task_file.write_text("Just plain content")

        fm, body = read_task(task_file)
        assert fm == {}
        assert body == "Just plain content"

    def test_write_creates_valid_frontmatter(self, tmp_path):
        task_file = tmp_path / "task.md"
        write_task(task_file, {"status": "ready", "priority": "high"}, "# Task\nDo something")

        fm, body = read_task(task_file)
        assert fm["status"] == "ready"
        assert "Task" in body


# ---------------------------------------------------------------------------
# task_lock
# ---------------------------------------------------------------------------


class TestTaskLock:
    def test_task_lock_creates_and_removes_sidecar(self, tmp_path):
        task_file = tmp_path / "task.md"
        task_file.write_text("# Task\n")

        with task_lock(task_file, timeout=0.1):
            assert task_file.with_suffix(".lock").exists()

        assert not task_file.with_suffix(".lock").exists()


# ---------------------------------------------------------------------------
# is_task_available
# ---------------------------------------------------------------------------


class TestIsTaskAvailable:
    def test_ready_status_is_available(self):
        assert is_task_available({"status": "ready"}) is True

    def test_non_ready_status_not_available(self):
        assert is_task_available({"status": "done"}) is False
        assert is_task_available({"status": "blocked"}) is False

    def test_completed_execution_not_available(self):
        fm = {"status": "ready", "execution": {"status": "completed"}}
        assert is_task_available(fm) is False

    def test_stale_claim_becomes_available(self):
        old_time = (datetime.now() - timedelta(hours=3)).isoformat()
        fm = {
            "status": "ready",
            "execution": {"status": "claimed", "claimed_at": old_time},
        }
        assert is_task_available(fm, stale_hours=2) is True

    def test_fresh_claim_not_available(self):
        recent = datetime.now().isoformat()
        fm = {
            "status": "ready",
            "execution": {"status": "claimed", "claimed_at": recent},
        }
        assert is_task_available(fm, stale_hours=2) is False

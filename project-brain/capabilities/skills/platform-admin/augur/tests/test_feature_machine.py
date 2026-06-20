"""Tests for feature_machine.py — task reading, checklist management, slug generation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from feature_machine import (
    DEFAULT_PHASES,
    _append_log,
    _ensure_checklist,
    _extract_section,
    _extract_test_commands,
    _parse_created,
    _priority_score,
    _read_task,
    _set_checklist_phase,
    _slugify,
    _task_title,
    _write_task,
)


# ---------------------------------------------------------------------------
# _slugify
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_basic_slug(self):
        assert _slugify("My Feature Task") == "my-feature-task"

    def test_strips_special_chars(self):
        assert _slugify("Fix: bug #123!") == "fix-bug-123"

    def test_empty_returns_feature(self):
        assert _slugify("") == "feature"

    def test_strips_leading_trailing_hyphens(self):
        assert _slugify("---hello---") == "hello"


# ---------------------------------------------------------------------------
# _priority_score
# ---------------------------------------------------------------------------


class TestPriorityScore:
    def test_p0_is_zero(self):
        assert _priority_score("p0") == 0
        assert _priority_score("critical") == 0

    def test_p1_is_one(self):
        assert _priority_score("p1") == 1
        assert _priority_score("high") == 1

    def test_unknown_is_four(self):
        assert _priority_score("whatever") == 4

    def test_empty_is_four(self):
        assert _priority_score("") == 4


# ---------------------------------------------------------------------------
# _task_title
# ---------------------------------------------------------------------------


class TestTaskTitle:
    def test_extracts_h1(self):
        assert _task_title("# Implement Auth\nDetails...", "fallback") == "Implement Auth"

    def test_returns_fallback_when_no_h1(self):
        assert _task_title("no header", "fallback") == "fallback"


# ---------------------------------------------------------------------------
# _read_task / _write_task
# ---------------------------------------------------------------------------


class TestReadWriteTask:
    def test_round_trip(self, tmp_path):
        f = tmp_path / "task.md"
        fm = {"status": "ready", "priority": "high"}
        body = "# My Task\nDo the thing.\n"

        _write_task(f, fm, body)
        loaded_fm, loaded_body = _read_task(f)

        assert loaded_fm["status"] == "ready"
        assert loaded_fm["priority"] == "high"
        assert "My Task" in loaded_body

    def test_read_no_frontmatter(self, tmp_path):
        f = tmp_path / "plain.md"
        f.write_text("Just a body with no frontmatter")
        fm, body = _read_task(f)
        assert fm == {}
        assert "Just a body" in body


# ---------------------------------------------------------------------------
# _ensure_checklist
# ---------------------------------------------------------------------------


class TestEnsureChecklist:
    def test_adds_checklist_to_empty_body(self):
        result = _ensure_checklist("", ["design", "test"])
        assert "## Feature Machine Checklist" in result
        assert "- [ ] design" in result
        assert "- [ ] test" in result

    def test_does_not_duplicate_existing_phases(self):
        body = "## Feature Machine Checklist\n- [ ] design\n"
        result = _ensure_checklist(body, ["design", "test"])
        assert result.count("- [ ] design") == 1
        assert "- [ ] test" in result

    def test_preserves_existing_body(self):
        body = "# Task\nSome content here.\n"
        result = _ensure_checklist(body, ["impl"])
        assert "Some content here." in result
        assert "- [ ] impl" in result


# ---------------------------------------------------------------------------
# _set_checklist_phase
# ---------------------------------------------------------------------------


class TestSetChecklistPhase:
    def test_marks_phase_done(self):
        body = "## Feature Machine Checklist\n- [ ] design\n- [ ] test\n"
        result = _set_checklist_phase(body, "design", True)
        assert "- [x] design" in result
        assert "- [ ] test" in result

    def test_marks_phase_undone(self):
        body = "## Feature Machine Checklist\n- [x] design\n"
        result = _set_checklist_phase(body, "design", False)
        assert "- [ ] design" in result


# ---------------------------------------------------------------------------
# _append_log
# ---------------------------------------------------------------------------


class TestAppendLog:
    def test_adds_log_header_when_missing(self):
        body = "# Task\nContent."
        result = _append_log(body, "design", "Started design phase")
        assert "## Execution Log" in result
        assert "design" in result
        assert "Started design phase" in result

    def test_appends_to_existing_log(self):
        body = "## Execution Log\n- 2026-01-01 | init\n"
        result = _append_log(body, "test", "Running tests")
        assert result.count("## Execution Log") == 1
        assert "Running tests" in result


# ---------------------------------------------------------------------------
# _extract_section
# ---------------------------------------------------------------------------


class TestExtractSection:
    def test_extracts_section(self):
        body = "## Objective\nBuild the feature.\n## Criteria\nMust pass tests.\n"
        result = _extract_section(body, "Objective")
        assert result == "Build the feature."

    def test_returns_empty_when_missing(self):
        body = "## Other\nContent\n"
        result = _extract_section(body, "Objective")
        assert result == ""


# ---------------------------------------------------------------------------
# _extract_test_commands
# ---------------------------------------------------------------------------


class TestExtractTestCommands:
    def test_extracts_pytest_commands(self):
        body = "Run `pytest tests/` and `npm test`."
        cmds = _extract_test_commands(body)
        assert "pytest tests/" in cmds
        assert "npm test" in cmds

    def test_ignores_non_command_backticks(self):
        body = "Use `myvar` in your code."
        cmds = _extract_test_commands(body)
        assert cmds == []

    def test_deduplicates(self):
        body = "Run `pytest tests/` and `pytest tests/` again."
        cmds = _extract_test_commands(body)
        assert len(cmds) == 1


# ---------------------------------------------------------------------------
# _parse_created
# ---------------------------------------------------------------------------


class TestParseCreated:
    def test_iso_with_timezone(self):
        result = _parse_created("2026-03-10T12:00:00Z")
        assert result.year == 2026
        assert result.month == 3

    def test_date_only(self):
        result = _parse_created("2026-01-15")
        assert result.year == 2026

    def test_empty_returns_min(self):
        from datetime import datetime
        result = _parse_created(None)
        assert result == datetime.min

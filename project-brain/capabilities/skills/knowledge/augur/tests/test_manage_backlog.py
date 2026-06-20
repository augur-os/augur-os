"""
Tests for manage_backlog — create placeholder backlog entries for knowledge tasks.

Module: skills/knowledge/scripts/manage_backlog.py
"""

import json
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# _load_context tests
# ---------------------------------------------------------------------------


class TestLoadContext:
    """Tests for _load_context JSON parsing with fallback to env."""

    def test_parses_valid_json_string(self):
        from skills.knowledge.scripts.manage_backlog import _load_context

        result = _load_context('{"key": "value"}')
        assert result == {"key": "value"}

    def test_invalid_json_returns_raw_wrapper(self):
        from skills.knowledge.scripts.manage_backlog import _load_context

        result = _load_context("not-json")
        assert result == {"raw": "not-json"}

    def test_none_falls_back_to_env(self, monkeypatch):
        from skills.knowledge.scripts.manage_backlog import _load_context

        monkeypatch.setenv("CHAIN_CONTEXT", '{"env_key": 1}')
        result = _load_context(None)
        assert result == {"env_key": 1}

    def test_none_with_no_env_returns_empty(self, monkeypatch):
        from skills.knowledge.scripts.manage_backlog import _load_context

        monkeypatch.delenv("CHAIN_CONTEXT", raising=False)
        result = _load_context(None)
        assert result == {}

    def test_none_with_invalid_env_returns_empty(self, monkeypatch):
        from skills.knowledge.scripts.manage_backlog import _load_context

        monkeypatch.setenv("CHAIN_CONTEXT", "broken-json")
        result = _load_context(None)
        assert result == {}


# ---------------------------------------------------------------------------
# main() integration tests
# ---------------------------------------------------------------------------


class TestMain:
    """Tests for the main() function creating backlog tasks."""

    def test_creates_backlog_file(self, tmp_path):
        from skills.knowledge.scripts.manage_backlog import main

        runtime_dir = tmp_path / "runtime"
        with (
            patch(
                "skills.knowledge.scripts.manage_backlog.get_runtime_dir",
                return_value=runtime_dir,
            ),
            patch("sys.argv", ["manage_backlog.py", "--json"]),
        ):
            exit_code = main()

        assert exit_code == 0

        backlog_dir = runtime_dir / "factory" / "knowledge" / "backlog"
        assert backlog_dir.exists()
        files = list(backlog_dir.glob("knowledge_*.json"))
        assert len(files) == 1

        task_data = json.loads(files[0].read_text())
        assert task_data["title"] == "Review knowledge gaps"
        assert task_data["id"].startswith("knowledge_")

"""
Tests for generate_docs — create a lightweight internal memo from context.

Module: skills/knowledge/scripts/generate_docs.py
"""

import json
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# _load_context tests
# ---------------------------------------------------------------------------


class TestLoadContext:
    """Tests for _load_context JSON parsing with env fallback."""

    def test_parses_valid_json(self):
        from skills.knowledge.scripts.generate_docs import _load_context

        result = _load_context('{"topic": "architecture"}')
        assert result == {"topic": "architecture"}

    def test_invalid_json_wraps_raw(self):
        from skills.knowledge.scripts.generate_docs import _load_context

        result = _load_context("plain text")
        assert result == {"raw": "plain text"}

    def test_none_reads_env(self, monkeypatch):
        from skills.knowledge.scripts.generate_docs import _load_context

        monkeypatch.setenv("CHAIN_CONTEXT", '{"from_env": true}')
        result = _load_context(None)
        assert result == {"from_env": True}

    def test_none_no_env_returns_empty(self, monkeypatch):
        from skills.knowledge.scripts.generate_docs import _load_context

        monkeypatch.delenv("CHAIN_CONTEXT", raising=False)
        result = _load_context(None)
        assert result == {}


# ---------------------------------------------------------------------------
# main() integration tests
# ---------------------------------------------------------------------------


class TestMain:
    """Tests for the main() function generating memo files."""

    def test_creates_memo_file(self, tmp_path):
        from skills.knowledge.scripts.generate_docs import main

        runtime_dir = tmp_path / "runtime"
        with (
            patch(
                "skills.knowledge.scripts.generate_docs.get_runtime_dir",
                return_value=runtime_dir,
            ),
            patch("sys.argv", ["generate_docs.py"]),
        ):
            exit_code = main()

        assert exit_code == 0

        reports_dir = runtime_dir / "factory" / "knowledge" / "reports"
        assert reports_dir.exists()
        files = list(reports_dir.glob("memo_*.md"))
        assert len(files) == 1

        content = files[0].read_text()
        assert "# Internal Memo" in content
        assert "Generated:" in content

    def test_json_output_mode(self, tmp_path, capsys):
        from skills.knowledge.scripts.generate_docs import main

        runtime_dir = tmp_path / "runtime"
        with (
            patch(
                "skills.knowledge.scripts.generate_docs.get_runtime_dir",
                return_value=runtime_dir,
            ),
            patch("sys.argv", ["generate_docs.py", "--json"]),
        ):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "ok"
        assert "memo_path" in data

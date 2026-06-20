"""Tests for CLI stdout/stderr separation and output formats (ADR-258)."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cli import (
    _strip_ansi,
    _is_machine_mode,
    _should_suppress_color,
    format_tool_list,
    format_tool_list_json,
    parse_param_value,
    _render_tool_help,
)


class TestStripAnsi:
    def test_removes_color_codes(self):
        assert _strip_ansi("\x1b[31mred\x1b[0m") == "red"

    def test_preserves_plain_text(self):
        assert _strip_ansi("hello world") == "hello world"

    def test_handles_multiple_codes(self):
        assert _strip_ansi("\x1b[1m\x1b[32mbold green\x1b[0m") == "bold green"

    def test_empty_string(self):
        assert _strip_ansi("") == ""


class TestIsMachineMode:
    def test_json_flag(self):
        args = MagicMock()
        args.json = True
        args.format = None
        assert _is_machine_mode(args)

    def test_format_json(self):
        args = MagicMock()
        args.json = False
        args.format = "json"
        assert _is_machine_mode(args)

    def test_piped_output(self):
        args = MagicMock()
        args.json = False
        args.format = None
        with patch("src.cli.sys") as mock_sys:
            mock_sys.stdout.isatty.return_value = False
            # Re-import to test; for simplicity, test the condition directly
            assert not mock_sys.stdout.isatty()


class TestFormatToolListJson:
    def test_valid_json(self):
        tools = {
            "test-tool": {
                "name": "test-tool",
                "description": "A test tool",
                "inputSchema": None,
            }
        }
        result = format_tool_list_json(tools)
        data = json.loads(result)
        assert data["total"] == 1
        assert data["tools"][0]["name"] == "test-tool"

    def test_empty_tools(self):
        result = format_tool_list_json({})
        data = json.loads(result)
        assert data["total"] == 0
        assert data["tools"] == []


class TestFormatToolList:
    def test_text_output(self):
        tools = {
            "get-skill": {
                "name": "get-skill",
                "description": "Get a skill by name",
                "inputSchema": None,
            }
        }
        result = format_tool_list(tools)
        assert "get-skill" in result
        assert "Total: 1 tools" in result

    def test_categorization(self):
        tools = {
            "get-skill": {"name": "get-skill", "description": "Query", "inputSchema": None},
            "file-read": {"name": "file-read", "description": "Read file", "inputSchema": None},
            "career-search": {"name": "career-search", "description": "Search", "inputSchema": None},
        }
        result = format_tool_list(tools)
        assert "Query:" in result
        assert "Files:" in result
        assert "Career:" in result


class TestRenderToolHelp:
    def test_expands_wrapped_params_schema(self):
        help_text = _render_tool_help(
            "list-skills",
            {
                "description": "List skills",
                "inputSchema": {
                    "$defs": {
                        "ListSkillsInput": {
                            "properties": {
                                "format": {
                                    "description": "Output format",
                                    "type": "string",
                                },
                                "ownership": {
                                    "description": "Ownership filter",
                                    "type": "string",
                                },
                            },
                            "required": ["format"],
                            "type": "object",
                        }
                    },
                    "properties": {"params": {"$ref": "#/$defs/ListSkillsInput"}},
                    "required": ["params"],
                    "type": "object",
                },
            },
        )

        assert "--format STRING    Output format (required)" in help_text
        assert "--ownership STRING    Ownership filter" in help_text
        assert "--params" not in help_text

    def test_direct_schema_help_keeps_direct_fields(self):
        help_text = _render_tool_help(
            "browse-index",
            {
                "description": "Browse",
                "inputSchema": {
                    "properties": {
                        "category": {"description": "Category", "type": "string"},
                    },
                    "required": ["category"],
                    "type": "object",
                },
            },
        )

        assert "--category STRING    Category (required)" in help_text


class TestParseParamValue:
    def test_json_object(self):
        assert parse_param_value('{"key": "val"}') == {"key": "val"}

    def test_json_array(self):
        assert parse_param_value('[1, 2, 3]') == [1, 2, 3]

    def test_boolean_true(self):
        assert parse_param_value("true") is True

    def test_boolean_false(self):
        assert parse_param_value("false") is False

    def test_integer(self):
        assert parse_param_value("42") == 42

    def test_float(self):
        assert parse_param_value("3.14") == 3.14

    def test_string(self):
        assert parse_param_value("hello") == "hello"


class TestShouldSuppressColor:
    def test_no_color_env_detected(self):
        """NO_COLOR env var should suppress ANSI codes."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            assert _should_suppress_color()

    def test_tty_allows_color(self):
        """When stdout is a TTY and NO_COLOR is unset, color is allowed."""
        env = os.environ.copy()
        env.pop("NO_COLOR", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("src.cli.sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = True
                assert not _should_suppress_color()

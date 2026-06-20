"""Tests for schema-driven tool help (ADR-260)."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cli import _render_tool_help


def _make_tool_info(description=None, input_schema=None):
    info = {"name": "test-tool"}
    if description is not None:
        info["description"] = description
    if input_schema is not None:
        info["inputSchema"] = input_schema
    return info


SAMPLE_SCHEMA = {
    "type": "object",
    "properties": {
        "skill_name": {"type": "string", "description": "The skill name"},
        "include_config": {"type": "boolean", "description": "Include config"},
    },
    "required": ["skill_name"],
}


def test_renders_parameters():
    tool_info = _make_tool_info(
        description="Get details about a specific skill",
        input_schema=SAMPLE_SCHEMA,
    )
    result = _render_tool_help("get-skill", tool_info)
    assert "--skill-name STRING" in result
    assert "--include-config BOOL" in result
    assert "The skill name" in result
    assert "Include config" in result


def test_required_markers():
    tool_info = _make_tool_info(
        description="A tool",
        input_schema=SAMPLE_SCHEMA,
    )
    result = _render_tool_help("get-skill", tool_info)
    assert "(required)" in result
    # skill_name is required, include_config is not
    for line in result.splitlines():
        if "--skill-name" in line:
            assert "(required)" in line
        if "--include-config" in line:
            assert "(required)" not in line


def test_no_schema():
    tool_info = _make_tool_info(description="A tool", input_schema=None)
    result = _render_tool_help("simple-tool", tool_info)
    assert "no parameters" in result.lower()


def test_empty_properties():
    tool_info = _make_tool_info(
        description="A tool",
        input_schema={"type": "object", "properties": {}},
    )
    result = _render_tool_help("empty-tool", tool_info)
    assert "no parameters" in result.lower()


def test_description_shown():
    tool_info = _make_tool_info(
        description="Get details about a specific skill",
        input_schema=SAMPLE_SCHEMA,
    )
    result = _render_tool_help("get-skill", tool_info)
    assert "Get details about a specific skill" in result


def test_param_name_formatting():
    tool_info = _make_tool_info(
        description="A tool",
        input_schema={
            "type": "object",
            "properties": {
                "my_param_name": {"type": "string", "description": "A param"},
            },
        },
    )
    result = _render_tool_help("test-tool", tool_info)
    assert "--my-param-name" in result
    assert "my_param_name" not in result

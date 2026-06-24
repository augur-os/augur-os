"""Unit tests for src._cli_mcp — pure CLI formatting and schema helpers."""

from __future__ import annotations

import json

import src._cli_mcp as cli_mcp


def test_parse_param_value_types():
    assert cli_mcp.parse_param_value("true") is True
    assert cli_mcp.parse_param_value("false") is False
    assert cli_mcp.parse_param_value("42") == 42
    assert cli_mcp.parse_param_value("3.14") == 3.14
    assert cli_mcp.parse_param_value('{"a": 1}') == {"a": 1}
    assert cli_mcp.parse_param_value("[1, 2, 3]") == [1, 2, 3]
    assert cli_mcp.parse_param_value("hello") == "hello"


def test_parse_param_value_invalid_json_falls_back_to_string():
    # Looks like JSON but is malformed -> treated as plain string.
    assert cli_mcp.parse_param_value("{not json") == "{not json"


def test_format_tool_list_groups_and_totals():
    tools = {
        "list-skills": {"description": "List all skills"},
        "google-calendar": {"description": "Google calendar tool"},
        "run-job": {"description": "Run a job\nsecond line ignored"},
        "mystery-tool": {"description": ""},
    }
    out = cli_mcp.format_tool_list(tools)
    assert "Available MCP Tools:" in out
    assert "Total: 4 tools" in out
    # Verb-based grouping
    assert "Query:" in out  # list-skills
    assert "Execution:" in out  # run-job
    # Hub-prefix grouping
    assert "Google:" in out
    # System fallback for unmatched
    assert "System:" in out
    # No-description rendering
    assert "(no description)" in out
    # Multiline description truncated to first line
    assert "second line ignored" not in out


def test_format_tool_list_json_roundtrip():
    tools = {
        "a": {"name": "a", "description": "first"},
        "b": {"name": "b", "description": "second"},
    }
    payload = json.loads(cli_mcp.format_tool_list_json(tools))
    assert payload["total"] == 2
    names = {t["name"] for t in payload["tools"]}
    assert names == {"a", "b"}


def test_schema_ref_target_resolves_local_defs():
    schema = {"$defs": {"Foo": {"type": "object", "title": "Foo"}}}
    resolved = cli_mcp._schema_ref_target(schema, "#/$defs/Foo")
    assert resolved == {"type": "object", "title": "Foo"}
    assert cli_mcp._schema_ref_target(schema, "#/$defs/Missing") is None
    assert cli_mcp._schema_ref_target(schema, "not-a-ref") is None


def test_wrapped_params_detection_and_packing():
    inner = {"type": "object", "properties": {"x": {"type": "string"}}}
    wrapped = {
        "properties": {"params": {"$ref": "#/$defs/Payload"}},
        "$defs": {"Payload": inner},
    }
    assert cli_mcp._wrapped_params_payload_schema(wrapped) == inner
    assert cli_mcp._schema_uses_wrapped_params(wrapped) is True

    plain = {"properties": {"x": {"type": "string"}}}
    assert cli_mcp._wrapped_params_payload_schema(plain) is None
    assert cli_mcp._schema_uses_wrapped_params(plain) is False


def test_pack_tool_params_for_schema():
    wrapped = {"properties": {"params": {"type": "object"}}}
    plain = {"properties": {"x": {"type": "string"}}}

    # Wrapped schema -> nest under "params"
    assert cli_mcp._pack_tool_params_for_schema({"x": 1}, wrapped) == {"params": {"x": 1}}
    # No schema -> also wrapped (conservative default)
    assert cli_mcp._pack_tool_params_for_schema({"x": 1}, None) == {"params": {"x": 1}}
    # No schema, empty params -> empty params payload
    assert cli_mcp._pack_tool_params_for_schema({}, None) == {"params": {}}
    # Plain schema -> pass through unchanged
    assert cli_mcp._pack_tool_params_for_schema({"x": 1}, plain) == {"x": 1}


def test_render_tool_help_with_params():
    info = {
        "description": "A demo tool\nignored second line",
        "inputSchema": {
            "properties": {
                "file_path": {"type": "string", "description": "Path to file"},
                "force": {"type": "boolean", "description": "Force it"},
            },
            "required": ["file_path"],
        },
    }
    rendered = cli_mcp._render_tool_help("demo", info)
    assert "demo — A demo tool" in rendered
    assert "ignored second line" not in rendered
    assert "--file-path" in rendered
    assert "STRING" in rendered
    assert "(required)" in rendered
    assert "--force" in rendered


def test_render_tool_help_no_params():
    info = {"description": "No params here", "inputSchema": {"properties": {}}}
    rendered = cli_mcp._render_tool_help("noargs", info)
    assert "This tool takes no parameters." in rendered


def test_print_manifest_markdown(capsys):
    manifest = {
        "manifest": {"name": "augur"},
        "focus": {"hub": "dev", "skill": "ingest"},
        "recommended_tools": [{"name": "list-skills", "skill": "core"}],
    }
    cli_mcp._print_manifest_markdown(manifest)
    out = capsys.readouterr().out
    assert "# augur capability manifest" in out
    assert "Focus: hub=dev skill=ingest" in out
    assert "- list-skills: core" in out

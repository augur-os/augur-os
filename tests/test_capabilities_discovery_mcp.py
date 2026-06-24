"""Unit tests for src.lib.capabilities._discovery_mcp.

Exercises the stateless MCP-tool AST helpers: declared-tool exposure
resolution from policy, decorator-name extraction, and scanning a real
Python source file for @tool decorators.
"""

from __future__ import annotations

import ast
from pathlib import Path

from src.lib.capabilities._discovery_mcp import (
    _declared_mcp_tool_exposure,
    _extract_mcp_tool_decorator_name,
    _script_mcp_tool_names,
)
from src.lib.capabilities._discovery_helpers import capability_id


def test_declared_mcp_tool_exposure_default_when_no_policy():
    assert _declared_mcp_tool_exposure("my-tool", {}) == ("mcp", "browse")
    # Non-dict capabilities entry -> default.
    assert _declared_mcp_tool_exposure("my-tool", {"capabilities": []}) == ("mcp", "browse")


def test_declared_mcp_tool_exposure_unclassified_entry_default():
    policy = {
        "capabilities": {
            capability_id("mcp-tool", "my-tool"): {
                "classification_status": "draft",
                "export_to": "mcp",
            }
        }
    }
    # status not in approved/blocked/deprecated -> default exposure.
    assert _declared_mcp_tool_exposure("my-tool", policy) == ("mcp", "browse")


def test_declared_mcp_tool_exposure_blocked_removes_mcp():
    policy = {
        "capabilities": {
            capability_id("mcp-tool", "secret"): {
                "classification_status": "blocked",
                "export_to": "browse",
            }
        }
    }
    # blocked + mcp not in export_to -> mcp dropped; cli/agents-md only added
    # for approved/deprecated, so blocked keeps just browse.
    assert _declared_mcp_tool_exposure("secret", policy) == ("browse",)


def test_declared_mcp_tool_exposure_approved_prepends_cli_and_agents():
    policy = {
        "capabilities": {
            capability_id("mcp-tool", "pub"): {
                "classification_status": "approved",
                "export_to": ["mcp", "cli", "agents-md"],
            }
        }
    }
    result = _declared_mcp_tool_exposure("pub", policy)
    # cli and agents-md prepended (insert at 0 in reversed iteration order),
    # mcp retained because it's in export_to, browse retained from default.
    assert result == ("cli", "agents-md", "mcp", "browse")


def test_extract_mcp_tool_decorator_name_positional():
    tree = ast.parse('@mcp.tool("named-tool")\ndef f():\n    pass\n')
    func = tree.body[0]
    decorator = func.decorator_list[0]
    assert _extract_mcp_tool_decorator_name(decorator) == "named-tool"


def test_extract_mcp_tool_decorator_name_keyword():
    tree = ast.parse('@server.tool(name="kw-tool")\ndef f():\n    pass\n')
    decorator = tree.body[0].decorator_list[0]
    assert _extract_mcp_tool_decorator_name(decorator) == "kw-tool"


def test_extract_mcp_tool_decorator_name_rejects_non_tool():
    tree = ast.parse('@app.route("/x")\ndef f():\n    pass\n')
    decorator = tree.body[0].decorator_list[0]
    assert _extract_mcp_tool_decorator_name(decorator) == ""
    # Plain Name decorator (not a Call) -> "".
    tree2 = ast.parse("@staticmethod\ndef f():\n    pass\n")
    assert _extract_mcp_tool_decorator_name(tree2.body[0].decorator_list[0]) == ""


def test_script_mcp_tool_names_scans_real_file(tmp_path: Path):
    src = '''
import mcp

@mcp.tool("first-tool")
def first():
    return 1

@mcp.tool(name="second-tool")
async def second():
    return 2

@mcp.tool("first-tool")
def duplicate():
    return 3

def not_a_tool():
    return 4
'''
    py_file = tmp_path / "tools.py"
    py_file.write_text(src, encoding="utf-8")
    names = _script_mcp_tool_names(py_file)
    # Dedupes "first-tool", keeps order of first occurrence.
    assert names == ("first-tool", "second-tool")


def test_script_mcp_tool_names_handles_syntax_error_and_missing(tmp_path: Path):
    bad = tmp_path / "broken.py"
    bad.write_text("def f(:\n    pass\n", encoding="utf-8")
    assert _script_mcp_tool_names(bad) == ()
    missing = tmp_path / "nope.py"
    assert _script_mcp_tool_names(missing) == ()

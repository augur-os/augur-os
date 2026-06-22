"""Smoke test: launch augur-framework stdio server and verify tools/list."""

from __future__ import annotations

import pytest
import json
import os
import subprocess
import sys
import time
from pathlib import Path

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="spawns the MCP/bundle server subprocess, which emits a console CTRL event at shutdown that destabilizes the Windows test runner; server behavior is covered on POSIX. Validation pending (ROADMAP)",
)


def _list_augur_framework_tools(extra_env: dict[str, str] | None = None) -> list[dict]:
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{project_root}:{env.get('PYTHONPATH', '')}"
    env["PYTHONUNBUFFERED"] = "1"
    if extra_env:
        env.update(extra_env)

    proc = subprocess.Popen(
        [sys.executable, "-m", "src.mcp.augur_framework"],
        cwd=str(project_root),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        # Isolate the child into its own process group on Windows so a console
        # Ctrl+C/Break event it sees can never propagate up to pytest (which
        # would abort the whole run with a spurious KeyboardInterrupt).
        creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0),
    )
    try:
        init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "0"},
            },
        }
        ls = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        assert proc.stdin and proc.stdout
        proc.stdin.write((json.dumps(init) + "\n").encode())
        proc.stdin.write((json.dumps(ls) + "\n").encode())
        proc.stdin.flush()

        deadline = time.monotonic() + 20.0
        responses: list[dict] = []
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            try:
                responses.append(json.loads(line.decode()))
            except json.JSONDecodeError:
                continue
            if any(r.get("id") == 2 for r in responses):
                break

        tools = next((r for r in responses if r.get("id") == 2), None)
        assert tools is not None, f"no tools/list response; got {responses!r}"
        return tools["result"]["tools"]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_augur_framework_server_starts_and_lists_tools() -> None:
    tool_names = [tool["name"] for tool in _list_augur_framework_tools()]
    n = len(tool_names)
    # Track 3a PR 5 + Track 4: augur-framework now exposes its full
    # tool surface (300+) to AI clients; the CURATED_VISIBLE_TOOLS
    # visibility filter that previously hid most tools was removed in
    # Track 4. Wide bound covers tool additions/removals over time.
    assert 100 <= n <= 450, f"expected 100-450 tools in augur-framework, got {n}"


def test_augur_framework_client_id_parser() -> None:
    from src.mcp.augur_framework.__main__ import _client_id_from_argv

    assert _client_id_from_argv(["--client-id", "client-mcp"]) == "client-mcp"
    assert _client_id_from_argv(["--client-id=dashboard-Augur-p1"]) == "dashboard-Augur-p1"
    assert _client_id_from_argv([]) == "mcp"


def test_augur_framework_dashboard_mode_includes_core_tools() -> None:
    tool_names = set(
        tool["name"] for tool in _list_augur_framework_tools({"AUGUR_DASHBOARD_MCP_INCLUDE_CORE_TOOLS": "1"})
    )

    assert {
        "health",
        "get-preferences",
        "list-skills",
        "brain-active-context",
        "brain-discovery",
        "reindex-browse-category",
        "update-preference",
    }.issubset(tool_names)


def test_augur_framework_tool_schemas_are_provider_compatible() -> None:
    schema_keys = {"type", "anyOf", "oneOf", "allOf", "$ref", "enum", "const"}
    violations: list[str] = []

    def resolve(schema: dict, root: dict) -> dict:
        ref = schema.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            return root.get("$defs", {})[ref.removeprefix("#/$defs/")]
        return schema

    def visit(schema: object, root: dict, path: str) -> None:
        if not isinstance(schema, dict):
            return
        schema = resolve(schema, root)
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for name, prop in properties.items():
                prop_path = f"{path}.properties.{name}"
                if isinstance(prop, dict):
                    resolved = resolve(prop, root)
                    if isinstance(resolved, dict) and not schema_keys.intersection(resolved):
                        violations.append(f"{prop_path}: {resolved}")
                visit(prop, root, prop_path)
        for key in ("anyOf", "oneOf", "allOf"):
            for index, child in enumerate(schema.get(key, []) or []):
                visit(child, root, f"{path}.{key}[{index}]")
        if "items" in schema:
            visit(schema["items"], root, f"{path}.items")

    for tool in _list_augur_framework_tools():
        input_schema = tool.get("inputSchema") or {}
        visit(input_schema, input_schema, tool["name"])

    assert violations == []

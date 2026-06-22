"""Integration test: launch augur_shared.bundle_server for apple and
verify tools/list returns apple's tools.

Requires the apple bundle to exist at ~/Projects/Au-vault/skills/apple/.
Skipped on systems without the vault repo present.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="spawns the MCP/bundle server subprocess, which emits a console CTRL event at shutdown that destabilizes the Windows test runner; server behavior is covered on POSIX. Validation pending (ROADMAP)",
)

APPLE_BUNDLE = Path.home() / "Projects" / "Au-vault" / "skills" / "apple"


@pytest.mark.skipif(not APPLE_BUNDLE.exists(), reason="Au-vault apple bundle not present locally")
def test_apple_per_bundle_server_starts_and_lists_tools() -> None:
    """Launch the per-bundle server for apple, send tools/list, verify response."""
    project_root = Path(__file__).resolve().parents[2]

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{project_root}:{env.get('PYTHONPATH', '')}"
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "-m", "src.mcp.augur_shared.bundle_server", "apple"],
        cwd=str(project_root),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        # Own process group on Windows so a child console Ctrl event can't
        # propagate a spurious KeyboardInterrupt up to pytest.
        creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0),
    )

    try:
        # Send MCP initialize then tools/list over stdio.
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "track2-test", "version": "0.0.0"},
            },
        }
        list_msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        assert proc.stdin is not None
        assert proc.stdout is not None
        proc.stdin.write((json.dumps(init_msg) + "\n").encode())
        proc.stdin.write((json.dumps(list_msg) + "\n").encode())
        proc.stdin.flush()

        # Drain output for a few seconds; FastMCP responds line-by-line.
        deadline = time.monotonic() + 10.0
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

        tools_response = next((r for r in responses if r.get("id") == 2), None)
        assert tools_response is not None, f"no tools/list response; got {responses!r}"
        tools = tools_response["result"]["tools"]
        assert len(tools) > 0, f"apple per-bundle server returned no tools; full response: {tools_response!r}"
        # Sanity: should include known apple tool names. Tolerant match.
        names = {t["name"] for t in tools}
        assert any(
            "apple" in n.lower() or "note" in n.lower() or "calendar" in n.lower() for n in names
        ), f"no recognizable apple tool names in {sorted(names)}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

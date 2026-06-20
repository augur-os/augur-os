"""Integration test: launch augur_shared.bundle_server for ingest."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

INGEST_BUNDLE = Path.home() / "Projects" / "Au-vault" / "skills" / "ingest"


@pytest.mark.skipif(not INGEST_BUNDLE.exists(), reason="Au-vault ingest bundle not present")
def test_ingest_per_bundle_server_starts_and_lists_tools() -> None:
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{project_root}:{env.get('PYTHONPATH', '')}"
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "-m", "src.mcp.augur_shared.bundle_server", "ingest"],
        cwd=str(project_root),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "0"},
            },
        }
        list_msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write((json.dumps(init_msg) + "\n").encode())
        proc.stdin.write((json.dumps(list_msg) + "\n").encode())
        proc.stdin.flush()
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
        assert tools_response is not None
        assert len(tools_response["result"]["tools"]) > 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

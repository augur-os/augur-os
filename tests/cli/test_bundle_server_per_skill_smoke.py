"""Integration smoke test: augur_shared.bundle_server can wrap any vault skill.

The contract under test belongs to `augur_shared.bundle_server` (repo-level).
We exercise it against whichever vault-side skill bundle is present on the
developer's machine — set AUGUR_BUNDLE_SERVER_TEST_SKILL to pick one
explicitly, otherwise we auto-pick the first available skill under
~/Projects/Au-vault/skills/. Skips cleanly when no vault skill is reachable.

Renamed + parameterized from test_bundle_server_file_manager.py to avoid
hard-coding a staged-skill name (file-manager / books / plugin-pack) into the
central tests/ directory. The test was leaking knowledge of unreleased skills
into a tree that's destined for upstream packaging.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

VAULT_SKILLS_ROOT = Path.home() / "Projects" / "Au-vault" / "skills"


def _pick_skill() -> str | None:
    """Pick a vault skill to wrap. Env var override > first listed dir."""
    override = os.environ.get("AUGUR_BUNDLE_SERVER_TEST_SKILL")
    if override:
        return override if (VAULT_SKILLS_ROOT / override).is_dir() else None
    if not VAULT_SKILLS_ROOT.is_dir():
        return None
    candidates = sorted(p.name for p in VAULT_SKILLS_ROOT.iterdir() if p.is_dir() and not p.name.startswith("."))
    return candidates[0] if candidates else None


@pytest.mark.skipif(_pick_skill() is None, reason="No vault skill bundle present to wrap")
def test_bundle_server_starts_and_lists_tools_for_a_vault_skill() -> None:
    skill_name = _pick_skill()
    assert skill_name is not None  # for type narrowing; skipif guarded

    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{project_root}:{env.get('PYTHONPATH', '')}"
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "-m", "src.mcp.augur_shared.bundle_server", skill_name],
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
        assert tools_response is not None, f"No tools/list response for skill {skill_name!r}"
        assert len(tools_response["result"]["tools"]) > 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

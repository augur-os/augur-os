"""Tests for scripts/generate-worktree-mcp.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_worktree_mcp_stdout_uses_core_only_project_tier_server(tmp_path: Path) -> None:
    script = Path("scripts/generate-worktree-mcp.py")

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--path",
            str(tmp_path),
            "--stdout",
            "--mcp-port",
            "8091",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    config = json.loads(result.stdout)
    servers = config["mcpServers"]

    assert set(servers) == {"augur-core"}
    assert servers["augur-core"]["args"] == ["-m", "augur_core", "--client-id", "worktree"]
    assert "augur_mcp" not in result.stdout
    assert "augur_framework" not in result.stdout


def test_worktree_mcp_generation_is_json_valid_and_ascii_on_windows_paths(tmp_path: Path) -> None:
    script = Path("scripts/generate-worktree-mcp.py")

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--path",
            str(tmp_path),
            "--client",
            "claude",
            "--mcp-port",
            "8091",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result.stdout.encode("ascii")
    assert "Generated .claude" in result.stdout

    config = json.loads((tmp_path / ".claude" / "mcp.json").read_text(encoding="utf-8"))
    server = config["mcpServers"]["augur-core"]
    assert "\\" not in server["cwd"]
    assert server["cwd"] == tmp_path.resolve().as_posix()
    assert server["env"]["MCP_PORT"] == "8091"


def test_worktree_mcp_copilot_writes_repo_root_mcp_json(tmp_path: Path) -> None:
    """Copilot reads the repo-root .mcp.json via gca's --additional-mcp-config

    injection; fresh worktrees must get it or copilot sessions launch with
    no Augur MCP servers at all.
    """
    script = Path("scripts/generate-worktree-mcp.py")

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--path",
            str(tmp_path),
            "--client",
            "copilot",
            "--mcp-port",
            "8091",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    config = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    server = config["mcpServers"]["augur-core"]
    assert server["cwd"] == tmp_path.resolve().as_posix()
    assert "$WORKTREE_PATH" not in (tmp_path / ".mcp.json").read_text(encoding="utf-8")

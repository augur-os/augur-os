"""
scripts._launch_session — Session owner and client exec helpers for the agent launcher.

Covers: Windows executable resolution, terminal reset, exec_client, Popen-based
client launch with session claiming/releasing, and the session-owner watchdog.

Split from src/scripts/agent_launch.py (WS5, behavior-preserving).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

NATIVE_TERMINAL_SURFACE = "native-terminal"
SESSION_OWNER_WATCHDOG_INTERVAL_SECONDS = 2.0


def with_copilot_project_mcp(command: list[str], cwd: Path) -> list[str]:
    """Append the checkout-local project MCP config to copilot launches.

    Project-scoped Augur servers never ship in ~/.copilot/mcp-config.json;
    copilot only sees them via --additional-mcp-config. The path is relative
    so it resolves inside whichever checkout the session runs from.
    """
    if not command or command[0] != "copilot":
        return command
    if "--additional-mcp-config" in command:
        return command
    if not (cwd / ".mcp.json").exists():
        return command
    return [command[0], "--additional-mcp-config", "@.mcp.json", *command[1:]]


def _resolve_windows_executable(command: str, env: dict[str, str] | None = None) -> str:
    search_path = env.get("PATH") if env is not None else None
    resolved = shutil.which(command, path=search_path)
    if resolved is None:
        raise FileNotFoundError(command)
    return resolved


def _is_windows() -> bool:
    """Windows detection seam. Tests patch THIS (not the global os.name) so that
    simulating Windows never mutates os.name globally — mutating os.name makes
    pathlib.Path() construct WindowsPath, which raises on non-Windows runners and
    leaks into unrelated fixture teardowns under CI collection order."""
    return os.name == "nt"


def _reset_windows_terminal_input_modes() -> None:
    if not _is_windows() or "WT_SESSION" not in os.environ:
        return
    try:
        sys.stdout.write("\x1b[?2004l\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l")
        sys.stdout.flush()
    except OSError:
        pass


def exec_client(command: list[str], env: dict[str, str] | None = None) -> None:
    if command[:1] == ["copilot"]:
        command = with_copilot_project_mcp(command, Path.cwd())
    try:
        if _is_windows():
            executable = _resolve_windows_executable(command[0], env)
            try:
                result = subprocess.run([executable, *command[1:]], env=env, check=False)
            finally:
                _reset_windows_terminal_input_modes()
            raise SystemExit(result.returncode)
        if env is None:
            os.execvp(command[0], command)
        else:
            os.execvpe(command[0], command, env)
    except FileNotFoundError as exc:
        raise RuntimeError(f"AI client executable not found: {command[0]}") from exc


def _decode_session_owner_response(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("session ownership tool returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("session ownership tool returned a non-object response")
    return data


def claim_native_terminal_session(session_id: str, pid: int, cli_id: str) -> None:
    from src.mcp.augur_framework.tools.infrastructure.session_owners import (
        SessionClaimInput,
        session_claim_impl,
    )

    raw = asyncio.run(
        session_claim_impl(
            SessionClaimInput(
                session_id=session_id,
                surface=NATIVE_TERMINAL_SURFACE,
                pid=pid,
                cli_id=cli_id,
            )
        )
    )
    data = _decode_session_owner_response(raw)
    if data.get("ok") is True:
        return

    conflict = data.get("conflict")
    if isinstance(conflict, dict):
        owner_surface = conflict.get("surface", "unknown")
        owner_pid = conflict.get("pid", "unknown")
        owner_host = conflict.get("host", "unknown")
        raise RuntimeError(f"session {session_id} is already owned by {owner_surface} pid {owner_pid} on {owner_host}")
    raise RuntimeError(f"session {session_id} could not be claimed by native terminal")


def release_native_terminal_session(session_id: str, pid: int) -> None:
    from src.mcp.augur_framework.tools.infrastructure.session_owners import (
        SessionReleaseInput,
        session_release_impl,
    )

    raw = asyncio.run(
        session_release_impl(
            SessionReleaseInput(
                session_id=session_id,
                surface=NATIVE_TERMINAL_SURFACE,
                pid=pid,
            )
        )
    )
    data = _decode_session_owner_response(raw)
    if data.get("ok") is not True:
        raise RuntimeError(f"session {session_id} could not be released by native terminal")


def _native_terminal_owner_is_current(session_id: str, pid: int) -> bool:
    from src.mcp.augur_framework.tools.infrastructure.session_owners import (
        SessionStatusInput,
        session_status_impl,
    )

    raw = asyncio.run(session_status_impl(SessionStatusInput(session_id=session_id)))
    data = _decode_session_owner_response(raw)
    if data.get("ok") is not True:
        return True
    owner = data.get("owner")
    if not isinstance(owner, dict):
        return False
    return owner.get("surface") == NATIVE_TERMINAL_SURFACE and owner.get("pid") == pid


def _popen_client(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.Popen:
    command = with_copilot_project_mcp(command, cwd)
    try:
        if _is_windows():
            executable = _resolve_windows_executable(command[0], env)
            return subprocess.Popen([executable, *command[1:]], cwd=cwd, env=env)
        return subprocess.Popen(command, cwd=cwd, env=env)
    except FileNotFoundError as exc:
        raise RuntimeError(f"AI client executable not found: {command[0]}") from exc


def _terminate_unclaimed_child(process: subprocess.Popen) -> None:
    try:
        process.terminate()
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    except ProcessLookupError:
        return


# run_handoff_client lives in agent_launch.py (must call claim/release via agent_launch globals for test monkeypatching)

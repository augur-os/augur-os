from __future__ import annotations

import argparse
import json
import os
import shutil  # noqa: F401 — exposed as agent_launch.shutil for test monkeypatching
import subprocess  # noqa: F401 — exposed as agent_launch.subprocess for test monkeypatching
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Re-export git helpers (stable public surface — tests access via agent_launch.*)
from src.scripts._launch_git import (  # noqa: F401
    abort_merge_if_active,
    abort_rebase_if_active,
    git_stdout,
    prompt_safe_sync,
    repo_is_dirty,
    restore_stash,
    rev_count,
    run_git,
    safe_sync_main_checkout,
    stash,
    sync_main_checkout,
)

# Re-export worktree helpers (stable public surface — tests access via agent_launch.*)
# Note: create_worktree is defined below (calls resolved via agent_launch globals for monkeypatching)
from src.scripts._launch_worktree import (  # noqa: F401
    bootstrap_worktree,
    derive_worktree_name,
    generate_mcp_config,
    helper_env,
    register_worktree,
    resolve_base_ref,
    run_python_helper,
)

# Re-export session/client helpers (stable public surface — tests access via agent_launch.*)
# Note: _start_session_owner_watchdog and run_handoff_client are defined below
from src.scripts._launch_session import (  # noqa: F401
    NATIVE_TERMINAL_SURFACE,
    SESSION_OWNER_WATCHDOG_INTERVAL_SECONDS,
    _decode_session_owner_response,
    _is_windows,
    _native_terminal_owner_is_current,
    _popen_client,
    _reset_windows_terminal_input_modes,
    _resolve_windows_executable,
    _terminate_unclaimed_child,
    claim_native_terminal_session,
    exec_client,
    release_native_terminal_session,
    with_copilot_project_mcp,
)


def _start_session_owner_watchdog(
    process: subprocess.Popen,
    *,
    session_id: str,
    pid: int,
) -> threading.Event:
    """Start a watchdog thread that terminates the child if the session claim is released.

    Defined in agent_launch.py (not _launch_session.py) so that tests can monkeypatch
    agent_launch._native_terminal_owner_is_current and agent_launch.SESSION_OWNER_WATCHDOG_INTERVAL_SECONDS.
    """
    stop_event = threading.Event()

    def watch() -> None:
        while not stop_event.wait(SESSION_OWNER_WATCHDOG_INTERVAL_SECONDS):
            poll = getattr(process, "poll", None)
            if callable(poll) and poll() is not None:
                return
            try:
                current = _native_terminal_owner_is_current(session_id, pid)
            except Exception as exc:  # noqa: BLE001 - transient MCP state must not kill the client.
                import sys as _sys

                print(f"Warning: failed to check session owner: {exc}", file=_sys.stderr)
                continue
            if not current:
                _terminate_unclaimed_child(process)
                return

    thread = threading.Thread(
        target=watch,
        name=f"augur-session-owner-watchdog-{pid}",
        daemon=True,
    )
    thread.start()
    return stop_event


def run_handoff_client(
    command: list[str],
    *,
    cwd: Path,
    session_id: str,
    cli_id: str,
    env: dict[str, str] | None = None,
) -> int:
    """Launch client via Popen, claim the session, run the watchdog, then release.

    Defined in agent_launch.py (not _launch_session.py) so that tests can monkeypatch
    agent_launch.claim_native_terminal_session and agent_launch.release_native_terminal_session.
    """
    process = _popen_client(command, cwd=cwd, env=env)
    claimed = False
    watchdog_stop: threading.Event | None = None
    try:
        try:
            claim_native_terminal_session(session_id, process.pid, cli_id)
            claimed = True
            watchdog_stop = _start_session_owner_watchdog(
                process,
                session_id=session_id,
                pid=process.pid,
            )
        except Exception:
            _terminate_unclaimed_child(process)
            raise
        return process.wait()
    finally:
        if watchdog_stop is not None:
            watchdog_stop.set()
        if claimed:
            try:
                release_native_terminal_session(session_id, process.pid)
            except Exception as exc:  # noqa: BLE001 - launcher cleanup must not hide client exit status.
                import sys as _sys

                print(f"Warning: failed to release session owner: {exc}", file=_sys.stderr)
        _reset_windows_terminal_input_modes()


def create_worktree(repo: Path, command: list[str]) -> None:
    """Create a new git worktree, bootstrap it, then exec the client inside.

    Defined in agent_launch.py (not _launch_worktree.py) so that tests can monkeypatch
    agent_launch.resolve_base_ref, agent_launch.run_git, agent_launch.register_worktree,
    agent_launch.bootstrap_worktree, agent_launch.generate_mcp_config, agent_launch.exec_client.
    """
    name = derive_worktree_name()
    wt_dir = repo.parent / f"augur-{name}"
    base_ref = resolve_base_ref(repo)

    if not wt_dir.exists():
        run_git(repo, "worktree", "add", str(wt_dir), "-b", name, base_ref)

    register_worktree(repo, wt_dir, name)
    bootstrap_worktree(repo, wt_dir)
    generate_mcp_config(repo, wt_dir, name)

    last_wt_file = os.environ.get("AUGUR_LAST_WORKTREE_FILE")
    if last_wt_file:
        try:
            Path(last_wt_file).write_text(str(wt_dir), encoding="utf-8")
        except Exception as e:
            print(f"Warning: failed to write worktree path to handoff file: {e}", file=sys.stderr)

    env = os.environ.copy()
    env.update(
        {
            "AUGUR_ROOT": str(wt_dir),
            "AUGUR_CORE": str(wt_dir),
            "AUGUR_REPO": str(wt_dir),
        }
    )
    os.chdir(wt_dir)
    exec_client(command, env)


CLIENTS = {
    "codex": ["codex", "--dangerously-bypass-approvals-and-sandbox"],
    "claude": ["claude", "--dangerously-skip-permissions"],
    "gemini": ["gemini", "--yolo"],
    "copilot": ["copilot", "--allow-all"],
}

AUTO_APPROVE_FLAGS = {
    "--dangerously-skip-permissions",
    "--dangerously-bypass-approvals-and-sandbox",
    "--full-auto",
    "--yolo",
    "--force",
    "--approve-mcps",
    "--allow-all",
}

SHORTCUTS = {
    "codex": "xa",
    "claude": "ca",
    "gemini": "ga",
    "copilot": "gca",
}

HANDOFF_TTL_SECONDS = 15 * 60
HANDOFF_CLOCK_SKEW_SECONDS = 60
CODEX_LATEST_SESSION_ID = "__codex_latest__"


@dataclass(frozen=True)
class LaunchRequest:
    client: str
    desktop: bool
    dry_run: bool
    extra_args: list[str]
    repo_root: Path
    handoff_file: Path | None = None
    selected_mode: str | None = None


def prompt_mode(client: str) -> str:
    while True:
        print(f"Start {client} in:")
        print("  1) main")
        print("  2) new worktree")
        print("Select [1-2]: ", end="", flush=True)
        choice = sys.stdin.readline()
        if choice == "":
            raise RuntimeError("selection cancelled")

        normalized = choice.strip().lower()
        if normalized in {"1", "main"}:
            return "main"
        if normalized in {"2", "worktree"}:
            return "worktree"
        print("Invalid choice. Enter 1 or 2.")


def normalize_mode_selection(mode: str) -> str | None:
    normalized = mode.strip().lower().replace("_", "-")
    if normalized in {"1", "main"}:
        return "main"
    if normalized in {"2", "worktree", "new", "new-worktree"}:
        return "worktree"
    return None


def consume_choose_mode(extra_args: list[str], parser: argparse.ArgumentParser) -> tuple[str | None, list[str]]:
    if not extra_args:
        return None, extra_args
    if extra_args[0] != "choose":
        return None, extra_args
    if len(extra_args) < 2:
        parser.error("choose requires a mode: main or worktree")
    selected_mode = normalize_mode_selection(extra_args[1])
    if selected_mode is None:
        parser.error("choose mode must be main or worktree")
    return selected_mode, extra_args[2:]


def parse_args(argv: list[str]) -> LaunchRequest:
    parser = argparse.ArgumentParser(
        description="Launch an AI client in main, a new worktree, or Codex Desktop.",
        epilog=(
            "Supported clients: codex, claude, gemini, copilot. "
            "Modes: main, new worktree, or --desktop for Codex Desktop. "
            "Use 'choose main' or 'choose worktree' to select a mode without the prompt."
        ),
    )
    parser.add_argument("--client", choices=sorted(CLIENTS), required=True)
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Open Codex Desktop for this repo without the main/worktree prompt.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--handoff-file")
    args, extra_args = parser.parse_known_args(argv)

    explicit_client_args = extra_args[:1] == ["--"]
    if extra_args[:1] == ["--"]:
        extra_args = extra_args[1:]
    selected_mode = None
    if not explicit_client_args:
        selected_mode, extra_args = consume_choose_mode(extra_args, parser)
        # "choose main -- <flags>": the separator only delimits forwarded
        # args and must not reach the client binary.
        if extra_args[:1] == ["--"]:
            extra_args = extra_args[1:]

    if args.desktop and args.client != "codex":
        parser.error("--desktop is only supported for --client codex")

    default_root = Path(__file__).resolve().parents[2]
    repo_root = Path(os.environ.get("AI_PROJECT_ROOT", default_root)).resolve()
    return LaunchRequest(
        client=args.client,
        desktop=args.desktop,
        dry_run=args.dry_run,
        extra_args=extra_args,
        repo_root=repo_root,
        handoff_file=Path(args.handoff_file).resolve() if args.handoff_file else None,
        selected_mode=selected_mode,
    )


def command_for(request: LaunchRequest) -> list[str]:
    return [*CLIENTS[request.client], *request.extra_args]


def desktop_command_for(request: LaunchRequest) -> list[str]:
    return ["codex", "app", str(request.repo_root), *request.extra_args]


def format_command(command: list[str]) -> str:
    return " ".join(command)


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"handoff payload {key} must be a non-empty string")
    return value.strip()


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"handoff payload {key} must be a non-empty string")
    return value.strip()


def _require_route(payload: dict[str, Any]) -> dict[str, Any]:
    route = payload.get("route")
    if not isinstance(route, dict):
        raise RuntimeError("handoff payload route must be an object")
    airplane_mode = route.get("airplane_mode")
    if not isinstance(airplane_mode, bool):
        raise RuntimeError("handoff payload route.airplane_mode must be a boolean")
    launch_argv = route.get("launch_argv")
    if airplane_mode is True and (
        not isinstance(launch_argv, list) or not all(isinstance(arg, str) and arg for arg in launch_argv)
    ):
        raise RuntimeError("airplane handoff payload must include launch_argv")
    return route


def load_handoff_payload(path: Path, client: str) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"handoff payload not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("handoff payload must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("handoff payload must be a JSON object")
    if payload.get("version") != 1:
        raise RuntimeError("handoff payload version must be 1")
    created_at = _require_str(payload, "created_at")
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp()
    except ValueError as exc:
        raise RuntimeError("handoff payload created_at must be ISO-8601") from exc
    now = time.time()
    if now - created > HANDOFF_TTL_SECONDS:
        raise RuntimeError("handoff payload has expired")
    if created - now > HANDOFF_CLOCK_SKEW_SECONDS:
        raise RuntimeError("handoff payload created_at is outside the allowed time window")
    payload_client = _require_str(payload, "cli_id")
    if payload_client != client:
        raise RuntimeError(f"handoff payload cli_id {payload_client} does not match requested client {client}")
    expected_shortcut = SHORTCUTS.get(client)
    if _require_str(payload, "shortcut") != expected_shortcut:
        raise RuntimeError(f"handoff payload shortcut must be {expected_shortcut}")
    _require_str(payload, "session_id")
    cwd = Path(_require_str(payload, "cwd"))
    if not cwd.exists() or not cwd.is_dir():
        raise RuntimeError(f"handoff cwd is not a directory: {cwd}")
    _require_str(payload, "current_page")
    _require_str(payload, "dashboard_mode")
    _require_str(payload, "theme_mode")
    _require_route(payload)
    return payload


def strip_auto_approve_flags(args: list[str]) -> list[str]:
    return [arg for arg in args if arg not in AUTO_APPROVE_FLAGS]


def resume_command_for(client: str, session_id: str) -> list[str]:
    base = CLIENTS[client]
    if client == "codex":
        if session_id == CODEX_LATEST_SESSION_ID:
            return [base[0], "resume", "--last", *base[1:]]
        return [base[0], "resume", session_id, *base[1:]]
    return [*base, "--resume", session_id]


def command_for_handoff(payload: dict[str, Any]) -> list[str]:
    client = _require_str(payload, "cli_id")
    session_id = _require_str(payload, "session_id")
    command = resume_command_for(client, session_id)
    handoff_prompt = _optional_str(payload, "handoff_prompt")
    if handoff_prompt:
        command = [*command, handoff_prompt]
    route = _require_route(payload)
    launch_argv = route.get("launch_argv")
    if route.get("airplane_mode") is True:
        if not isinstance(launch_argv, list):
            raise RuntimeError("airplane handoff payload must include launch_argv")
        return [*launch_argv, *strip_auto_approve_flags(command[1:])]
    return command


def main(argv: list[str] | None = None) -> int:
    try:
        request = parse_args(list(argv if argv is not None else sys.argv[1:]))
        if request.handoff_file is not None:
            payload = load_handoff_payload(request.handoff_file, request.client)
            command = command_for_handoff(payload)
            command_text = format_command(command)
            cwd = Path(_require_str(payload, "cwd")).resolve()
            if request.dry_run or os.environ.get("AI_NO_EXEC") == "1":
                print(f"mode=handoff repo={cwd} command={command_text}")
                return 0
            return run_handoff_client(
                command,
                cwd=cwd,
                session_id=_require_str(payload, "session_id"),
                cli_id=_require_str(payload, "cli_id"),
            )

        if request.desktop:
            command = desktop_command_for(request)
            command_text = format_command(command)
            if request.dry_run or os.environ.get("AI_NO_EXEC") == "1":
                print(f"mode=desktop repo={request.repo_root} command={command_text}")
                return 0

            os.chdir(request.repo_root)
            exec_client(command)
            return 0

        command = command_for(request)
        command_text = format_command(command)
        mode = request.selected_mode or prompt_mode(request.client)

        if mode == "main":
            if request.dry_run:
                print(f"mode=main repo={request.repo_root} sync_target=origin/main command={command_text}")
                return 0

            sync_main_checkout(request.repo_root)
            if os.environ.get("AI_NO_EXEC") == "1":
                print(f"mode=main repo={request.repo_root} sync_target=origin/main command={command_text}")
                return 0

            os.chdir(request.repo_root)
            exec_client(command)

        if request.dry_run or os.environ.get("AI_NO_EXEC") == "1":
            print(f"mode=worktree repo={request.repo_root} command=create-worktree -- {command_text}")
            return 0

        create_worktree(request.repo_root, command)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

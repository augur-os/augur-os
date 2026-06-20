#!/usr/bin/env python3
"""
IDE Bridge - Shared resource for interacting with Agentic IDEs.
Handles auto-detection, prompt pasting, and history logging.

Usage:
    python3 ide_bridge.py --action status [--json]
    python3 ide_bridge.py --action prompt --content "My Prompt" [--ide "Cursor"] [--json]
    python3 ide_bridge.py --action history [--json]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import shutil
import time
from datetime import datetime
from pathlib import Path
from subprocess import CalledProcessError, check_output, run  # nosec B404

# Add project root to sys.path
import sys

from bootstrap_paths import ensure_project_paths

logger = logging.getLogger(__name__)

project_root = ensure_project_paths(__file__)

from src.config.paths import get_logs_dir, get_ipc_dir  # noqa: E402

# --- Configuration ---
HISTORY_FILE = get_logs_dir() / "ide_history.json"

# Supported IDEs and their process names / app names
IDES = {
    "Cursor": {"process": "Cursor", "app_name": "Cursor"},
    "VSCode": {"process": "Code", "app_name": "Visual Studio Code"},
    "Claude": {"process": "Claude", "app_name": "Claude"},
    "claude_desktop": {"process": "Claude", "app_name": "Claude"},
    "cowork": {"process": "Claude", "app_name": "Claude"},  # Cowork runs inside Claude Desktop
    "Antigravity": {"process": "Antigravity", "app_name": "Antigravity"},
    "Codex": {"process": "Cursor", "app_name": "Cursor"},  # User-specific alias for Cursor
}


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable to absolute path when available."""
    if not command:
        raise ValueError("Command must not be empty")

    executable = command[0]
    if Path(executable).is_absolute():
        return command

    resolved = shutil.which(executable)
    if not resolved:
        return command

    return [resolved, *command[1:]]


def _run_command(command: list[str], **kwargs: object):
    """Run subprocess command with resolved executable path."""
    return run(_resolve_command(command), **kwargs)  # nosec B603


def _check_output_command(command: list[str], **kwargs: object) -> str:
    """Get command output using resolved executable path."""
    return check_output(_resolve_command(command), **kwargs)  # nosec B603


def ensure_data_dir():
    """Ensure data directories exist."""
    get_logs_dir().mkdir(parents=True, exist_ok=True)
    if not HISTORY_FILE.exists():
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def get_running_ides() -> list[str]:
    """Detect which supported IDEs are running."""
    try:
        running = []

        running = []

        if platform.system() == "Darwin":
            # macOS: Use osascript to ask System Events for running applications
            # This avoids "helper" processes and only sees actual Apps
            try:
                cmd = [
                    'osascript',
                    '-e',
                    'tell application "System Events" to get name of (processes where background only is false)',
                ]
                output = _check_output_command(cmd, text=True).strip()
                running_apps = [app.strip() for app in output.split(',')]

                # Check against our map
                for ide_key, info in IDES.items():
                    app_name = info.get("app_name", ide_key)
                    # Check if app_name matches any running app
                    # Loose match: "Visual Studio Code" match "Code"
                    if app_name in running_apps:
                        running.append(ide_key)
                    # Special Case: Antigravity might strictly be "Augur" or similar
                    elif ide_key == "Antigravity" and "Antigravity" in running_apps:
                        running.append(ide_key)

            except Exception as e:
                # Fallback to ps if osascript fails
                logger.warning("osascript IDE detection failed, falling back to ps: %s", e)
                try:
                    output = _check_output_command(["ps", "-ax", "-o", "comm="], text=True, encoding="utf-8")
                except Exception as ps_err:
                    logger.warning("ps fallback also failed: %s", ps_err)
                    output = ""

                for ide_key, info in IDES.items():
                    proc = info["process"].lower()
                    if any(
                        line.lower().strip().endswith(f"/{proc}") or line.lower().strip() == proc
                        for line in output.splitlines()
                    ):
                        running.append(ide_key)

        elif platform.system() == "Windows":
            # Windows: Use tasklist (faster startup than PowerShell)
            try:
                sys.stderr.write("DEBUG: Running tasklist...\n")
                # /FO CSV /NH returns comma-separated values without header
                output = _check_output_command(["tasklist", "/FO", "CSV", "/NH"], text=True, encoding="utf-8")
                sys.stderr.write(f"DEBUG: tasklist finished, {len(output)} bytes\n")
            except CalledProcessError:
                sys.stderr.write("DEBUG: tasklist failed\n")
                output = ""

            for ide_key, info in IDES.items():
                proc = info["process"].lower()

                # tasklist output format: "Image Name","PID","Session Name","Session#","Mem Usage"
                # We just check if the process name is in the line
                if any(f'"{proc}.exe"' in line.lower() or f'"{proc}"' in line.lower() for line in output.splitlines()):
                    running.append(ide_key)
                # Antigravity special case
                elif ide_key == "Antigravity" and any("antigravity" in line.lower() for line in output.splitlines()):
                    running.append(ide_key)

        # Prioritize Antigravity, then Cursor
        ordered = []
        if "Antigravity" in running:
            ordered.append("Antigravity")
        if "Cursor" in running:
            ordered.append("Cursor")

        # Add remaining
        for r in running:
            if r not in ordered:
                ordered.append(r)

        return ordered
    except Exception as e:
        logger.exception("IDE detection failed")
        sys.stderr.write(f"DEBUG: Detetion failed: {e}\n")
        return []


def log_history(prompt: str, ide: str, success: bool, error: str | None = None):
    """Log prompt to history file."""
    ensure_data_dir()
    entry = {"timestamp": datetime.now().isoformat(), "prompt": prompt, "ide": ide, "success": success, "error": error}

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception as e:
        logger.warning("Failed to load IDE history from %s: %s", HISTORY_FILE, e)
        history = []

    history.insert(0, entry)  # Prepend
    history = history[:100]  # Keep last 100

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def get_history():
    """Read history."""
    ensure_data_dir()
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to retrieve IDE history: %s", e)
        return []


def send_prompt(prompt: str, ide_name: str | None = None) -> dict:
    """Send prompt to IDE via Augur Bridge.app wrapper.

    For 'cowork' target: dispatches via file-based dispatch directory.
    For all other targets: uses Augur Bridge.app wrapper.
    """

    # Auto-detect if not specified
    if not ide_name:
        running = get_running_ides()
        if not running:
            return {"success": False, "error": "No supported IDE found running."}
        ide_name = running[0]

    # Cowork uses file-based dispatch, not the Bridge.app
    if ide_name == "cowork":
        if not _has_cowork_feature():
            return {"success": False, "error": "Cowork is not available. Claude Desktop with Cowork feature required."}
        return dispatch_to_cowork(prompt)

    app_name = IDES.get(ide_name, {}).get("app_name", ide_name)

    # Paths
    bridge_script = Path(__file__).parent / "bridge_runner.applescript"

    # App stays in hidden bin, or strictly move to data dir?
    # Let's keep it in .augur/bin for now as it's a "binary", but ensure data flows to runtime dirs
    bin_dir = Path.home() / ".augur" / "bin"
    app_path = bin_dir / "Augur Bridge.app"

    bridge_dir = get_ipc_dir()
    bridge_dir.mkdir(parents=True, exist_ok=True)

    request_file = bridge_dir / "bridge_request.json"
    response_file = bridge_dir / "bridge_response.json"

    # Compile App (Always force recompile to ensure latest logic) - macOS ONLY
    if platform.system() == "Darwin":
        bin_dir.mkdir(parents=True, exist_ok=True)
        try:
            # Read template
            with open(bridge_script, "r", encoding="utf-8") as f:
                script_content = f.read()

            # Inject actual paths
            # We replace the hardcoded "set requestPath..." lines with our dynamic ones
            # Note: We use simple string searching or just prepend the properties if we change the script to use properties
            # But the script uses 'set requestPath to ...'. Let's replace the default paths.

            req_path_str = str(request_file.resolve())
            res_path_str = str(response_file.resolve())

            # Simple replacement of the lines logic
            # We find the lines setting the paths and replace them.
            # Or simpler: We define them at the top.

            # 1. Remove original assignments if they exist (naive replace)
            # The original script has hardcoded paths that we replace with dynamic ones

            # We'll just replace the entire block or lines.
            # To be safe, let's look for the specific lines. BUT the lines rely on 'posixHome'.
            # A robust way is to replace the whole 'on run' preamble or just use regex.

            # Strategy: Replace the hardcoded path lines with absolute paths
            import re

            # Regex to match the set lines.
            # Matches: set requestPath to posixHome & "..."
            script_content = re.sub(
                r'set requestPath to posixHome & "[^"]+"', f'set requestPath to "{req_path_str}"', script_content
            )
            script_content = re.sub(
                r'set responsePath to posixHome & "[^"]+"', f'set responsePath to "{res_path_str}"', script_content
            )

            # Write temp script
            temp_script = bridge_dir / "temp_bridge_runner.applescript"
            with open(temp_script, "w", encoding="utf-8") as f:
                f.write(script_content)

            _run_command(["osacompile", "-o", str(app_path), str(temp_script)], check=True, capture_output=True)

            # Cleanup
            if temp_script.exists():
                temp_script.unlink()

            # Apply Icon if available
            icon_source = project_root / "src/lib" / "assets" / "icon.icns"
            if not icon_source.exists():
                # Fallback to legacy location just in case
                icon_source = Path.home() / ".augur" / "assets" / "icon.icns"

            if icon_source.exists():
                # Destination: Contents/Resources/applet.icns
                dest_icon = app_path / "Contents" / "Resources" / "applet.icns"
                if dest_icon.parent.exists():
                    _run_command(["cp", str(icon_source), str(dest_icon)], check=True)
                    # Touch app to refresh icon cache
                    _run_command(["touch", str(app_path)], check=True)
        except CalledProcessError as e:
            return {"success": False, "error": f"Failed to compile bridge app: {e.stderr.decode(encoding='utf-8')}"}
    elif platform.system() == "Windows":
        # Windows bridge logic (future)
        pass

    # Write Request
    # CHECK LINE LIMIT (BUG-20260110-192625-004)
    # Raised from 20 to 80 — short prompts were being truncated to file references,
    # causing the AppleScript bridge to paste a useless file-path message.
    LINE_LIMIT = 80
    lines = prompt.splitlines()
    if len(lines) > LINE_LIMIT:
        # Offload to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        instruction_file = bridge_dir / f"instruction_{timestamp}.md"

        with open(instruction_file, "w", encoding="utf-8") as f:
            f.write(prompt)

        # Truncate prompt
        truncated_prompt = "\n".join(lines[:LINE_LIMIT])
        truncated_prompt += f"\n\n... (Truncated {len(lines) - LINE_LIMIT} lines)\n"
        truncated_prompt += f"Detailed instructions located at: {instruction_file}\n"
        truncated_prompt += "Please read the file above for full context."

        prompt = truncated_prompt

    request_data = {"prompt": prompt, "app_name": app_name}
    with open(request_file, "w", encoding="utf-8") as f:
        json.dump(request_data, f)

    # Clear previous response
    if response_file.exists():
        response_file.unlink()

    # Run App
    try:
        # We use 'open' to launch the app. It will run the AppleScript handler.
        _run_command(["open", "-a", str(app_path)], check=True)

        # Poll for response (max 20s)
        for _ in range(40):
            if response_file.exists():
                try:
                    with open(response_file, "r", encoding="utf-8") as f:
                        result = json.load(f)
                    log_history(prompt, ide_name, result.get("success", False), result.get("error"))
                    return result
                except Exception as e:
                    logger.debug("Race condition reading bridge response file: %s", e)
                    result = None  # Race condition while response is being written
            time.sleep(0.5)

        return {"success": False, "error": "Timeout waiting for Augur Bridge response."}

    except Exception as e:
        logger.exception("Failed to send prompt to IDE via Augur Bridge")
        log_history(prompt, ide_name, False, str(e))
        return {"success": False, "error": str(e)}


def _has_cowork_feature() -> bool:
    """Check if the Cowork feature is available in Claude Desktop config.

    Cowork is distinguished from plain Claude Desktop by checking for
    the 'cowork' or 'agent' feature flag in Claude's config.json.
    Falls back to True if Claude Desktop is installed (Cowork bundled since Jan 2026).
    """
    home = Path.home()
    if platform.system() == "Darwin":
        config_path = home / "Library" / "Application Support" / "Claude" / "config.json"
    elif platform.system() == "Windows":
        config_path = Path(os.environ.get("APPDATA", "")) / "Claude" / "config.json"
    else:
        config_path = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "Claude" / "config.json"

    if not config_path.exists():
        # If config.json doesn't exist, check if Claude Desktop is installed at all
        if platform.system() == "Darwin":
            return Path("/Applications/Claude.app").exists()
        elif platform.system() == "Windows":
            claude_exe = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Claude" / "Claude.exe"
            return claude_exe.exists()
        return False

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        features = config.get("features", {})
        if isinstance(features, dict):
            if features.get("cowork") or features.get("agentic") or features.get("agent"):
                return True
        if config.get("cowork_enabled") or config.get("agenticMode"):
            return True
        # Bundled since Jan 2026 — assume available unless explicitly disabled
        return not config.get("cowork_disabled", False)
    except Exception:
        return False


def _get_cowork_dispatch_dir() -> Path:
    """Get the state/cowork-dispatch directory."""
    try:
        from src.config.paths import get_runtime_dir  # type: ignore[import]
        return get_runtime_dir() / "cowork-dispatch"
    except ImportError:
        runtime_dir = os.environ.get("AUGUR_STATE") or os.environ.get("AUGUR_RUNTIME")
        if runtime_dir:
            return Path(runtime_dir) / "cowork-dispatch"
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "Augur" / "state" / "cowork-dispatch"
        return Path.home() / ".local" / "state" / "augur" / "cowork-dispatch"


def dispatch_to_cowork(prompt: str, task_id: str | None = None) -> dict:
    """Write a prompt task file to the Cowork dispatch directory.

    Cowork monitors state/cowork-dispatch/ for pending task files.

    Args:
        prompt: The task prompt to dispatch
        task_id: Optional task identifier (auto-generated if None)

    Returns:
        dict with success, task_id, task_file, error
    """

    if task_id is None:
        task_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    dispatch_dir = _get_cowork_dispatch_dir()
    try:
        dispatch_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"success": False, "task_id": task_id, "task_file": None, "error": f"Cannot create dispatch dir: {e}"}

    task_file = dispatch_dir / f"task_{task_id}.json"
    task_data = {
        "task_id": task_id,
        "created_at": datetime.now().isoformat(),
        "status": "pending",
        "prompt": prompt,
    }

    try:
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump(task_data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        log_history(prompt, "cowork", True)
        return {"success": True, "task_id": task_id, "task_file": str(task_file), "error": None}
    except Exception as e:
        log_history(prompt, "cowork", False, str(e))
        return {"success": False, "task_id": task_id, "task_file": str(task_file), "error": f"Failed to write task file: {e}"}


def _emit_post_exec_event(command: str, outcome: str, duration_ms: int = 0) -> None:
    """Append a post-execution event to the adaptive loop queue."""
    try:
        from src.config.paths import get_runtime_dir
        queue_file = get_runtime_dir() / "adaptive" / "post_exec_queue.jsonl"
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "command": command,
            "outcome": outcome,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat(),
        }
        with open(queue_file, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass  # Best-effort, don't break command execution


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True, choices=["status", "prompt", "history"])
    parser.add_argument("--content", help="Prompt content")
    parser.add_argument("--ide", help="Target IDE (optional)")
    parser.add_argument("--json", action="store_true")

    args = parser.parse_args()

    result = {}

    if args.action == "status":
        running = get_running_ides()
        # Add cowork to available IDEs if Claude Desktop is running and has Cowork feature
        if "Claude" in running or "claude_desktop" in running:
            if _has_cowork_feature() and "cowork" not in running:
                running.append("cowork")
        result = {"success": True, "active_ide": running[0] if running else None, "available_ides": running}

    elif args.action == "history":
        history = get_history()
        result = {"success": True, "history": history}

    elif args.action == "prompt":
        if not args.content:
            result = {"success": False, "error": "Missing --content"}
        else:
            t0 = time.monotonic()
            result = send_prompt(args.content, args.ide)
            duration_ms = int((time.monotonic() - t0) * 1000)
            # Extract slash command name from prompt if present
            command_name = "ide-prompt"
            content_stripped = args.content.strip()
            if content_stripped.startswith("/"):
                first_word = content_stripped.split()[0] if content_stripped.split() else ""
                if first_word.startswith("/") and len(first_word) > 1:
                    command_name = first_word.lstrip("/")
            _emit_post_exec_event(
                command_name,
                "success" if result.get("success") else "failure",
                duration_ms,
            )

    if args.json:
        sys.stdout.write(f"{json.dumps(result)}\n")
    else:
        sys.stdout.write(f"{result}\n")


if __name__ == "__main__":
    main()

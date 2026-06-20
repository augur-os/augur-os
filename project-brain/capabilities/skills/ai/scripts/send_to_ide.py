#!/usr/bin/env python3
"""
Send prompt to IDE chat (Cursor/VS Code) via AppleScript.

Usage:
    python3 send_to_ide.py --prompt "Your prompt here"
    python3 send_to_ide.py --prompt "Your prompt" --app Cursor
    python3 send_to_ide.py --prompt "Your prompt" --json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from subprocess import CompletedProcess, TimeoutExpired, run  # nosec B404


def _resolve_command(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise RuntimeError(f"Required executable not found in PATH: {name}")
    return resolved


def send_to_ide(prompt: str, app: str = "Cursor") -> dict:
    """
    Send prompt to IDE chat via AppleScript.
    Only pastes the prompt - user controls when to run.
    """
    # Escape quotes for AppleScript
    escaped_prompt = prompt.replace('\\', '\\\\').replace('"', '\\"')

    applescript = f'''
    -- Copy prompt to clipboard
    set the clipboard to "{escaped_prompt}"
    
    -- Activate the IDE
    tell application "{app}" to activate
    delay 0.3
    
    -- Open chat panel (Cmd+L for Cursor, Cmd+Shift+I for VS Code)
    tell application "System Events"
        tell process "{app}"
            keystroke "l" using {{command down}}
            delay 0.3
            -- Paste the prompt
            keystroke "v" using {{command down}}
        end tell
    end tell
    '''

    try:
        result: CompletedProcess[str] = run(
            [_resolve_command("osascript"), "-e", applescript],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )  # nosec B603

        if result.returncode == 0:
            return {"success": True, "message": f"Prompt pasted to {app} chat. Review and click run.", "app": app}
        else:
            return {
                "success": False,
                "error": result.stderr or "AppleScript execution failed",
                "hint": "Make sure to grant accessibility permissions to Terminal/Python",
            }
    except TimeoutExpired:
        return {"success": False, "error": "Timeout waiting for IDE", "hint": f"Make sure {app} is running"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Send prompt to IDE chat")
    parser.add_argument("--prompt", required=True, help="Prompt to send")
    parser.add_argument("--app", default="Cursor", help="IDE application name (default: Cursor)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    result = send_to_ide(args.prompt, args.app)

    if args.json:
        sys.stdout.write(f"{json.dumps(result)}\n")
    else:
        if result["success"]:
            sys.stdout.write(f"✅ {result['message']}\n")
        else:
            sys.stdout.write(f"❌ {result['error']}\n")
            if "hint" in result:
                sys.stdout.write(f"   💡 {result['hint']}\n")
            sys.exit(1)


if __name__ == "__main__":
    main()

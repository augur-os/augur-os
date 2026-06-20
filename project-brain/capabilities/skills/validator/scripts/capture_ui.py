#!/usr/bin/env python3
"""Capture a full-page UI screenshot via the shared dashboard engine.

Thin wrapper over apps/dashboard/scripts/skill-scripts/capture_ui.py.
Screenshots and metadata land under get_logs_dir()/browser-verification/ —
never the repo tree (repo .gitignore blanket-hides binaries; see CLAUDE.md
rule 4).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bootstrap_paths import ensure_project_paths

PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_logs_dir, get_project_root, get_python_executable  # noqa: E402


def _resolve_engine_python(explicit: str | None) -> str:
    """Interpreter for the Playwright engine.

    The project venv does not ship playwright; allow pointing at one that has
    it via --python or AUGUR_PLAYWRIGHT_PYTHON.
    """
    if explicit:
        return explicit
    env_override = os.environ.get("AUGUR_PLAYWRIGHT_PYTHON")
    if env_override:
        return env_override
    return str(get_python_executable())


def _run_frontend_capture(url: str, output_path: Path, engine_python: str) -> subprocess.CompletedProcess[str]:
    root = get_project_root()
    script_path = root / "apps/dashboard/scripts/skill-scripts/capture_ui.py"
    cmd = [engine_python, str(script_path), "--url", url, "--output", str(output_path)]
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{root}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(root)
    return subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, env=env)  # nosec B603


def _parse_json_output(stdout: str) -> dict[str, Any]:
    raw = stdout.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"result": parsed}
    except json.JSONDecodeError:
        marker = raw.find("{")
        if marker >= 0:
            try:
                parsed = json.loads(raw[marker:])
                return parsed if isinstance(parsed, dict) else {"result": parsed}
            except json.JSONDecodeError:
                pass
        return {"raw_output": raw}


def _default_output_path() -> Path:
    captures = get_logs_dir() / "browser-verification" / "validator"
    captures.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return captures / f"capture_{timestamp}.png"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validator UI capture wrapper")
    parser.add_argument("--url", required=True, help="Target URL")
    parser.add_argument("--output", help="Optional output path for screenshot")
    parser.add_argument(
        "--python",
        help="Interpreter with playwright installed (default: project python, "
        "or AUGUR_PLAYWRIGHT_PYTHON)",
    )
    args = parser.parse_args()

    output_path = Path(args.output).expanduser().resolve() if args.output else _default_output_path().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = _run_frontend_capture(args.url, output_path, _resolve_engine_python(args.python))
    parsed = _parse_json_output(result.stdout)
    parser_status = str(parsed.get("status", "")).lower() if isinstance(parsed, dict) else ""
    parser_error = bool(parsed.get("error")) if isinstance(parsed, dict) else False
    success = result.returncode == 0 and parser_status != "error" and not parser_error
    normalized_returncode = result.returncode if result.returncode != 0 else (0 if success else 1)

    response: dict[str, Any] = {
        "success": success,
        "returncode": normalized_returncode,
        "url": args.url,
        "output_path": str(output_path),
        "result": parsed,
    }
    stderr = result.stderr.strip()
    if stderr:
        response["stderr"] = stderr

    metadata_path = output_path.with_suffix(".json")
    metadata_path.write_text(json.dumps(response, indent=2), encoding="utf-8")
    response["metadata_path"] = str(metadata_path)

    sys.stdout.write(json.dumps(response, indent=2))
    sys.stdout.write("\n")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

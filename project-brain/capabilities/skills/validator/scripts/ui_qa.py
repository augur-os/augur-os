#!/usr/bin/env python3
"""Run UI QA via the shared dashboard engine and archive results in runtime state.

Thin wrapper over apps/dashboard/scripts/skill-scripts/ui_qa.py for one-off,
URL-targeted QA passes (hydration / alignment / interactivity). Results are
archived under get_runtime_dir()/validator/ — never the repo tree.
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
SKILL_ROOT = Path(__file__).resolve().parents[1]

from src.config.paths import get_project_root, get_python_executable, get_runtime_dir  # noqa: E402


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


def _run_frontend_ui_qa(forward_args: list[str], engine_python: str) -> subprocess.CompletedProcess[str]:
    root = get_project_root()
    script_path = root / "apps/dashboard/scripts/skill-scripts/ui_qa.py"
    cmd = [engine_python, str(script_path), *forward_args, "--json"]
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
        # Frontend tool can print non-JSON logs before payload in some environments.
        marker = raw.rfind("{")
        if marker >= 0:
            try:
                parsed = json.loads(raw[marker:])
                return parsed if isinstance(parsed, dict) else {"result": parsed}
            except json.JSONDecodeError:
                pass
    return {"raw_output": raw}


def _archive_result(payload: dict[str, Any]) -> Path:
    run_dir = get_runtime_dir() / "validator" / "ui_qa_runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_file = run_dir / f"ui_qa_{timestamp}.json"
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Validator UI QA wrapper")
    parser.add_argument("--url", default="http://localhost:3000/browse", help="Target URL")
    parser.add_argument(
        "--action",
        choices=["hydration", "alignment", "interactivity", "full"],
        default="full",
        help="QA action",
    )
    parser.add_argument("--selector", help="Custom selector for interactivity test")
    parser.add_argument("--config", help="Optional YAML config path")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser headless")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="Show browser window")
    parser.add_argument(
        "--python",
        help="Interpreter with playwright installed (default: project python, "
        "or AUGUR_PLAYWRIGHT_PYTHON)",
    )
    args = parser.parse_args()

    forward_args = ["--url", args.url, "--action", args.action]
    if args.selector:
        forward_args.extend(["--selector", args.selector])
    config_path = args.config
    if not config_path:
        default_config = SKILL_ROOT / "augur" / "config" / "ui-qa-validator.yaml"
        if default_config.exists():
            config_path = str(default_config)
    if config_path:
        forward_args.extend(["--config", config_path])
    if args.headless:
        forward_args.append("--headless")
    else:
        forward_args.append("--no-headless")

    result = _run_frontend_ui_qa(forward_args, _resolve_engine_python(args.python))
    parsed = _parse_json_output(result.stdout)
    overall_status = str(parsed.get("overall_status", "")).upper() if isinstance(parsed, dict) else ""
    tool_error = parsed.get("error") if isinstance(parsed, dict) else None
    success = result.returncode == 0 and overall_status not in {"FAILED", "ERROR"} and not tool_error
    payload: dict[str, Any] = {
        "success": success,
        "returncode": result.returncode if result.returncode != 0 else (0 if success else 1),
        "url": args.url,
        "action": args.action,
        "result": parsed,
    }
    stderr = result.stderr.strip()
    if stderr:
        payload["stderr"] = stderr

    archive_path = _archive_result(payload)
    response = {
        "success": payload["success"],
        "returncode": payload["returncode"],
        "url": args.url,
        "action": args.action,
        "config": config_path,
        "archive_path": str(archive_path),
        "result": parsed,
    }
    if stderr:
        response["stderr"] = stderr

    sys.stdout.write(json.dumps(response, indent=2))
    sys.stdout.write("\n")
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

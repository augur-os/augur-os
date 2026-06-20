#!/usr/bin/env python3
"""
Fix Audit Issues
Auto-fixes pattern compliance issues found by the audit.

This script wraps auto_fix_pattern_issues.py and provides a skill action interface.
"""

import json
import sys
from subprocess import TimeoutExpired, run as subprocess_run  # nosec B404
from pathlib import Path
from typing import Dict, Any


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def main(params: Dict[str, Any] = None) -> str:
    """
    Main entry point for skill action.

    Args:
        params: Dictionary with optional parameters:
            - limit: Maximum number of pages to fix (default: 5)
            - fixes: List of fixes to apply (default: ["gradient", "spacing", "focus", "cards"])
            - audit_report: Path to specific audit report (optional)
            - page: Specific page to fix (optional)
            - dry_run: If True, preview changes without applying (default: False)

    Returns:
        JSON string with results
    """
    if params is None:
        params = {}

    # Get script directory
    script_dir = Path(__file__).parent
    auto_fix_script = script_dir / "auto_fix_pattern_issues.py"

    if not auto_fix_script.exists():
        return json.dumps(
            {"status": "error", "message": "Auto-fix script not found", "expected_path": str(auto_fix_script)}, indent=2
        )

    # Build command
    cmd = [sys.executable, str(auto_fix_script)]

    # Add parameters
    limit = params.get("limit", 5)
    cmd.extend(["--limit", str(limit)])

    fixes = params.get("fixes", ["gradient", "spacing", "focus", "cards"])
    if isinstance(fixes, list):
        cmd.extend(["--fixes"] + fixes)
    elif isinstance(fixes, str):
        cmd.extend(["--fixes", fixes])

    if params.get("dry_run", False):
        cmd.append("--dry-run")

    if params.get("audit_report"):
        cmd.extend(["--audit-report", str(params["audit_report"])])
    elif params.get("page"):
        cmd.extend(["--page", str(params["page"])])

    # Resolve project root
    try:
        from src.config.paths import get_project_root
        project_root = get_project_root()
    except ImportError:
        project_root = script_dir.parent.parent.parent.parent  # fallback

    # Run auto-fix script
    try:
        result = subprocess_run(  # nosec B603
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd=project_root,
        )

        # Parse output for summary
        output_lines = result.stdout.split('\n')
        summary = {
            "status": "success" if result.returncode == 0 else "error",
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": " ".join(cmd),
        }

        # Extract key metrics from output
        for line in output_lines:
            if "Fixed:" in line or "Items created:" in line:
                summary["summary"] = line.strip()
            elif "Summary:" in line or "📊 Summary:" in line:
                # Get next few lines for summary
                idx = output_lines.index(line)
                summary["summary_lines"] = output_lines[idx : idx + 5]

        return json.dumps(summary, indent=2)

    except TimeoutExpired:
        return json.dumps(
            {"status": "error", "message": "Auto-fix script timed out (exceeded 10 minutes)", "command": " ".join(cmd)},
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "message": f"Failed to run auto-fix script: {str(e)}",
                "command": " ".join(cmd),
                "error": str(e),
            },
            indent=2,
        )


if __name__ == "__main__":
    # CLI mode - parse arguments
    import argparse

    parser = argparse.ArgumentParser(description="Fix audit issues (skill action wrapper)")
    parser.add_argument("--limit", type=int, default=5, help="Maximum pages to fix")
    parser.add_argument(
        "--fixes", nargs="+", default=["gradient", "spacing", "focus", "cards"], help="Which fixes to apply"
    )
    parser.add_argument("--audit-report", help="Path to audit report")
    parser.add_argument("--page", help="Specific page to fix")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes")

    args = parser.parse_args()

    params = {"limit": args.limit, "fixes": args.fixes, "dry_run": args.dry_run}

    if args.audit_report:
        params["audit_report"] = args.audit_report
    if args.page:
        params["page"] = args.page

    result = main(params)
    _out(result)

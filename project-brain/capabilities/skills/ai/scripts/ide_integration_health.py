#!/usr/bin/env python3
"""
IDE Integration Health - AI Bridge script for auditing and fixing IDE integrations.

Provides actions for:
- audit_ide_integrations: Run health checks for all IDEs
- fix_ide_integration: Auto-fix configuration for a specific IDE
- create_backlog_on_failure: Create backlog items when critical checks fail

Usage:
    python3 ide_integration_health.py --action audit
    python3 ide_integration_health.py --action fix --ide cursor
    python3 ide_integration_health.py --action create_backlog --ide cursor
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Add project root to path
from bootstrap_paths import ensure_project_paths  # noqa: E402

project_root = ensure_project_paths(__file__)

from src.lib.ai.ide_integrations import (  # noqa: E402
    update_ide_config,
    update_ide_health,
)
from skills.ai.augur.adapters.registry import get_registry  # noqa: E402
from src.lib.ai.ide_health import check_all_ides  # noqa: E402


def audit_integrations() -> dict[str, Any]:
    """
    Run health checks for all IDE integrations.

    Returns:
        dict with audit results
    """
    get_registry()
    results = check_all_ides()

    summary = {
        "total": len(results),
        "healthy": sum(1 for r in results.values() if r.get("healthy", False)),
        "degraded": sum(1 for r in results.values() if r.get("status") == "degraded"),
        "not_configured": sum(1 for r in results.values() if r.get("status") == "not_configured"),
        "errors": sum(1 for r in results.values() if r.get("status") == "error"),
        "details": results,
    }

    return summary


def fix_integration(ide_name: str) -> dict[str, Any]:
    """
    Auto-fix configuration for a specific IDE.

    Args:
        ide_name: Name of the IDE to fix

    Returns:
        dict with fix results
    """
    registry = get_registry()
    adapter = registry.get(ide_name)

    if not adapter:
        return {
            "success": False,
            "error": f"Adapter for '{ide_name}' not found",
        }

    try:
        result = adapter.ensure_config()

        if result.get("success"):
            # Update config store
            update_ide_config(
                ide_name,
                config_paths=result.get("config_paths", []),
            )

            # Run health check after fix
            health = adapter.health_check()
            update_ide_health(ide_name, health)

            return {
                "success": True,
                "changed": result.get("changed", False),
                "config_paths": result.get("config_paths", []),
                "backup_paths": result.get("backup_paths", []),
                "summary": result.get("summary", ""),
                "health_after": health,
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def create_backlog_on_failure(ide_name: str, threshold: str = "critical") -> dict[str, Any]:
    """
    Create backlog items when IDE integration checks fail.

    Args:
        ide_name: Name of the IDE
        threshold: "critical" (end_to_end fails) or "any" (any check fails)

    Returns:
        dict with backlog creation results
    """
    registry = get_registry()
    adapter = registry.get(ide_name)

    if not adapter:
        return {
            "success": False,
            "error": f"Adapter for '{ide_name}' not found",
        }

    # Run health check
    health = adapter.health_check()
    update_ide_health(ide_name, health)

    if health.get("healthy", False):
        return {
            "success": True,
            "backlog_created": False,
            "message": f"{ide_name} is healthy, no backlog item needed",
        }

    checks = health.get("checks", {})
    failed_checks = []

    if threshold == "critical":
        # Only create backlog if end_to_end fails
        if checks.get("end_to_end") and not checks["end_to_end"][0]:
            failed_checks.append(("end_to_end", checks["end_to_end"][1]))
    else:
        # Create backlog for any failed check
        for check_name, (passed, message) in checks.items():
            if passed is False:
                failed_checks.append((check_name, message))

    if not failed_checks:
        return {
            "success": True,
            "backlog_created": False,
            "message": f"No critical failures for {ide_name}",
        }

    # Create backlog task
    try:
        from src.config.paths import get_runtime_dir

        backlog_dir = get_runtime_dir() / "agent-tasks" / "backlog"
        backlog_dir.mkdir(parents=True, exist_ok=True)

        task_id = f"ide-integration-{ide_name}-{datetime.now().strftime('%Y%m%d')}"
        task_file = backlog_dir / f"{task_id}.md"

        failed_summary = "\n".join(f"- **{name}**: {msg}" for name, msg in failed_checks)

        task_content = f"""---
id: {task_id}
type: bugfix
priority: p1-high
status: ready
skill: ai
workspace: ~/Projects/augur
created: {datetime.now().isoformat()}
source: ai-automated
---

# Fix IDE Integration: {ide_name}

## Objective

Fix failing health checks for {ide_name} IDE integration.

## Failed Checks

{failed_summary}

## Health Status

- **Overall**: {health.get('status', 'unknown')}
- **Last Check**: {health.get('last_check', 'never')}
- **Error**: {health.get('error', 'None')}

## Acceptance Criteria

- [ ] All health checks pass for {ide_name}
- [ ] Configuration files are properly set up
- [ ] End-to-end test passes
- [ ] Integration status shows as "healthy" in dashboard

## Auto-Generated

This task was automatically created by AI Bridge when health checks failed.
"""

        task_file.write_text(task_content, encoding="utf-8")

        return {
            "success": True,
            "backlog_created": True,
            "task_id": task_id,
            "task_file": str(task_file),
            "failed_checks": failed_checks,
        }
    except Exception as e:
        return {
            "success": False,
            "backlog_created": False,
            "error": f"Failed to create backlog task: {e}",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="IDE Integration Health Management")
    parser.add_argument("--action", required=True, choices=["audit", "fix", "create_backlog"])
    parser.add_argument("--ide", help="IDE name (required for fix/create_backlog)")
    parser.add_argument(
        "--threshold", default="critical", choices=["critical", "any"], help="Threshold for backlog creation"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.action in ["fix", "create_backlog"] and not args.ide:
        parser.error(f"--ide is required for action '{args.action}'")

    try:
        if args.action == "audit":
            result = audit_integrations()
        elif args.action == "fix":
            result = fix_integration(args.ide)
        elif args.action == "create_backlog":
            result = create_backlog_on_failure(args.ide, args.threshold)
        else:
            result = {"error": "Unknown action"}

        if args.json:
            _out(json.dumps(result, indent=2))
        else:
            if args.action == "audit":
                _out("IDE Integration Audit")
                _out(f"Total: {result['total']}")
                _out(f"Healthy: {result['healthy']}")
                _out(f"Degraded: {result['degraded']}")
                _out(f"Not Configured: {result['not_configured']}")
                _out(f"Errors: {result['errors']}")
            else:
                if result.get("success"):
                    _out(f"✅ Success: {result.get('message', 'Operation completed')}")
                    if result.get("backlog_created"):
                        _out(f"📋 Created backlog task: {result.get('task_id')}")
                else:
                    _out(f"❌ Failed: {result.get('error', 'Unknown error')}")
                    return 1

        return 0
    except Exception as e:
        if args.json:
            _out(json.dumps({"error": str(e)}, indent=2))
        else:
            _out(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

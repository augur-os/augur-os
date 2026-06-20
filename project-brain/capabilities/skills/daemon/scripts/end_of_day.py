#!/usr/bin/env python3
"""
End of Day Trigger - Collects daily context for Night Shift

Supports manual trigger ("Goodnight Augur") and time-based trigger.
Aggregates implicit feedback (errors, logs) and explicit requests (inbox).
Generates nightly_context.json for factory agents.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

try:
    from src.logging import get_entity_logger
except ImportError:
    import logging

    def get_entity_logger(name: str):
        return logging.getLogger(name)


logger = get_entity_logger("end_of_day")

try:
    import yaml
except ImportError:
    yaml = None

try:
    from src.config.paths import get_project_root
except ImportError:

    def _get_project_root() -> Path:
        env = os.environ.get("AUGUR_ROOT")
        if env:
            return Path(env).expanduser().resolve()
        return get_project_root()


def _get_data_dir() -> Path:
    """Get augur data directory."""
    return get_project_root()


def _collect_implicit_feedback(data_dir: Path) -> dict[str, Any]:
    """Collect implicit feedback: errors, retry loops, etc."""
    feedback = {
        "errors": [],
        "warnings": [],
        "retry_loops": [],
        "performance_issues": [],
    }

    # Check for error logs
    log_dirs = [
        data_dir / "agent-tasks" / "logs",
        data_dir / "factory" / "logs",
    ]

    for log_dir in log_dirs:
        if log_dir.exists():
            for log_file in log_dir.glob("**/*.log"):
                try:
                    content = log_file.read_text(encoding="utf-8")
                    # Simple error detection (can be enhanced)
                    if "ERROR" in content or "Exception" in content:
                        feedback["errors"].append(
                            {
                                "file": str(log_file),
                                "count": content.count("ERROR") + content.count("Exception"),
                            }
                        )
                except Exception as exc:
                    logger.debug("Skipping unreadable log file %s: %s", log_file, exc)

    return feedback


def _collect_explicit_requests(data_dir: Path) -> dict[str, Any]:
    """Collect explicit requests from inbox."""
    requests = {
        "inbox_items": [],
        "pending_tasks": [],
    }

    # Check inbox files
    inbox_paths = [
        data_dir / "factory" / "executor" / "inbox.md",
        data_dir / "inbox.md",
    ]

    for inbox_path in inbox_paths:
        if inbox_path.exists():
            try:
                content = inbox_path.read_text(encoding="utf-8")
                # Extract items (simple line-based, can be enhanced)
                lines = [line.strip() for line in content.split("\n") if line.strip() and not line.startswith("#")]
                requests["inbox_items"].extend(lines)
            except Exception as exc:
                logger.debug("Skipping unreadable inbox file %s: %s", inbox_path, exc)

    # Check for pending tasks in backlog
    backlog_dir = data_dir / "factory" / "executor" / "backlog"
    if backlog_dir.exists():
        for task_file in backlog_dir.glob("**/*.md"):
            if task_file.name == "EPIC.md":
                continue
            try:
                content = task_file.read_text(encoding="utf-8")
                if "---" in content:
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1]) or {}
                        status = frontmatter.get("status", "").lower()
                        if status in ["ready", "draft"]:
                            requests["pending_tasks"].append(
                                {
                                    "id": frontmatter.get("id", task_file.stem),
                                    "type": frontmatter.get("type", "unknown"),
                                    "priority": frontmatter.get("priority", "unknown"),
                                    "status": status,
                                }
                            )
            except Exception as exc:
                logger.debug("Skipping unreadable task file %s: %s", task_file, exc)

    return requests


def _generate_nightly_context(data_dir: Path, trigger_type: str = "manual") -> dict[str, Any]:
    """Generate nightly context JSON for factory agents."""
    implicit_feedback = _collect_implicit_feedback(data_dir)
    explicit_requests = _collect_explicit_requests(data_dir)

    context = {
        "triggered_at": datetime.now().isoformat(),
        "trigger_type": trigger_type,  # "manual" or "time-based"
        "day": datetime.now().strftime("%Y-%m-%d"),
        "implicit_feedback": implicit_feedback,
        "explicit_requests": explicit_requests,
        "summary": {
            "error_count": len(implicit_feedback["errors"]),
            "inbox_items_count": len(explicit_requests["inbox_items"]),
            "pending_tasks_count": len(explicit_requests["pending_tasks"]),
        },
    }

    return context


def _save_nightly_context(context: dict[str, Any], data_dir: Path) -> Path:
    """Save nightly context to JSON file."""
    output_dir = data_dir / "factory" / "nightly"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_file = output_dir / f"nightly_context_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(context, f, indent=2)

    # Also create/update latest symlink
    latest_file = output_dir / "nightly_context.json"
    if latest_file.exists():
        latest_file.unlink()
    latest_file.symlink_to(output_file.name)

    return output_file


def goodnight_augur(trigger_type: str = "manual") -> dict[str, Any]:
    """
    Main function: Trigger end of day aggregation.

    Args:
        trigger_type: "manual" or "time-based"

    Returns:
        Dictionary with context and output file path
    """
    data_dir = _get_data_dir()

    _out("🌙 Goodnight Augur - Aggregating daily context...")

    # Generate context
    context = _generate_nightly_context(data_dir, trigger_type)

    # Save to file
    output_file = _save_nightly_context(context, data_dir)

    _out(f"✅ Nightly context generated: {output_file}")
    _out(f"   - Errors: {context['summary']['error_count']}")
    _out(f"   - Inbox items: {context['summary']['inbox_items_count']}")
    _out(f"   - Pending tasks: {context['summary']['pending_tasks_count']}")

    return {
        "status": "success",
        "context": context,
        "output_file": str(output_file),
    }


def main(params: dict | None = None) -> dict[str, Any]:
    """
    MCP tool entry point.

    Args:
        params: Optional dict with:
            - trigger: "manual" or "time-based" (default: "manual")
            - output: Optional output file path

    Returns:
        Result dictionary with status, context, and output_file
    """
    params = params or {}
    trigger_type = params.get("trigger", "manual")
    output_path = params.get("output")

    result = goodnight_augur(trigger_type=trigger_type)

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        result["custom_output_file"] = str(output_file)

    return result


if __name__ == "__main__":
    # CLI support
    parser = argparse.ArgumentParser(description="End of Day Trigger - Aggregate daily context")
    parser.add_argument("--trigger", choices=["manual", "time-based"], default="manual")
    parser.add_argument("--output", type=str, help="Output file path")
    args = parser.parse_args()

    result = main({"trigger": args.trigger, "output": args.output})
    _out(json.dumps(result, indent=2))
    sys.exit(0)

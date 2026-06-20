#!/usr/bin/env python3
"""
Morning Briefing Generator for Augur.

Generates a daily summary of overnight autonomous execution:
- Tasks completed and failed
- PRs created (with links)
- Backlog status
- Today's top priorities

Designed to run at 7 AM via launchd or on-demand.

Usage:
    python morning_briefing.py                # Generate today's briefing
    python morning_briefing.py --date 2026-02-04  # Specific date
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from subprocess import CompletedProcess, run  # nosec B404
from typing import Any

logger = logging.getLogger(__name__)


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from src.config.paths import get_logs_dir, get_runtime_dir  # noqa: E402
from task_utils import all_backlog_dirs, read_task  # noqa: E402

BRIEFING_DIR = get_runtime_dir() / "briefings"
HEADLESS_LOG_DIR = get_logs_dir() / "headless"
CONTINUOUS_LOG_DIR = get_logs_dir() / "continuous"
NIGHTLY_LOG_DIR = get_logs_dir() / "nightly"


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve command executable to an absolute path when available."""
    if not command:
        return command
    resolved = shutil.which(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return command


def _run_command(command: list[str], **kwargs: Any) -> CompletedProcess[Any]:
    """Run a subprocess command with a resolved executable path."""
    return run(_resolve_command(command), **kwargs)  # nosec B603


def collect_execution_logs(date_str: str) -> list[dict[str, Any]]:
    """Collect all headless runner logs for the given date."""
    logs: list[dict[str, Any]] = []

    for log_dir in [HEADLESS_LOG_DIR, CONTINUOUS_LOG_DIR, NIGHTLY_LOG_DIR]:
        if not log_dir.exists():
            continue
        for log_file in log_dir.glob(f"*{date_str}*"):
            if not log_file.name.endswith(".json"):
                continue
            try:
                data = json.loads(log_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    # Single run log
                    logs.append(data)
                elif isinstance(data, list):
                    logs.extend(data)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                logger.debug("Failed to parse execution log %s: %s", log_file, exc)

    # Also check for run logs with timestamps matching the date
    if HEADLESS_LOG_DIR.exists():
        for log_file in HEADLESS_LOG_DIR.glob("run-*.json"):
            try:
                data = json.loads(log_file.read_text(encoding="utf-8"))
                started = data.get("started_at", "")
                if date_str in started:
                    if data not in logs:
                        logs.append(data)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
                logger.debug("Failed to parse timestamped run log %s: %s", log_file, exc)

    return logs


def get_open_prs() -> list[dict[str, str]]:
    """Get open draft PRs created by autonomous execution."""
    try:
        result = _run_command(
            ["gh", "pr", "list", "--state=open", "--draft", "--json=title,url,createdAt,headRefName"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            prs = json.loads(result.stdout)
            # Filter to auto/ branches
            return [pr for pr in prs if pr.get("headRefName", "").startswith("auto/")]
        return []
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        logger.debug("Failed to query open PRs: %s", exc)
        return []


def count_backlog_status() -> dict[str, int]:
    """Count backlog tasks by status."""
    counts: dict[str, int] = {"ready": 0, "in_progress": 0, "completed": 0, "total": 0}

    for bdir in all_backlog_dirs():
        for path in bdir.rglob("*.md"):
            if path.name in ("EPIC.md", "README.md"):
                continue
            try:
                frontmatter, _ = read_task(path)
                status = str(frontmatter.get("status", "")).lower().strip()
                counts["total"] += 1
                if status == "ready":
                    counts["ready"] += 1
                elif status in ("in-progress", "in_progress", "claimed"):
                    counts["in_progress"] += 1
                elif status in ("completed", "done"):
                    counts["completed"] += 1
            except (OSError, UnicodeDecodeError, ValueError, TypeError) as exc:
                logger.debug("Failed to parse backlog task %s: %s", path, exc)

    return counts


def generate_briefing(date_str: str) -> str:
    """Generate the morning briefing markdown."""
    logs = collect_execution_logs(date_str)
    prs = get_open_prs()
    backlog = count_backlog_status()

    succeeded = [log for log in logs if log.get("success")]
    failed = [log for log in logs if not log.get("success")]

    lines = [
        f"# Morning Briefing — {date_str}",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
        "## Overnight Summary",
        "",
        f"- **Tasks executed**: {len(logs)}",
        f"- **Succeeded**: {len(succeeded)}",
        f"- **Failed**: {len(failed)}",
        "",
    ]

    # Completed tasks
    if succeeded:
        lines.append("### Completed Tasks")
        lines.append("")
        for log in succeeded:
            title = log.get("task_title", log.get("task_id", "unknown"))
            pr_url = log.get("pr_url", "")
            duration = log.get("duration_seconds", 0)
            files = log.get("files_changed", 0)
            pr_link = f" — [PR]({pr_url})" if pr_url else ""
            lines.append(f"- **{title}**{pr_link} ({files} files, {duration:.0f}s)")
        lines.append("")

    # Failed tasks
    if failed:
        lines.append("### Failed Tasks")
        lines.append("")
        for log in failed:
            title = log.get("task_title", log.get("task_id", "unknown"))
            error = log.get("error", "unknown error")
            lines.append(f"- **{title}**: {error}")
        lines.append("")

    # Open PRs
    if prs:
        lines.append("## Open Auto PRs (Awaiting Review)")
        lines.append("")
        for pr in prs:
            title = pr.get("title", "")
            url = pr.get("url", "")
            created = pr.get("createdAt", "")[:10]
            lines.append(f"- [{title}]({url}) (created {created})")
        lines.append("")

    # Backlog status
    lines.extend(
        [
            "## Backlog Status",
            "",
            f"- **Ready**: {backlog['ready']}",
            f"- **In Progress**: {backlog['in_progress']}",
            f"- **Total**: {backlog['total']}",
            "",
        ]
    )

    # No activity warning
    if not logs and not prs:
        lines.extend(
            [
                "---",
                "",
                "> No autonomous activity overnight. Check that the nightly executor and",
                "> continuous executor services are running: `launchctl list | grep augur`",
                "",
            ]
        )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Morning briefing generator")
    parser.add_argument("--date", type=str, default="", help="Date to generate briefing for (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.date:
        date_str = args.date
    else:
        # Default: yesterday (briefing covers overnight work)
        date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    briefing = generate_briefing(date_str)

    # Write to file
    BRIEFING_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BRIEFING_DIR / f"{date_str}.md"
    output_path.write_text(briefing, encoding="utf-8")

    # Also print to stdout
    _out(briefing)
    _out(f"\nBriefing written to: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

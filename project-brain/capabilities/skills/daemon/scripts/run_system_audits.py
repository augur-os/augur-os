#!/usr/bin/env python3
"""
Run System Audits - Master orchestration for all skill audits.

Runs all audit scripts, collects results, creates dashboard review task,
and schedules calendar reminder for Saturday review.

Usage:
    python run_system_audits.py              # Full run
    python run_system_audits.py --dry-run    # Preview only
    python run_system_audits.py --skills platform-admin  # Specific skills
"""

import sys
import json
import logging
import shutil
import yaml
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import importlib.util
from subprocess import CalledProcessError, CompletedProcess, run as subprocess_run  # nosec B404
from typing import Any

# Add project root to path
from bootstrap_paths import ensure_project_paths  # noqa: E402

project_root = ensure_project_paths(__file__)

from src.config.paths import get_runtime_dir


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))

logger = logging.getLogger(__name__)


SKILL_AUDITS = {
    "platform-admin": {
        "script": "project-brain/capabilities/skills/platform-admin/scripts/check_repo_health.py",
        "name": "Repo Health Audit",
    },
}


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable path when available."""
    if not command:
        return command
    resolved = shutil.which(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return command


def _run_command(command: list[str], **kwargs: Any) -> CompletedProcess[str]:
    """Run subprocess command with resolved executable path."""
    return subprocess_run(_resolve_command(command), **kwargs)  # nosec B603


@dataclass
class AuditRun:
    """Result of a full audit run."""

    timestamp: datetime = field(default_factory=datetime.now)
    audits_run: list = field(default_factory=list)
    total_findings: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    reports: list = field(default_factory=list)


def run_audit_script(skill: str, config: dict, dry_run: bool = False) -> dict:
    """Run a single audit script and return results."""
    script_path = project_root / config["script"]

    if not script_path.exists():
        return {
            "skill": skill,
            "name": config["name"],
            "success": False,
            "error": f"Script not found: {script_path}",
        }

    try:
        # Import and run the audit
        spec = importlib.util.spec_from_file_location(f"{skill}_audit", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        result = module.run_audit(dry_run=dry_run)
        result["skill"] = skill
        result["name"] = config["name"]
        return result

    except Exception as e:
        return {
            "skill": skill,
            "name": config["name"],
            "success": False,
            "error": str(e),
        }


def create_dashboard_review(run: AuditRun) -> str:
    """Create a review task in the dashboard."""
    reviews_dir = get_runtime_dir() / "attention" / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    reviews_file = reviews_dir / "pending_reviews.yaml"

    # Load existing reviews
    existing = []
    if reviews_file.exists():
        try:
            with open(reviews_file) as f:
                data = yaml.safe_load(f)
                existing = data.get("reviews", [])
        except (OSError, yaml.YAMLError, TypeError, ValueError, AttributeError) as exc:
            logger.debug("Failed to load existing pending reviews from %s: %s", reviews_file, exc)

    # Create new review task
    review_id = f"audit-{run.timestamp.strftime('%Y%m%d-%H%M%S')}"

    summary_parts = []
    for audit in run.audits_run:
        if audit.get("success"):
            summary = audit.get("summary", {})
            summary_parts.append(f"{audit['skill']}: {summary.get('findings_count', 0)} findings")

    new_review = {
        "id": review_id,
        "skill": "system",
        "title": f"Weekly System Audit - {run.timestamp.strftime('%Y-%m-%d')}",
        "summary": ", ".join(summary_parts) if summary_parts else "Audit run completed",
        "reportPath": str(run.reports[0]) if run.reports else "",
        "createdAt": run.timestamp.isoformat(),
        "status": "pending",
        "findingsCount": run.total_findings,
        "errorsCount": run.total_errors,
        "warningsCount": run.total_warnings,
    }

    existing.append(new_review)

    with open(reviews_file, "w") as f:
        yaml.dump({"reviews": existing}, f, default_flow_style=False)

    _out(f"📋 Created dashboard review: {review_id}")
    return review_id


def schedule_saturday_reminder():
    """Schedule a calendar reminder for Saturday 18:00."""
    # Find next Saturday
    today = datetime.now()
    days_until_saturday = (5 - today.weekday()) % 7  # Saturday is 5
    if days_until_saturday == 0 and today.hour >= 18:
        days_until_saturday = 7

    saturday = today + timedelta(days=days_until_saturday)
    saturday_6pm = saturday.replace(hour=18, minute=0, second=0, microsecond=0)

    # Create calendar event using osascript
    script = f'''
    tell application "Calendar"
        tell calendar "Augur"
            make new event with properties {{
                summary: "📊 Weekly System Audit Review",
                start date: date "{saturday_6pm.strftime('%B %d, %Y at %I:%M:%S %p')}",
                end date: date "{(saturday_6pm + timedelta(hours=1)).strftime('%B %d, %Y at %I:%M:%S %p')}",
                description: "Review system audits in Augur dashboard: /reviews"
            }}
        end tell
    end tell
    '''

    try:
        _run_command(["osascript", "-e", script], check=True, capture_output=True, text=True)
        _out(f"📅 Scheduled reminder: Saturday {saturday_6pm.strftime('%Y-%m-%d')} 18:00")
        return True
    except CalledProcessError as e:
        _out(f"⚠️  Could not schedule calendar event: {e.stderr if e.stderr else str(e)}")
        return False


def run_all_audits(skills: list = None, dry_run: bool = False, skip_calendar: bool = False) -> AuditRun:
    """Run all configured audits."""
    run = AuditRun()

    skills_to_run = skills or list(SKILL_AUDITS.keys())

    _out(f"🔍 Running {len(skills_to_run)} audits...")
    _out("=" * 50)

    for skill in skills_to_run:
        if skill not in SKILL_AUDITS:
            _out(f"⚠️  Unknown skill: {skill}")
            continue

        config = SKILL_AUDITS[skill]
        _out(f"\n▶ {config['name']}...")

        result = run_audit_script(skill, config, dry_run=dry_run)
        run.audits_run.append(result)

        if result.get("success"):
            summary = result.get("summary", {})
            run.total_findings += summary.get("findings_count", 0)
            run.total_errors += summary.get("errors", summary.get("critical", 0) + summary.get("high", 0))
            run.total_warnings += summary.get("warnings", summary.get("medium", 0))

            if result.get("report_path"):
                run.reports.append(result["report_path"])

            _out(f"   ✓ {summary.get('findings_count', 0)} findings")
        else:
            _out(f"   ✗ {result.get('error', 'Unknown error')}")

    _out("\n" + "=" * 50)
    _out(f"📊 Total: {run.total_findings} findings ({run.total_errors} errors, {run.total_warnings} warnings)")

    # Create dashboard review
    if not dry_run:
        create_dashboard_review(run)

    # Schedule calendar reminder
    if not dry_run and not skip_calendar:
        schedule_saturday_reminder()

    return run


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run System Audits")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--skills", type=str, help="Comma-separated list of skills to audit")
    parser.add_argument("--skip-calendar", action="store_true", help="Skip calendar reminder")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    skills = args.skills.split(",") if args.skills else None

    run = run_all_audits(skills=skills, dry_run=args.dry_run, skip_calendar=args.skip_calendar)

    if args.json:
        output = {
            "timestamp": run.timestamp.isoformat(),
            "audits": run.audits_run,
            "total_findings": run.total_findings,
            "reports": run.reports,
        }
        _out(json.dumps(output, indent=2))

#!/usr/bin/env python3
"""Verify adaptive loop commands against a chosen platform.

This runner is intentionally generic: it discovers the commands that belong to
the requested loop, resolves each module's declared platform capability, and
then runs scans only when the contract says the command is runnable.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from bootstrap_paths import ensure_project_paths  # noqa: E402

    PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_project_root
from src.lib.ops_protocol import OpsContext, resolve_ops_execution
from skills.daemon.scripts.adaptive.discovery import discover_auto_commands


@dataclass(frozen=True)
class PlatformVerifyItem:
    """Per-command verification result."""

    name: str
    outcome: str
    fix_mode: str
    scan_health: str = ""
    issue_count: int = 0
    actionable_issue_count: int = 0
    summary: str = ""
    skip_reason: str = ""


@dataclass(frozen=True)
class PlatformVerifyReport:
    """Aggregate verification result for a loop on one platform."""

    loop_name: str
    platform_name: str
    mode: str
    items: tuple[PlatformVerifyItem, ...]
    failures: tuple[str, ...]


def _entry_sort_key(entry: object) -> str:
    return str(getattr(entry, "name", ""))


def _declared_capabilities(entry: object) -> object | None:
    """Return module-declared capabilities, or None when not yet migrated."""
    module = getattr(entry, "module", None)
    if module is None or not hasattr(module, "OPS_CAPABILITIES"):
        return None
    return getattr(entry, "capabilities", None)


def _count_actionable_issues(issues: list[object]) -> int:
    """Count issues that should fail verify mode.

    Verify mode is intended to fail on actionable findings while allowing
    non-actionable maintenance/evolution gaps to remain visible without making
    the platform contract look broken.
    """
    non_actionable_kinds = {
        "clean",
        "environment",
        "external",
        "maintenance",
        "manual",
        "scanner-defect",
    }
    actionable = 0
    for issue in issues:
        if not isinstance(issue, dict):
            actionable += 1
            continue
        kind = str(issue.get("kind", "actionable") or "actionable")
        if kind not in non_actionable_kinds:
            actionable += 1
    return actionable


def verify_loop_platform(
    project_root: Path,
    loop_name: str,
    platform_name: str,
    mode: str = "verify",
    difficulty: int = 2,
) -> PlatformVerifyReport:
    """Verify every discovered auto-command in *loop_name* for *platform_name*."""
    registry = discover_auto_commands(project_root)
    entries = [
        entry
        for entry in registry.values()
        if getattr(entry, "loop_name", "") == loop_name
    ]
    entries.sort(key=_entry_sort_key)

    items: list[PlatformVerifyItem] = []
    failures: list[str] = []

    if not entries:
        failures.append(f"{loop_name}: no auto-commands discovered")

    for entry in entries:
        declared_capabilities = _declared_capabilities(entry)
        if declared_capabilities is None:
            items.append(
                PlatformVerifyItem(
                    name=entry.name,
                    outcome="skipped_unsupported",
                    fix_mode="unsupported",
                    skip_reason="OPS_CAPABILITIES not declared for this check yet",
                )
            )
            continue

        decision = resolve_ops_execution(
            declared_capabilities,
            platform_name=platform_name,
            allow_fix=False,
        )

        if not decision.run_scan:
            items.append(
                PlatformVerifyItem(
                    name=entry.name,
                    outcome="skipped_unsupported",
                    fix_mode=decision.fix_mode,
                    skip_reason=decision.skip_reason,
                )
            )
            continue

        module = getattr(entry, "module", None)
        scan = getattr(module, "scan", None)
        if not callable(scan):
            failures.append(f"{entry.name}: scan() is missing")
            items.append(
                PlatformVerifyItem(
                    name=entry.name,
                    outcome="failed",
                    fix_mode=decision.fix_mode,
                )
            )
            continue

        ctx = OpsContext(
            project_root=project_root,
            difficulty=difficulty,
            dry_run=True,
            config=getattr(entry, "config", {}) or {},
        )

        try:
            scan_result = scan(ctx)
        except Exception as exc:  # pragma: no cover - exercised through CLI/tests
            failures.append(f"{entry.name}: scan() raised {exc}")
            items.append(
                PlatformVerifyItem(
                    name=entry.name,
                    outcome="failed",
                    fix_mode=decision.fix_mode,
                )
            )
            continue

        scan_health = str(getattr(scan_result, "health", "verified"))
        issues = list(getattr(scan_result, "issues", []) or [])
        actionable_issue_count = _count_actionable_issues(issues)
        summary = str(getattr(scan_result, "summary", "") or "")
        if actionable_issue_count:
            failures.append(
                f"{entry.name}: {actionable_issue_count} actionable finding(s)"
            )

        items.append(
            PlatformVerifyItem(
                name=entry.name,
                outcome=decision.fix_mode,
                fix_mode=decision.fix_mode,
                scan_health=scan_health,
                issue_count=len(issues),
                actionable_issue_count=actionable_issue_count,
                summary=summary,
            )
        )

    return PlatformVerifyReport(
        loop_name=loop_name,
        platform_name=platform_name,
        mode=mode,
        items=tuple(items),
        failures=tuple(failures),
    )


def render_report(report: PlatformVerifyReport) -> list[str]:
    """Render a human-readable report for CLI use."""
    lines = [
        f"loop={report.loop_name} platform={report.platform_name} mode={report.mode}",
    ]

    for item in report.items:
        parts = [f"{item.name}: {item.outcome}"]
        if item.scan_health:
            parts.append(f"scan={item.scan_health}")
        if item.issue_count:
            parts.append(f"issues={item.issue_count}")
        if item.actionable_issue_count:
            parts.append(f"actionable={item.actionable_issue_count}")
        if item.summary:
            parts.append(f"summary={item.summary}")
        if item.outcome == "skipped_unsupported" and item.skip_reason:
            parts.append(f"reason={item.skip_reason}")
        lines.append(" ".join(parts))

    supported_count = sum(
        1 for item in report.items
        if item.outcome in {"report_only", "auto_fix", "ran"}
    )
    report_only_count = sum(1 for item in report.items if item.outcome == "report_only")
    skipped_count = sum(1 for item in report.items if item.outcome == "skipped_unsupported")

    lines.append(
        f"summary: {supported_count} supported, {report_only_count} report_only, "
        f"{skipped_count} skipped, {len(report.failures)} failed",
    )
    if report.failures:
        lines.append("failures:")
        lines.extend(f"  - {failure}" for failure in report.failures)

    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a loop against a platform contract")
    parser.add_argument("--loop", required=True, help="Loop name to verify, e.g. hardening")
    parser.add_argument("--platform", required=True, help="Target platform name, e.g. windows")
    parser.add_argument(
        "--mode",
        default="verify",
        help="Verification mode label to include in output",
    )
    parser.add_argument(
        "--difficulty",
        type=int,
        default=2,
        help="Non-mutating scan difficulty to use while verifying",
    )
    parser.add_argument(
        "--project-root",
        default="",
        help="Repository root to verify from; defaults to the active project root",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve() if args.project_root else get_project_root()
    report = verify_loop_platform(
        project_root=project_root,
        loop_name=args.loop,
        platform_name=args.platform,
        mode=args.mode,
        difficulty=args.difficulty,
    )

    for line in render_report(report):
        print(line)

    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

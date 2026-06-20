"""Reporting and formatting helpers for adaptive loop executor.

Provides pending issue scanning, executive report generation,
CLI metrics persistence, and status formatting for the adaptive loop engine.
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.logging import get_entity_logger
from src.lib.ops_protocol import OpsContext

from .engine import AdaptiveLoopEngine, CycleReport
from .discovery import normalize_scheduler, normalize_trigger
from .run_inspection import inspect_run, generate_evolve_analysis
from .evolve_queue import persist_suggestions, format_pending_report
from .evolve_remediate import apply_reclassify, format_remediation_report
from .snapshot import build_shared_snapshot

logger = get_entity_logger("adaptive_loop_reporter")


def _parse_iso8601(value: str) -> datetime | None:
    """Parse ISO timestamps from journal/runtime payloads."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_rel_path(project_root: Path, path: str) -> str:
    """Return a readable path label for report output."""
    if not path:
        return "n/a"
    path_obj = Path(path)
    try:
        return str(path_obj.relative_to(project_root))
    except ValueError:
        return str(path_obj)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Render a simple markdown table."""
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def _summarize_loop_ownership(loop_entries: list[Any]) -> tuple[str, str]:
    """Return overall owner plus a trigger-by-trigger ownership summary."""

    if not loop_entries:
        return "unknown", "no discovered scheduler metadata"

    owners_by_trigger: dict[str, set[str]] = {}
    for entry in loop_entries:
        trigger = normalize_trigger(getattr(entry, "trigger", None), "unknown")
        scheduler = normalize_scheduler(getattr(entry, "scheduler", None)) or "unknown"
        owners_by_trigger.setdefault(trigger, set()).add(scheduler)

    trigger_owners = {
        trigger: (sorted(schedulers)[0] if len(schedulers) == 1 else "mixed")
        for trigger, schedulers in sorted(owners_by_trigger.items())
    }
    unique_owners = set(trigger_owners.values())
    owner = next(iter(unique_owners)) if len(unique_owners) == 1 else "split"
    owner_detail = ", ".join(
        f"{trigger} via {scheduler}" for trigger, scheduler in trigger_owners.items()
    )
    return owner, owner_detail


def _load_latest_loop_reports(adaptive_dir: Path) -> dict[str, dict[str, Any]]:
    """Load latest per-loop JSON reports emitted by the adaptive engine."""
    reports_dir = adaptive_dir / "reports"
    loaded: dict[str, dict[str, Any]] = {}
    if not reports_dir.is_dir():
        return loaded

    for report_path in sorted(reports_dir.glob("*-latest.json")):
        if report_path.name.startswith("executor-"):
            continue
        loop_name = report_path.name.removesuffix("-latest.json")
        try:
            loaded[loop_name] = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return loaded


def _coverage_gap_summary(project_root: Path) -> tuple[int, str | None]:
    """Extract the current coverage gap count from the generated report."""
    report_path = project_root / "docs" / "generated" / "coverage-gaps-report.md"
    if not report_path.is_file():
        return 0, None

    try:
        content = report_path.read_text(encoding="utf-8")
    except OSError:
        return 0, str(report_path)

    match = re.search(r"##\s+(\d+)\s+Untested Python Modules", content)
    return (int(match.group(1)) if match else 0), str(report_path)


def generate_executive_report(
    engine: AdaptiveLoopEngine,
    config: dict[str, Any],
    *,
    days: int = 1,
) -> str:
    """Build the full `/routines report` executive report."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, days))
    entries = engine.journal_reader.read_all()
    recent_entries = [
        entry
        for entry in entries
        if (parsed := _parse_iso8601(entry.timestamp)) is not None and parsed >= cutoff
    ]
    latest_reports = _load_latest_loop_reports(engine._adaptive_dir)
    latest_outcome_by_category: dict[tuple[str, str], str] = {}
    for loop_name, report in latest_reports.items():
        for category in report.get("categories", []):
            category_name = category.get("name")
            if isinstance(category_name, str):
                latest_outcome_by_category[(loop_name, category_name)] = str(
                    category.get("outcome", "")
                )
    coverage_gap_count, coverage_report_path = _coverage_gap_summary(engine._project_root)
    last_by_loop = {}
    for entry in recent_entries:
        last_by_loop[entry.loop] = entry

    lines = [
        f"# Adaptive Loops Executive Report",
        "",
        f"- Window: last {max(1, days)} day(s)",
        f"- Generated: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
    ]

    configured_loops = set((config.get("loops") or {}).keys())
    known_loop_names = configured_loops | set(engine.loops.keys()) | engine._auto_loop_names
    all_loop_names = sorted(known_loop_names)
    loop_rows: list[list[str]] = []
    category_rows: list[list[str]] = []
    autofix_rows: list[list[str]] = []
    clean_rows: list[list[str]] = []
    failure_rows: list[list[str]] = []
    follow_up_items: list[tuple[int, str]] = []

    latest_by_category: dict[tuple[str, str], Any] = {}
    for entry in recent_entries:
        latest_by_category[(entry.loop, entry.category)] = entry

    clean_counts: dict[str, int] = {}
    for entry in recent_entries:
        if entry.action == "clean-scan" and entry.result == "success":
            clean_counts[entry.loop] = clean_counts.get(entry.loop, 0) + 1
        if entry.result == "success" and entry.action == "fix" and (entry.files or entry.commit):
            autofix_rows.append([
                entry.loop,
                entry.category,
                ", ".join(entry.files or []) or "n/a",
                entry.commit or "n/a",
            ])
        if entry.result in {"failure", "blocked", "deferred"}:
            if entry.loop not in known_loop_names:
                continue
            if latest_by_category.get((entry.loop, entry.category)) is not entry:
                continue
            latest_outcome = latest_outcome_by_category.get((entry.loop, entry.category))
            if latest_outcome and latest_outcome not in {
                "broken",
                "verification-failed-reverted",
                "blocked-needs-design",
                "context-insufficient",
                "design-written",
            }:
                continue
            action = entry.action or "unknown"
            recommendation = (
                "/routines heal --fix"
                if entry.result == "failure"
                else f"/routines run {entry.loop}"
            )
            failure_rows.append([
                entry.loop,
                entry.category,
                f"{entry.result}:{action}",
                (entry.error or "").replace("\n", " ")[:120] or "n/a",
                recommendation,
            ])

    for loop_name in all_loop_names:
        try:
            state = engine.ledger.get_loop_state(loop_name)
        except KeyError:
            continue
        categories = list(state.categories.values())
        enabled_categories = [cat for cat in categories if cat.enabled]
        avg_trust = (
            sum(cat.trust for cat in enabled_categories) / len(enabled_categories)
            if enabled_categories
            else 0.0
        )
        max_difficulty = max((cat.difficulty for cat in categories), default=0)
        latest_report = latest_reports.get(loop_name, {})
        report_categories = latest_report.get("categories", [])
        broken_count = sum(
            1
            for cat in report_categories
            if cat.get("outcome") in {"broken", "verification-failed-reverted"}
        )
        report_only_count = sum(
            1
            for cat in report_categories
            if cat.get("outcome") in {
                "report-only",
                "blocked-needs-design",
                "context-insufficient",
            }
            and cat.get("issue_count", 0) > 0
        )
        design_written_count = sum(
            1
            for cat in report_categories
            if cat.get("outcome") == "design-written" and cat.get("issue_count", 0) > 0
        )
        verdict = "healthy"
        if broken_count:
            verdict = f"broken:{broken_count}"
        elif design_written_count:
            verdict = f"design-written:{design_written_count}"
        elif report_only_count:
            verdict = f"follow-up:{report_only_count}"

        last_entry = last_by_loop.get(loop_name)
        last_result = (
            f"{last_entry.result}:{last_entry.action}"
            if last_entry and last_entry.action
            else "---"
        )
        loop_rows.append([
            loop_name,
            f"{state.budget - state.budget_remaining}/{state.budget}",
            f"{avg_trust:.2f}",
            f"d{max_difficulty}",
            verdict,
            last_result,
        ])

        for category_name, cat_state in sorted(
            state.categories.items(),
            key=lambda item: (item[1].trust, item[1].difficulty, item[0]),
        ):
            status_bits: list[str] = []
            if not cat_state.enabled:
                status_bits.append("disabled")
            if cat_state.disable_count:
                status_bits.append(f"disabled×{cat_state.disable_count}")
            if cat_state.consecutive_failures:
                status_bits.append(f"failures={cat_state.consecutive_failures}")
            if not status_bits:
                status_bits.append("enabled")
            category_rows.append([
                loop_name,
                category_name,
                f"{cat_state.trust:.2f}",
                f"d{cat_state.difficulty}",
                f"t{cat_state.tier}",
                str(cat_state.success_count),
                str(cat_state.failure_count),
                ", ".join(status_bits),
            ])

        for action in latest_report.get("next_actions", [])[:5]:
            priority = 0 if action.lower().startswith("fix ") else 1
            follow_up_items.append((priority, f"{loop_name}: {action}"))

        for category in report_categories:
            outcome = category.get("outcome", "")
            issue_count = int(category.get("issue_count", 0) or 0)
            if issue_count <= 0:
                continue
            if outcome in {"broken", "verification-failed-reverted"}:
                follow_up_items.append(
                    (0, f"{loop_name}/{category['name']}: broken scanner, run `/routines heal --fix`")
                )
            elif outcome == "blocked-needs-design":
                follow_up_items.append(
                    (
                        0,
                        f"{loop_name}/{category['name']}: structural issue needs design gate — {category.get('action_summary', '').strip()}",
                    )
                )
            elif outcome == "context-insufficient":
                follow_up_items.append(
                    (
                        1,
                        f"{loop_name}/{category['name']}: insufficient context for safe structural fix — {category.get('action_summary', '').strip()}",
                    )
                )
            elif outcome == "design-written":
                follow_up_items.append(
                    (
                        1,
                        f"{loop_name}/{category['name']}: design gate written, rerun at higher difficulty — {category.get('action_summary', '').strip()}",
                    )
                )
            elif outcome == "report-only":
                kind = "manual" if int(category.get("manual_count", 0) or 0) > 0 else "report-only"
                follow_up_items.append(
                    (
                        1 if kind == "report-only" else 2,
                        f"{loop_name}/{category['name']}: {issue_count} {kind} issue(s) — {category.get('action_summary', '').strip()}",
                    )
                )

    if coverage_gap_count:
        follow_up_items.append(
            (
                2,
                f"code-quality/auto-coverage-check: {coverage_gap_count} modules still in the coverage gap report"
                + (f" ({_format_rel_path(engine._project_root, coverage_report_path)})" if coverage_report_path else ""),
            )
        )

    lines.extend(["## Trust & Difficulty Per Loop", ""])
    lines.extend(_markdown_table(
        ["Loop", "Budget Used", "Avg Trust", "Max Diff", "Health", "Last Result"],
        loop_rows or [["none", "0/0", "0.00", "d0", "healthy", "---"]],
    ))
    lines.append("")

    lines.extend(["## Per-Category Trust Breakdown", ""])
    lines.extend(_markdown_table(
        ["Loop", "Category", "Trust", "Diff", "Tier", "OK", "Fail", "Status"],
        category_rows or [["none", "none", "0.00", "d0", "t0", "0", "0", "n/a"]],
    ))
    lines.append("")

    lines.extend(["## What Was Autofixed", ""])
    if autofix_rows:
        lines.extend(_markdown_table(["Loop", "Category", "Files", "Commit"], autofix_rows))
    else:
        lines.append("No verified autofixes in the selected window.")
    lines.append("")

    lines.extend(["## What Was Scanned Clean", ""])
    if clean_counts:
        clean_rows = [[loop_name, str(count)] for loop_name, count in sorted(clean_counts.items())]
        lines.extend(_markdown_table(["Loop", "Clean Scans"], clean_rows))
    else:
        lines.append("No clean-scan entries in the selected window.")
    lines.append("")

    lines.extend(["## What Failed Or Deferred", ""])
    if failure_rows:
        lines.extend(_markdown_table(["Loop", "Category", "Result", "Reason", "Suggested Command"], failure_rows))
    else:
        lines.append("No failures or deferred fixes in the selected window.")
    lines.append("")

    lines.extend(["## Top Items To Follow Up", ""])
    if follow_up_items:
        for idx, (_, item) in enumerate(sorted(set(follow_up_items), key=lambda item: (item[0], item[1]))[:20], start=1):
            lines.append(f"{idx}. {item}")
    else:
        lines.append("1. No active follow-up items detected.")
    lines.append("")

    report = "\n".join(lines).rstrip() + "\n"
    reports_dir = engine._adaptive_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / now.strftime("%Y-%m-%d.md")).write_text(report, encoding="utf-8")
    return report


def scan_pending_issues(
    engine: AdaptiveLoopEngine,
    config: dict[str, Any],
    project_root: Path,
) -> tuple[list[dict[str, Any]], int]:
    """Run scan-only across all auto-commands and collect pending issue counts."""
    pending: list[dict[str, Any]] = []
    total_issues = 0
    shared_snapshot = (
        build_shared_snapshot(project_root)
        if config.get("engine", {}).get("shared_snapshot", False)
        else {}
    )

    for loop_name in sorted(engine._auto_commands.keys()):
        loop_cfg = config.get("loops", {}).get(loop_name, {})
        if not isinstance(loop_cfg, dict):
            loop_cfg = {}
        for entry in sorted(engine._auto_commands[loop_name], key=lambda e: (e.tier, e.name)):
            entry_config = getattr(entry, "config", {})
            if not isinstance(entry_config, dict):
                entry_config = {}
            ctx = OpsContext(
                project_root=project_root,
                difficulty=0,
                dry_run=True,
                config=entry_config,
                loop_config=loop_cfg,
                shared_snapshot=shared_snapshot,
            )
            scan_t0 = time.monotonic()
            try:
                scan_result = entry.module.scan(ctx)
                scan_duration_ms = int((time.monotonic() - scan_t0) * 1000)
                issues = [
                    engine._normalize_issue(entry.name, issue)
                    for issue in (getattr(scan_result, "issues", []) or [])
                ]
                counts = engine._count_issue_kinds(issues)
                count = counts["actionable"]
                summary = getattr(scan_result, "summary", "")
                severity = getattr(scan_result, "severity", "info")
                pending.append(
                    {
                        "loop": loop_name,
                        "command": entry.name,
                        "tier": entry.tier,
                        "trigger": entry.trigger,
                        "scheduler": getattr(entry, "scheduler", "unknown"),
                        "count": count,
                        "maintenance_count": counts["maintenance"],
                        "environment_count": counts["environment"],
                        "scanner_defect_count": counts["scanner-defect"],
                        "manual_count": counts["manual"],
                        "broken_count": counts["broken"],
                        "scan_duration_ms": scan_duration_ms,
                        "severity": severity,
                        "summary": summary,
                    }
                )
                total_issues += count
            except Exception as exc:  # noqa: BLE001
                scan_duration_ms = int((time.monotonic() - scan_t0) * 1000)
                pending.append(
                    {
                        "loop": loop_name,
                        "command": entry.name,
                        "tier": entry.tier,
                        "trigger": entry.trigger,
                        "scheduler": getattr(entry, "scheduler", "unknown"),
                        "count": 0,
                        "scan_duration_ms": scan_duration_ms,
                        "severity": "error",
                        "summary": f"scan error: {exc}",
                    }
                )

    return pending, total_issues


def print_pending_report(pending: list[dict[str, Any]], total_issues: int) -> None:
    """Print a concise per-loop pending issue report."""
    print("Pending Issues Report")
    print("=====================")
    print(f"Total pending issues: {total_issues}")
    print(f"Total pending fixes: {total_issues}")
    print("")

    by_loop: dict[str, list[dict[str, Any]]] = {}
    for row in pending:
        by_loop.setdefault(row["loop"], []).append(row)

    for loop_name in sorted(by_loop.keys()):
        rows = sorted(by_loop[loop_name], key=lambda r: (r["tier"], r["command"]))
        loop_total = sum(int(r["count"]) for r in rows)
        print(f"Loop: {loop_name} (pending: {loop_total})")
        for row in rows:
            suffix_parts = []
            if row.get("maintenance_count"):
                suffix_parts.append(f"{row['maintenance_count']} maintenance")
            if row.get("environment_count"):
                suffix_parts.append(f"{row['environment_count']} environment")
            if row.get("scanner_defect_count"):
                suffix_parts.append(f"{row['scanner_defect_count']} scanner-defect")
            if row.get("manual_count"):
                suffix_parts.append(f"{row['manual_count']} manual")
            if row.get("scan_duration_ms", 0) >= 1000:
                suffix_parts.append(f"{row['scan_duration_ms']}ms")
            suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
            print(
                f"  Tier {row['tier']}: {row['command']} — {row['count']} actionable issue(s){suffix}"
            )
        print("")


def write_cli_metrics(
    runtime_dir: Path,
    mode: str,
    payload: dict[str, Any],
) -> Path | None:
    """Persist wrapper-level timing and outcome metrics for CLI executions."""
    reports_dir = runtime_dir / "adaptive" / "reports"
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("CLI metrics disabled for %s: %s", mode, exc)
        return None
    output_name = f"executor-{mode}-latest.json"
    if mode == "run":
        target_loop = str(payload.get("target_loop") or "").strip()
        if target_loop:
            output_name = f"executor-{mode}-{target_loop}-latest.json"
    output_path = reports_dir / output_name
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    try:
        output_path.write_text(json.dumps(data, indent=2))
    except OSError as exc:
        logger.warning("CLI metrics disabled for %s: %s", mode, exc)
        return None
    return output_path


def run_evolve_phase(
    engine: AdaptiveLoopEngine,
    project_root: Path,
    run_start_iso: str,
    reports: list[CycleReport],
) -> int:
    """Run evolve analysis/reporting for the provided reports."""
    if not reports:
        return 0

    evolve_t0 = time.monotonic()
    inspection = inspect_run(project_root, run_start_iso, reports)
    print(inspection.format())
    analysis = generate_evolve_analysis(inspection, reports, project_root)
    print(analysis)

    new_entries = persist_suggestions(
        reports, project_root,
        auto_commands=engine._auto_commands,
    )
    if new_entries:
        print(f"\n  Queued {len(new_entries)} new evolve suggestions.")

    # ADR-458 Phase 2: Auto-apply reclassify fixes at d2+
    max_difficulty = 0
    for loop_name_key in engine._auto_commands:
        try:
            ls = engine.ledger.get_loop_state(loop_name_key)
            for cs in ls.categories.values():
                if cs.difficulty > max_difficulty:
                    max_difficulty = cs.difficulty
        except KeyError:
            pass

    if max_difficulty >= 2:
        remediation_results = apply_reclassify()
        if remediation_results:
            print(format_remediation_report(remediation_results))
    else:
        logger.info("Evolve remediation skipped: max difficulty %d < 2", max_difficulty)

    pending_report = format_pending_report()
    if pending_report.strip() and "No pending" not in pending_report:
        print(pending_report)

    return int((time.monotonic() - evolve_t0) * 1000)


def format_status(engine: AdaptiveLoopEngine, config: dict) -> str:
    """Format status output for /routines status."""
    lines = []
    engine_cfg = config.get("engine", {})
    lines.append(
        f"Adaptive Loop Engine: {'ACTIVE' if engine_cfg.get('enabled') else 'DISABLED'}"
    )
    lines.append(f"Next nightly run: {engine_cfg.get('nightly_time', '03:00')}")
    lines.append("")
    lines.append(
        f"{'LOOP':<22} {'STATUS':<10} {'BUDGET':<10} {'TRUST':<10} "
        f"{'TRIGGER':<15} {'OWNER':<10} {'LAST EVENT (UTC)':<20} {'LAST RESULT':<24} {'OWNER DETAIL'}"
    )

    last_by_loop = {}
    for entry in engine.journal_reader.read_all():
        last_by_loop[entry.loop] = entry

    # Include both legacy loops and auto-command loops
    all_loop_names = sorted(set(engine.loops.keys()) | engine._auto_loop_names)
    for loop_name in all_loop_names:
        try:
            state = engine.ledger.get_loop_state(loop_name)
            status = "ENABLED" if state.enabled else "DISABLED"
            budget = f"{state.budget_remaining}/{state.budget}"
            # Average trust across enabled categories
            enabled_cats = [c for c in state.categories.values() if c.enabled]
            avg_trust = (
                f"{sum(c.trust for c in enabled_cats) / len(enabled_cats):.2f}"
                if enabled_cats
                else "---"
            )
            trigger = state.trigger if hasattr(state, "trigger") else "---"
            # Auto-command loops carry trigger on entries (ADR-200); infer from
            # registry so status reflects continuous/post-execution correctly.
            if loop_name in engine._auto_commands:
                loop_entries = engine._auto_commands.get(loop_name, [])
                loop_triggers = {e.trigger for e in loop_entries if getattr(e, "trigger", None)}
                if len(loop_triggers) == 1:
                    trigger = next(iter(loop_triggers))
                elif len(loop_triggers) > 1:
                    trigger = "mixed"
            owner = "unknown"
            owner_detail = "no discovered scheduler metadata"
            if loop_name in engine._auto_commands:
                loop_entries = engine._auto_commands.get(loop_name, [])
                owner, owner_detail = _summarize_loop_ownership(loop_entries)
            last_entry = last_by_loop.get(loop_name)
            last_event = "---"
            last_result = "---"
            if last_entry:
                # Keep readable UTC-like timestamp without microseconds/timezone.
                last_event = (
                    last_entry.timestamp.replace("T", " ").split(".")[0]
                )
                last_result = (
                    f"{last_entry.result}:{last_entry.action}"
                    if last_entry.action
                    else last_entry.result
                )
            lines.append(
                f"{loop_name:<22} {status:<10} {budget:<10} {avg_trust:<10} "
                f"{trigger:<15} {owner:<10} {last_event:<20} {last_result:<24} {owner_detail}"
            )
        except (KeyError, AttributeError):
            lines.append(f"{loop_name:<22} {'NEW':<10}")

    return "\n".join(lines)

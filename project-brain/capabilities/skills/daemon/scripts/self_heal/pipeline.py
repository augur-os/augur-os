"""
Main self-heal pipeline and notification system.

Orchestrates: scan -> dedup -> classify -> route -> fix/TODO
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ai_self_healer import ErrorFinding, RegistryEntry


# Notification dedup — suppress identical messages within cooldown window
_notif_cache: dict[str, datetime] = {}
_NOTIF_COOLDOWN_SECONDS = 600  # 10 minutes


def _notify(message: str, config: dict, event: str = "", copy_text: str = "") -> None:
    """Send notification if enabled and NotificationService is available.

    Deduplicates: the same message won't fire more than once per 10 minutes.
    When copy_text is provided, clicking the notification copies error
    context to clipboard (instead of opening a URL).
    """
    import ai_self_healer as _healer

    logger = _healer.logger
    NotificationService = _healer.NotificationService

    notif_conf = config.get("notifications", {})
    if not notif_conf.get(event, True):
        return

    if NotificationService is None:
        logger.info(f"[NOTIFY] {message}")
        return

    # Rate limit — suppress duplicate notifications
    dedup_key = f"{event}:{message[:100]}"
    now = datetime.now()
    last_sent = _notif_cache.get(dedup_key)
    if last_sent and (now - last_sent).total_seconds() < _NOTIF_COOLDOWN_SECONDS:
        return

    try:
        svc = NotificationService()
        svc.notify(
            message,
            category="self_heal",
            event=event,
            title="Augur Self-Heal",
            copy_text=copy_text,
        )
        _notif_cache[dedup_key] = now
    except Exception as e:
        logger.warning(f"Notification failed: {e}")


_SEVERITY_TO_PRIORITY: dict[str, str] = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "error": "critical",
}


def _raise_self_heal_attention(entry: "RegistryEntry") -> None:
    """Bridge a failed/aborted self-heal issue to the attention system.

    Creates an attention item with suggested_action="fix" so the dashboard
    button generates a "fix this manually" prompt for the CLI.
    """
    import ai_self_healer as _healer

    logger = _healer.logger

    try:
        _skills_root = Path(__file__).resolve().parents[3]
        if str(_skills_root) not in sys.path:
            sys.path.insert(0, str(_skills_root))

        from channels.augur.lib.registry import raise_attention  # type: ignore[import-untyped]
        from self_heal.escalation import format_fix_prompt

        priority = _SEVERITY_TO_PRIORITY.get(entry.severity, "medium")
        body = format_fix_prompt(entry)

        raise_attention(
            skill="daemon",
            source_type="notification",
            title=f"Self-heal failed: {entry.message[:80]}",
            summary=body,
            priority=priority,
            suggested_action={"action": "fix"},
        )
    except Exception as exc:
        logger.debug("Attention bridge skipped: %s", exc)


def run_pipeline(config: dict) -> dict:
    """Execute the full scan -> classify -> route -> act pipeline.

    Returns summary dict.
    """
    import ai_self_healer as _healer

    logger = _healer.logger
    ErrorFinding = _healer.ErrorFinding

    summary: dict[str, Any] = {
        "scanned": 0,
        "new_issues": 0,
        "classified": 0,
        "items_created": 0,
        "fixes_attempted": 0,
        "fixes_succeeded": 0,
        "todos_created": 0,
        "timestamp": datetime.now().isoformat(),
    }

    if not config.get("enabled", True):
        return summary

    # 0. Adaptive discovery — find new log files with errors
    adaptive_discovery = config.get("adaptive_discovery")
    if adaptive_discovery is None:
        adaptive_discovery = False

    if adaptive_discovery:
        try:
            new_targets = _healer.discover_untracked_logs(config)
            added = _healer.persist_discovered_targets(new_targets, config)
            if added:
                summary["targets_discovered"] = added
        except Exception as e:
            logger.warning(f"Adaptive discovery failed (non-fatal): {e}")

    # 1. Scan for new findings
    findings = _healer.scan_runtime(config)

    # 1b. Resource health checks (CPU, memory, cache size)
    resource_findings = _healer.check_resource_health(config)
    if resource_findings:
        findings.extend(resource_findings)
        summary["resource_checks"] = len(resource_findings)

    summary["scanned"] = len(findings)

    # 2. Dedup new findings
    registry = _healer.load_registry()
    registry, compacted_count = _healer.compact_dismissed_registry_entries(registry)
    if compacted_count:
        summary["registry_compacted"] = compacted_count
        logger.info(f"Compacted {compacted_count} duplicate dismissed registry entries")
    actionable = _healer.deduplicate_findings(findings, registry, config) if findings else []
    summary["new_issues"] = len(actionable)

    # 3. Recover stuck entries and pick up backlog
    backlog_limit = config.get("fix", {}).get("backlog_per_cycle", 3)
    max_retries = config.get("fix", {}).get("max_retries", 3)
    already_queued = {f.dedup_key for f in actionable}

    # 3a. Recover entries stuck in "fixing" (interrupted mid-fix)
    for e in registry.values():
        if e.status == "fixing" and e.dedup_key not in already_queued:
            logger.info(f"Recovering stuck 'fixing' entry: {e.dedup_key}")
            e.status = "new"

    # 3b. Abandon entries that have exhausted max retries
    for e in registry.values():
        if e.status in ("new", "classifying") and e.fix_attempts >= max_retries:
            logger.info(f"Abandoning max-retry entry: {e.dedup_key} ({e.fix_attempts} attempts)")
            e.status = "abandoned"
            e.fix_result = f"max_retries_exhausted ({e.fix_attempts} attempts)"
            _healer.create_todo_marker(e)

    # 3c. Pick up backlog
    stuck = [
        e
        for e in registry.values()
        if e.status in ("new", "classifying")
        and e.fix_attempts < max_retries
        and e.dedup_key not in already_queued
    ]
    for entry in stuck[:backlog_limit]:
        actionable.append(
            ErrorFinding(
                message=entry.message,
                file=entry.file,
                dedup_key=entry.dedup_key,
                stack_trace=entry.stack_trace,
            )
        )
        summary["backlog_picked"] = summary.get("backlog_picked", 0) + 1

    _healer.save_registry(registry)

    if not actionable:
        return summary

    # 4. Resolve CLI once
    cli_path = _healer.resolve_cli(config)

    # 5. Classify + Route + Act
    for finding in actionable:
        entry = registry[finding.dedup_key]

        # Circuit breaker
        if entry.fix_attempts >= 3 and entry.fix_result and entry.fix_result.startswith("failed"):
            entry.status = "wont_fix"
            logger.info(
                f"Circuit breaker: {entry.dedup_key} failed {entry.fix_attempts} times, "
                f"marking wont_fix"
            )
            _healer.save_registry(registry)
            summary["circuit_broken"] = summary.get("circuit_broken", 0) + 1
            continue

        # Skip re-classification for escalated entries
        if entry.fix_result and entry.fix_result.startswith("escalated_from_"):
            logger.info(
                f"Preserving escalated severity {entry.severity} for {entry.dedup_key} "
                f"({entry.fix_result}, {entry.occurrences} occurrences)"
            )
            summary["classified"] += 1
        elif (hint := _healer.pre_classify(entry)):
            entry.severity = hint.get("severity", "medium")
            entry.category = hint.get("category", "integration")
            entry.suggested_approach = hint.get("suggested_approach")
            summary["classified"] += 1
            logger.info(f"Pre-classified {entry.dedup_key} as {entry.severity} (pattern match)")
        elif cli_path:
            entry.status = "classifying"
            _healer.save_registry(registry)

            classification = _healer.classify_issue(entry, config, cli_path)
            if classification:
                entry.severity = classification.get("severity", "medium")
                entry.category = classification.get("category", "integration")
                entry.suggested_approach = classification.get("suggested_approach")
                summary["classified"] += 1
            else:
                entry.severity = "medium"
        else:
            entry.severity = "medium"

        # Shell action check
        shell_match = _healer.match_shell_action(entry)
        if shell_match:
            shell_cmd, shell_desc = shell_match
            entry.fix_attempts += 1
            entry.status = "fixing"
            _healer.save_registry(registry)
            shell_result = _healer.execute_shell_action(entry, shell_cmd, shell_desc)
            summary["fixes_attempted"] += 1
            if shell_result.get("success"):
                entry.status = "fixed"
                entry.fix_result = f"shell_action: {shell_desc}"
                summary["fixes_succeeded"] += 1
                _healer._notify(
                    f"Shell fix applied: {shell_desc}",
                    config,
                    event="on_fix_success",
                    copy_text=f"Shell fix: {shell_desc}\nIssue: {entry.message}",
                )
            else:
                entry.status = "failed"
                entry.fix_result = f"shell_action_failed: {shell_result.get('output', '')[:200]}"
                _healer.create_todo_marker(entry)
                summary["todos_created"] += 1
            _healer.save_registry(registry)
            continue

        # Route
        action = _healer.route_issue(entry, config)

        if action == "dismiss":
            entry.status = "dismissed"
            entry.fix_result = "transient_runtime_issue"
            logger.info(f"Dismissed transient issue: {entry.dedup_key} -- {entry.message[:80]}")
            summary["dismissed"] = summary.get("dismissed", 0) + 1
            _healer.save_registry(registry)
            continue

        logger.info(f"Detected {entry.severity.upper()} issue: {entry.message[:80]}")
        _healer._notify(
            f"Detected {entry.severity.upper()} issue: {entry.message[:100]}",
            config,
            event="on_detect",
            copy_text=_healer.format_fix_prompt(entry),
        )

        if action == "fix":
            entry.fix_attempts += 1
            item_path = _healer.create_critical_item(entry)
            summary["items_created"] = summary.get("items_created", 0) + 1

            if cli_path and _healer.acquire_fix_lock(entry.dedup_key):
                try:
                    entry.status = "fixing"
                    _healer.save_registry(registry)

                    result = _healer.invoke_headless_fix(entry, config, cli_path)
                    summary["fixes_attempted"] += 1

                    if result.get("aborted"):
                        entry.status = "abandoned"
                        entry.fix_result = "aborted_complex"
                        _healer.create_todo_marker(entry)
                        summary["todos_created"] += 1
                        copy_text = _healer.format_fix_prompt(entry)
                        _healer._notify(
                            f"[{entry.severity.upper()}] Too complex for auto-fix: {entry.message[:80]}",
                            config,
                            event="on_abort",
                            copy_text=copy_text,
                        )
                        _raise_self_heal_attention(entry)
                    elif result.get("success"):
                        entry.status = "fixed"
                        entry.fix_result = "resolved"
                        entry.fix_commit = result.get("commit")
                        summary["fixes_succeeded"] += 1
                        item_path.write_text(
                            item_path.read_text().replace(
                                "**Status**: awaiting_manual_fix",
                                f"**Status**: fixed (commit {entry.fix_commit})",
                            )
                        )
                        _healer._notify(
                            f"Fixed: {entry.message[:80]} (commit: {entry.fix_commit})",
                            config,
                            event="on_fix_success",
                            copy_text=f"Fixed: {entry.message}\nCommit: {entry.fix_commit}",
                        )
                    else:
                        entry.status = "failed"
                        entry.fix_result = result.get("output", "unknown")[:200]
                        _healer.create_todo_marker(entry)
                        summary["todos_created"] += 1
                        copy_text = _healer.format_fix_prompt(entry)
                        _healer._notify(
                            f"[{entry.severity.upper()}] Auto-fix failed: {entry.message[:80]}",
                            config,
                            event="on_fix_failure",
                            copy_text=copy_text,
                        )
                        _raise_self_heal_attention(entry)
                finally:
                    _healer.release_fix_lock()
            else:
                entry.status = "failed"
                _healer.create_todo_marker(entry)
                summary["todos_created"] += 1
                copy_text = _healer.format_fix_prompt(entry)
                _healer._notify(
                    f"[{entry.severity.upper()}] {entry.message[:100]}",
                    config,
                    event="on_detect",
                    copy_text=copy_text,
                )
                _raise_self_heal_attention(entry)
        else:
            entry.status = "todo_created"
            _healer.create_todo_marker(entry)
            summary["todos_created"] += 1

        _healer.save_registry(registry)

    return summary

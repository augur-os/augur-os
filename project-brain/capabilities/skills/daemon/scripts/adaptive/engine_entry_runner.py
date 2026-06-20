"""Per-entry scan/fix execution for auto-command cycles.

Extracted from engine.py (the inner run_entry closure of run_auto_cycle).
This module provides run_entry_scan_fix() as a standalone function that
operates on mutable collections passed by the caller.

The fix-phase logic lives in engine_fix_phase.py.
"""
from __future__ import annotations


# TODO_CLEANUP: This file is 1026 lines — consider splitting into smaller modules
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
import logging
import sys
import time
from typing import Any

from .loops.base_loop import LoopResult
from .reporting import CategoryReport
from .engine_fix_phase import _store_cat_report, run_fix_phase
from .evolve_queue import FIX_RECLASSIFY
from .evolve_remediate import get_reclassify_hint, verify_reclassify, clear_hint
from .trust_constants import CLEAN_SCAN_SKIP_THRESHOLD, CLEAN_SCAN_SKIP_MODULO

logger = logging.getLogger(__name__)


def build_platform_category_report(
    *,
    entry_name: str,
    trust_before: float,
    difficulty: int,
    decision: Any,
) -> CategoryReport:
    """Build a stable category report for platform-gated skips."""
    return CategoryReport(
        name=entry_name,
        trust_before=trust_before,
        trust_after=trust_before,
        difficulty_before=difficulty,
        difficulty_after=difficulty,
        status="skipped",
        action_summary=decision.skip_reason or "platform unsupported",
        outcome=decision.outcome,
    )


def run_entry_scan_fix(
    *,
    engine: Any,
    loop_name: str,
    loop_state: Any,
    entry: Any,
    trigger_filter: str | None,
    shared_snapshot: dict[str, Any],
    results: list[LoopResult],
    cat_reports: list[CategoryReport],
    broken_categories: set[str],
    degraded_categories: set[str],
    invalidated_categories: set[str],
    dep_invalidations: dict[str, set[str]],
    cycle_state: dict[str, Any],
    allow_invalidations: bool,
    no_coverage_categories: set[str] | None = None,
) -> bool:
    """Execute scan/fix for a single auto-command entry.

    Mutates results, cat_reports, broken_categories, degraded_categories,
    invalidated_categories, and cycle_state in-place.

    Returns True if the loop should continue (budget not exhausted).
    """
    # Filter by trigger if applicable
    if trigger_filter and entry.trigger != trigger_filter:
        return True

    if not engine.ledger.check_allowed(loop_name, entry.name):
        return True

    cat_state = loop_state.categories.get(entry.name)
    event_driven_entry = entry.trigger == "post-execution"

    # Fix #6: Skip dormant categories — but check if snapshot changed first.
    # If new code appeared, wake the category so it scans next cycle.
    # Post-execution categories consume runtime telemetry, not just code
    # snapshots, so they must still scan when events arrive.
    if cat_state and cat_state.strategy == "dormant" and not event_driven_entry:
        snap_fp = engine._snapshot_fingerprint(entry.name, shared_snapshot)
        if not snap_fp:
            # Legacy dormant states without snapshot support cannot wake
            # themselves, so fall back to active scanning.
            cat_state.strategy = "scan"
            cat_state.consecutive_clean_scans = 0
        elif snap_fp != cat_state.last_snapshot_fingerprint:
            # Wake: snapshot changed, run convergence to transition back to "scan"
            engine.ledger.record_convergence(
                loop_name, entry.name, issues=[],
                snapshot_fingerprint=snap_fp,
                entry_module=getattr(entry, "module", None),
            )
            # If still dormant after convergence (shouldn't happen), skip
            if cat_state.strategy == "dormant":
                return True
            # Fall through to run the scan
        else:
            return True

    # Clean-scan throttle: categories that have been clean for many
    # consecutive cycles only run once every N cycles to save compute.
    if (
        cat_state
        and not event_driven_entry
        and cat_state.consecutive_clean_scans >= CLEAN_SCAN_SKIP_THRESHOLD
        and cat_state.difficulty >= 1
        and loop_state.cycle_count % CLEAN_SCAN_SKIP_MODULO != 0
    ):
        return True

    trust_before = cat_state.trust if cat_state else 0.0
    diff_before = engine.ledger.get_difficulties(loop_name).get(entry.name, 0)
    strategy_before = cat_state.strategy if cat_state else "scan"
    previous_actionable = set(
        getattr(cat_state, "last_actionable_fingerprints", []) or []
    )
    previous_scanner = set(
        getattr(cat_state, "last_scanner_defect_fingerprints", []) or []
    )
    forced_deep_requested = bool(
        cat_state
        and getattr(cat_state, "force_deep_runs_remaining", 0) > 0
        and diff_before > 0
    )

    loop_cfg = engine._config.get("loops", {}).get(loop_name, {})
    if not isinstance(loop_cfg, dict):
        loop_cfg = {}
    entry_config = getattr(entry, "config", {})
    if not isinstance(entry_config, dict):
        entry_config = {}
    snap_fp = engine._snapshot_fingerprint(entry.name, shared_snapshot)
    should_short_circuit = engine._should_short_circuit_classify(
        cat_state, entry.name, entry_config, diff_before, snap_fp,
    )

    execution_mode, deepening_reason = _resolve_execution_mode(
        diff_before, should_short_circuit, forced_deep_requested,
        engine, entry, entry_config, cat_state, snap_fp,
    )

    # Import OpsContext here to avoid module-level cross-dependency
    from src.lib.ops_protocol import OpsContext, SessionContext, resolve_ops_execution

    _session = getattr(engine, '_session', SessionContext())
    _client = getattr(engine, '_local_client', None)

    ctx = OpsContext(
        project_root=engine._project_root,
        difficulty=diff_before,
        config=entry_config,
        loop_config=loop_cfg,
        shared_snapshot=shared_snapshot,
        session=_session,
        client=_client,
    )
    decision = resolve_ops_execution(
        getattr(entry, "capabilities", None),
        platform_name=sys.platform,
        allow_fix=not ctx.dry_run,
    )
    if not decision.run_scan:
        _store_cat_report(cat_reports, build_platform_category_report(
            entry_name=entry.name,
            trust_before=trust_before,
            difficulty=diff_before,
            decision=decision,
        ))
        return True
    ctx.config = {
        **ctx.config,
        "_ops_fix_mode": decision.fix_mode,
        "_ops_skip_reason": decision.skip_reason,
    }
    classify_ctx = OpsContext(
        project_root=engine._project_root,
        difficulty=0,
        config=entry_config,
        loop_config=loop_cfg,
        shared_snapshot=shared_snapshot,
        session=_session,
        client=_client,
    )

    is_first_run = cat_state and (cat_state.success_count + cat_state.failure_count == 0)

    t0 = time.monotonic()

    # -- Scan phase --
    scan_result, scan_duration_ms = _run_scan_phase(
        engine, loop_name, entry, cat_state, loop_state,
        should_short_circuit, classify_ctx, ctx,
        forced_deep_requested, is_first_run,
        trust_before, diff_before, deepening_reason, execution_mode,
        results, cat_reports, broken_categories, cycle_state, t0,
    )
    if scan_result is None:
        return True  # scan failed, already recorded

    scan_health = getattr(scan_result, "health", "verified")
    if scan_health == "broken":
        _handle_broken_scan(
            engine, loop_name, entry, cat_state, loop_state,
            scan_result, scan_duration_ms,
            forced_deep_requested, is_first_run,
            trust_before, diff_before, deepening_reason, execution_mode,
            should_short_circuit,
            results, cat_reports, broken_categories, cycle_state,
        )
        return True

    if scan_health == "degraded":
        degraded_categories.add(entry.name)

    # -- Issue analysis --
    issues = [
        engine._normalize_issue(entry.name, issue)
        for issue in (getattr(scan_result, "issues", []) or [])
    ]

    # ADR-458: Apply evolve reclassify hints to issues before counting
    hint = get_reclassify_hint(entry.name)
    pre_hint_actionable = sum(1 for i in issues if i.get("kind") == "actionable")
    if hint and hint.get("action") == FIX_RECLASSIFY:
        from_kind = hint.get("from_kind", "actionable")
        to_kind = hint.get("to_kind", "maintenance")
        for issue in issues:
            if issue.get("kind") == from_kind:
                issue["kind"] = to_kind
        post_hint_actionable = sum(1 for i in issues if i.get("kind") == "actionable")
        if post_hint_actionable < pre_hint_actionable:
            logger.info(
                "ADR-458: reclassify hint applied for %s: %d→%d actionable",
                entry.name, pre_hint_actionable, post_hint_actionable,
            )
        outcome = verify_reclassify(entry.name, pre_hint_actionable, post_hint_actionable)
        if outcome in ("no-change", "reverted"):
            clear_hint(entry.name)

    issue_counts = engine._count_issue_kinds(issues)
    current_actionable, current_scanner = engine._issue_fingerprint_sets(issues)
    yc, new_count, repeated_count, resolved_count = engine._yield_class(
        execution_mode, issues, issue_counts,
        previous_actionable, current_actionable, current_scanner,
    )
    if forced_deep_requested:
        engine.ledger.consume_forced_deep_scan(loop_name, entry.name)

    # -- Clean scan (no issues) --
    if not issues:
        if getattr(scan_result, "run_fix_on_clean", False) and not ctx.dry_run:
            return run_fix_phase(
                engine=engine,
                loop_name=loop_name,
                loop_state=loop_state,
                entry=entry,
                ctx=ctx,
                issues=[],
                issue_counts=issue_counts,
                scan_duration_ms=scan_duration_ms,
                trust_before=trust_before,
                diff_before=diff_before,
                strategy_before=strategy_before,
                deepening_reason=deepening_reason,
                execution_mode=execution_mode,
                should_short_circuit=should_short_circuit,
                snap_fp=snap_fp,
                yc=yc,
                new_count=new_count,
                repeated_count=repeated_count,
                resolved_count=resolved_count,
                results=results,
                cat_reports=cat_reports,
                invalidated_categories=invalidated_categories,
                dep_invalidations=dep_invalidations,
                allow_invalidations=allow_invalidations,
                t0=t0,
            )
        _handle_clean_entry(
            engine, loop_name, entry, loop_state,
            scan_result, scan_duration_ms, scan_health, snap_fp,
            should_short_circuit, strategy_before,
            trust_before, diff_before, deepening_reason, execution_mode,
            yc, new_count, repeated_count, resolved_count,
            cat_reports,
            no_coverage_categories=no_coverage_categories,
        )
        return True

    # -- Fix phase --
    cycle_state["any_issues_found"] = True
    cs = loop_state.categories.get(entry.name)
    if cs:
        cs.consecutive_clean_scans = 0

    if _entry_uses_orchestrator(entry):
        return _run_orchestrator_fix_phase(
            engine=engine,
            loop_name=loop_name,
            loop_state=loop_state,
            entry=entry,
            ctx=ctx,
            issues=issues,
            issue_counts=issue_counts,
            scan_duration_ms=scan_duration_ms,
            trust_before=trust_before,
            diff_before=diff_before,
            deepening_reason=deepening_reason,
            execution_mode=execution_mode,
            should_short_circuit=should_short_circuit,
            snap_fp=snap_fp,
            yc=yc,
            new_count=new_count,
            repeated_count=repeated_count,
            resolved_count=resolved_count,
            results=results,
            cat_reports=cat_reports,
            t0=t0,
        )

    engine.ledger.consume_budget(loop_name)

    return run_fix_phase(
        engine=engine,
        loop_name=loop_name,
        loop_state=loop_state,
        entry=entry,
        ctx=ctx,
        issues=issues,
        issue_counts=issue_counts,
        scan_duration_ms=scan_duration_ms,
        trust_before=trust_before,
        diff_before=diff_before,
        strategy_before=strategy_before,
        deepening_reason=deepening_reason,
        execution_mode=execution_mode,
        should_short_circuit=should_short_circuit,
        snap_fp=snap_fp,
        yc=yc,
        new_count=new_count,
        repeated_count=repeated_count,
        resolved_count=resolved_count,
        results=results,
        cat_reports=cat_reports,
        invalidated_categories=invalidated_categories,
        dep_invalidations=dep_invalidations,
        allow_invalidations=allow_invalidations,
        t0=t0,
    )


def _entry_uses_orchestrator(entry: Any) -> bool:
    runner = getattr(entry, "runner", "")
    return isinstance(runner, str) and runner.strip().lower() == "orchestrator"


def _issues_as_orchestrator_findings(
    *,
    loop_name: str,
    entry_name: str,
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for issue in issues:
        finding = dict(issue)
        finding.setdefault("auto_command", entry_name)
        finding.setdefault("loop", loop_name)
        findings.append(finding)
    return findings


def _run_orchestrator_fix_phase(
    *,
    engine: Any,
    loop_name: str,
    loop_state: Any,
    entry: Any,
    ctx: Any,
    issues: list[dict[str, Any]],
    issue_counts: dict[str, int],
    scan_duration_ms: int,
    trust_before: float,
    diff_before: int,
    deepening_reason: str,
    execution_mode: str,
    should_short_circuit: bool,
    snap_fp: str,
    yc: str,
    new_count: int,
    repeated_count: int,
    resolved_count: int,
    results: list[LoopResult],
    cat_reports: list[CategoryReport],
    t0: float,
) -> bool:
    """Delegate the fix phase for a marked entry to ADR-755's orchestrator."""
    engine.ledger.consume_budget(loop_name)
    consumed_budget_remaining = getattr(loop_state, "budget_remaining", 0)

    try:
        try:
            from routine_orchestrator import orchestrator
        except ModuleNotFoundError:
            from skills.daemon.scripts.routine_orchestrator import orchestrator

        result = orchestrator.fix_one_command(
            loop_name,
            command=entry,
            findings=_issues_as_orchestrator_findings(
                loop_name=loop_name,
                entry_name=entry.name,
                issues=issues,
            ),
            project_root=engine._project_root,
            runtime_dir=engine._runtime_dir,
            state_dir=engine._adaptive_dir,
            trust_config=engine._config,
            session=None,
            difficulty=ctx.difficulty,
            loop_config=ctx.loop_config,
            shared_snapshot=ctx.shared_snapshot,
            client=ctx.client,
            verify_command=engine._verify_command or None,
        )
    except Exception as exc:  # noqa: BLE001 - route failures are loop failures.
        return _record_orchestrator_route_failure(
            engine=engine,
            loop_name=loop_name,
            loop_state=loop_state,
            entry=entry,
            issues=issues,
            issue_counts=issue_counts,
            scan_duration_ms=scan_duration_ms,
            trust_before=trust_before,
            diff_before=diff_before,
            deepening_reason=deepening_reason,
            execution_mode=execution_mode,
            should_short_circuit=should_short_circuit,
            yc=yc,
            new_count=new_count,
            repeated_count=repeated_count,
            resolved_count=resolved_count,
            results=results,
            cat_reports=cat_reports,
            t0=t0,
            error=exc,
        )

    _reload_ledger_after_orchestrator(
        engine,
        loop_name=loop_name,
        consumed_budget_remaining=consumed_budget_remaining,
    )
    if _orchestrator_refunds_budget(result):
        loop_state.budget_remaining = min(
            loop_state.budget_remaining + 1,
            loop_state.budget,
        )
        engine.ledger.save()

    total_duration_ms = int((time.monotonic() - t0) * 1000)
    fix_duration_ms = max(0, total_duration_ms - scan_duration_ms)
    files_changed = _orchestrator_changed_files(result)
    commit_hash = _orchestrator_commit_hash(result)
    success = _orchestrator_success(result)
    summary = _orchestrator_summary(result)
    outcome = _orchestrator_outcome(result, success)

    engine.journal_writer.log(
        loop=loop_name,
        action="orchestrator-fix",
        category=entry.name,
        result="success" if success else "failure",
        files=files_changed,
        commit=commit_hash,
        error=None if success else summary,
        duration_ms=total_duration_ms,
    )
    results.append(
        LoopResult(
            success=success,
            action="orchestrator-fix",
            category=entry.name,
            files=files_changed,
            commit=commit_hash,
            error=None if success else summary,
            duration_ms=total_duration_ms,
        )
    )
    engine.ledger.record_convergence(
        loop_name,
        entry.name,
        issues=issues,
        snapshot_fingerprint=snap_fp,
        entry_module=getattr(entry, "module", None),
    )
    _store_cat_report(
        cat_reports,
        engine._make_cat_report(
            entry.name,
            trust_before,
            diff_before,
            loop_state,
            "ok" if success else "broken",
            summary[:120],
            outcome=outcome,
            issue_count=len(issues),
            issue_counts=issue_counts,
            deepening_reason=deepening_reason,
            yield_class=yc,
            new_fingerprint_count=new_count,
            repeated_fingerprint_count=repeated_count,
            resolved_fingerprint_count=resolved_count,
            execution_mode=execution_mode,
            short_circuit_used=should_short_circuit,
            scan_duration_ms=scan_duration_ms,
            fix_duration_ms=fix_duration_ms,
            total_duration_ms=total_duration_ms,
            files_changed=files_changed,
        ),
    )
    return engine.ledger.check_allowed(loop_name, entry.name)


def _reload_ledger_after_orchestrator(
    engine: Any,
    *,
    loop_name: str,
    consumed_budget_remaining: int,
) -> None:
    try:
        from .trust_persistence import load_persisted_state

        load_persisted_state(engine.ledger._state_file, engine.ledger._loops)
        loop_state = engine.ledger._loops.get(loop_name)
        if loop_state is not None:
            loop_state.budget_remaining = min(
                loop_state.budget_remaining,
                consumed_budget_remaining,
            )
        engine.ledger.save()
    except Exception as exc:  # noqa: BLE001 - reporting should not mask fix result.
        logger.warning("Unable to reload orchestrator trust state for %s: %s", loop_name, exc)


def _orchestrator_success(result: Any) -> bool:
    failed_dispatches = [
        item
        for item in getattr(result, "dispatched", [])
        if getattr(item, "status", "") != "success"
    ]
    return not getattr(result, "mechanical_failed", []) and not failed_dispatches


def _orchestrator_refunds_budget(result: Any) -> bool:
    if getattr(result, "mechanical_failed", []):
        return False
    failed_dispatches = [
        item
        for item in getattr(result, "dispatched", [])
        if getattr(item, "status", "") != "success"
    ]
    if failed_dispatches:
        return False
    successful_dispatches = [
        item
        for item in getattr(result, "dispatched", [])
        if getattr(item, "status", "") == "success"
    ]
    return not (
        getattr(result, "mechanical_applied", [])
        or successful_dispatches
    )


def _orchestrator_changed_files(result: Any) -> list[str]:
    files: list[str] = []
    for item in getattr(result, "mechanical_applied", []):
        files.extend(str(path) for path in getattr(item, "changed_files", []) or [])
    return sorted(set(files))


def _orchestrator_commit_hash(result: Any) -> str | None:
    for item in getattr(result, "mechanical_applied", []):
        commit = getattr(item, "commit", None)
        if commit:
            return str(commit)
    for item in getattr(result, "dispatched", []):
        commit = getattr(item, "commit_hash", None)
        if commit:
            return str(commit)
    return None


def _orchestrator_summary(result: Any) -> str:
    counts = getattr(result, "counts", {})
    if not isinstance(counts, dict):
        counts = {}
    return (
        "orchestrator: "
        f"{counts.get('mechanical_applied', 0)} applied, "
        f"{counts.get('mechanical_failed', 0)} failed, "
        f"{counts.get('deferred', 0)} deferred, "
        f"{counts.get('dispatched', 0)} dispatched, "
        f"{counts.get('enqueued', 0)} enqueued"
    )


def _orchestrator_outcome(result: Any, success: bool) -> str:
    if not success:
        return "verification-failed-reverted"
    if getattr(result, "mechanical_applied", []) or getattr(result, "dispatched", []):
        return "auto-fixed"
    if getattr(result, "design_gate_findings", []):
        return "blocked-needs-design"
    return "report-only"


def _record_orchestrator_route_failure(
    *,
    engine: Any,
    loop_name: str,
    loop_state: Any,
    entry: Any,
    issues: list[dict[str, Any]],
    issue_counts: dict[str, int],
    scan_duration_ms: int,
    trust_before: float,
    diff_before: int,
    deepening_reason: str,
    execution_mode: str,
    should_short_circuit: bool,
    yc: str,
    new_count: int,
    repeated_count: int,
    resolved_count: int,
    results: list[LoopResult],
    cat_reports: list[CategoryReport],
    t0: float,
    error: Exception,
) -> bool:
    message = f"orchestrator route failed: {error}"
    total_duration_ms = int((time.monotonic() - t0) * 1000)
    fix_duration_ms = max(0, total_duration_ms - scan_duration_ms)
    engine.ledger.record_failure(loop_name, entry.name)
    engine.journal_writer.log(
        loop=loop_name,
        action="orchestrator-fix",
        category=entry.name,
        result="failure",
        files=[],
        error=message,
        duration_ms=total_duration_ms,
    )
    results.append(
        LoopResult(
            success=False,
            action="orchestrator-fix",
            category=entry.name,
            error=message,
            duration_ms=total_duration_ms,
        )
    )
    _store_cat_report(
        cat_reports,
        engine._make_cat_report(
            entry.name,
            trust_before,
            diff_before,
            loop_state,
            "broken",
            message[:120],
            outcome="broken",
            issue_count=len(issues),
            issue_counts=issue_counts,
            deepening_reason=deepening_reason,
            yield_class=yc,
            new_fingerprint_count=new_count,
            repeated_fingerprint_count=repeated_count,
            resolved_fingerprint_count=resolved_count,
            execution_mode=execution_mode,
            short_circuit_used=should_short_circuit,
            scan_duration_ms=scan_duration_ms,
            fix_duration_ms=fix_duration_ms,
            total_duration_ms=total_duration_ms,
        ),
    )
    return engine.ledger.check_allowed(loop_name, entry.name)


def _resolve_execution_mode(
    diff_before: int,
    should_short_circuit: bool,
    forced_deep_requested: bool,
    engine: Any,
    entry: Any,
    entry_config: dict[str, Any],
    cat_state: Any,
    snap_fp: str,
) -> tuple[str, str]:
    """Determine execution_mode and deepening_reason."""
    execution_mode = "classify" if diff_before <= 0 else "deep"
    deepening_reason = "baseline"
    # ADR-412: hotspot-first deepening — categories with active hotspots
    # should always run deep scans to track hotspot evolution
    has_hotspots = bool(
        cat_state and getattr(cat_state, "hot_paths", None)
    )
    if should_short_circuit:
        execution_mode = "classify-shortcut"
        deepening_reason = "snapshot-unchanged"
    elif has_hotspots and diff_before > 0:
        execution_mode = "deep"
        deepening_reason = "hotspot-tracking"
    elif forced_deep_requested:
        deepening_reason = "forced-after-clean-loop"
    elif diff_before > 0 and engine._two_phase_enabled(entry.name, entry_config):
        last_snapshot = getattr(cat_state, "last_snapshot_fingerprint", "") if cat_state else ""
        deepening_reason = (
            "snapshot-changed" if snap_fp and last_snapshot and last_snapshot != snap_fp
            else "difficulty"
        )
    elif diff_before > 0:
        deepening_reason = "difficulty"
    return execution_mode, deepening_reason


def store_cat_report(cat_reports: list[CategoryReport], report: CategoryReport) -> None:
    """Store or replace a category report in the list."""
    for idx, existing in enumerate(cat_reports):
        if existing.name == report.name:
            cat_reports[idx] = report
            return
    cat_reports.append(report)


def _record_scan_failure(
    engine: Any, loop_name: str, entry: Any, cat_state: Any,
    loop_state: Any, scan_duration_ms: int,
    journal_error: str, result_error: str, error_summary: str,
    disable_reason: str,
    forced_deep_requested: bool, is_first_run: bool,
    trust_before: float, diff_before: int,
    deepening_reason: str, execution_mode: str, should_short_circuit: bool,
    results: list[LoopResult], cat_reports: list[CategoryReport],
    broken_categories: set[str], cycle_state: dict[str, Any],
) -> None:
    """Record a scan failure (exception or health=broken)."""
    broken_categories.add(entry.name)
    engine.journal_writer.log(
        loop=loop_name, action="scan", category=entry.name,
        result="failure", files=[], error=journal_error,
        duration_ms=scan_duration_ms,
    )
    engine.ledger.record_failure(loop_name, entry.name)
    if forced_deep_requested:
        engine.ledger.consume_forced_deep_scan(loop_name, entry.name)
    if is_first_run and cat_state and cat_state.enabled:
        engine._self_test_disable(cat_state, loop_state, entry.name, disable_reason)
        cycle_state["needs_save"] = True
    results.append(LoopResult(
        success=False, action="scan", category=entry.name,
        error=result_error, duration_ms=scan_duration_ms,
    ))
    store_cat_report(cat_reports, engine._make_cat_report(
        entry.name, trust_before, diff_before, loop_state,
        "broken", error_summary[:120], outcome="broken",
        deepening_reason=deepening_reason, execution_mode=execution_mode,
        short_circuit_used=should_short_circuit,
        scan_duration_ms=scan_duration_ms, total_duration_ms=scan_duration_ms,
    ))


def _run_scan_phase(
    engine: Any, loop_name: str, entry: Any,
    cat_state: Any, loop_state: Any,
    should_short_circuit: bool, classify_ctx: Any, ctx: Any,
    forced_deep_requested: bool, is_first_run: bool,
    trust_before: float, diff_before: int,
    deepening_reason: str, execution_mode: str,
    results: list[LoopResult], cat_reports: list[CategoryReport],
    broken_categories: set[str], cycle_state: dict[str, Any],
    t0: float,
) -> tuple[Any | None, int]:
    """Run the scan phase. Returns (scan_result, scan_duration_ms). scan_result is None on failure."""
    try:
        scan_ctx = classify_ctx if should_short_circuit else ctx
        scan_result = entry.module.scan(scan_ctx)
        scan_duration_ms = int((time.monotonic() - t0) * 1000)
        return scan_result, scan_duration_ms
    except Exception as exc:
        logger.warning("scan() failed for %s: %s", entry.name, exc)
        scan_duration_ms = int((time.monotonic() - t0) * 1000)
        _record_scan_failure(
            engine, loop_name, entry, cat_state, loop_state,
            scan_duration_ms,
            journal_error=str(exc),
            result_error=f"scan exception: {exc}",
            error_summary=str(exc),
            disable_reason="scan exception",
            forced_deep_requested=forced_deep_requested,
            is_first_run=is_first_run,
            trust_before=trust_before, diff_before=diff_before,
            deepening_reason=deepening_reason, execution_mode=execution_mode,
            should_short_circuit=should_short_circuit,
            results=results, cat_reports=cat_reports,
            broken_categories=broken_categories, cycle_state=cycle_state,
        )
        return None, scan_duration_ms


def _handle_broken_scan(
    engine: Any, loop_name: str, entry: Any,
    cat_state: Any, loop_state: Any, scan_result: Any,
    scan_duration_ms: int,
    forced_deep_requested: bool, is_first_run: bool,
    trust_before: float, diff_before: int,
    deepening_reason: str, execution_mode: str, should_short_circuit: bool,
    results: list[LoopResult], cat_reports: list[CategoryReport],
    broken_categories: set[str], cycle_state: dict[str, Any],
) -> None:
    """Handle a scan that returned health='broken'."""
    summary = getattr(scan_result, "summary", "")
    _record_scan_failure(
        engine, loop_name, entry, cat_state, loop_state,
        scan_duration_ms,
        journal_error=f"scan health: broken — {summary}",
        result_error="scan health: broken",
        error_summary=summary or "scan health: broken",
        disable_reason="health=broken",
        forced_deep_requested=forced_deep_requested,
        is_first_run=is_first_run,
        trust_before=trust_before, diff_before=diff_before,
        deepening_reason=deepening_reason, execution_mode=execution_mode,
        should_short_circuit=should_short_circuit,
        results=results, cat_reports=cat_reports,
        broken_categories=broken_categories, cycle_state=cycle_state,
    )


def _build_clean_cat_report(
    cs: Any,
    entry_name: str,
    trust_before: float,
    diff_before: int,
    status: str,
    action_summary: str,
    strategy_before: str,
    execution_mode: str,
    deepening_reason: str,
    yc: str,
    new_count: int,
    repeated_count: int,
    resolved_count: int,
    short_circuit_used: bool,
    scan_duration_ms: int,
) -> CategoryReport:
    """Build a CategoryReport for a clean (no-issues) scan."""
    return CategoryReport(
        name=entry_name,
        trust_before=trust_before,
        trust_after=cs.trust if cs else trust_before,
        difficulty_before=diff_before,
        difficulty_after=cs.difficulty if cs else diff_before,
        status=status,
        action_summary=action_summary,
        outcome="clean",
        strategy_after=cs.strategy if cs else "scan",
        self_repair_transition=(
            "recovered" if strategy_before == "self-repair" and (cs.strategy if cs else "scan") == "scan" else ""
        ),
        execution_mode=execution_mode,
        deepening_reason=deepening_reason,
        yield_class=yc,
        new_fingerprint_count=new_count,
        repeated_fingerprint_count=repeated_count,
        resolved_fingerprint_count=resolved_count,
        false_positive_rate=round(
            (
                (cs.false_positive_signal_count / cs.issue_cycles)
                if cs and getattr(cs, "issue_cycles", 0) > 0
                else 0.0
            ),
            3,
        ),
        self_repair_success_rate=round(
            (
                (cs.self_repair_successes / cs.self_repair_count)
                if cs and getattr(cs, "self_repair_count", 0) > 0
                else 0.0
            ),
            3,
        ),
        short_circuit_used=short_circuit_used,
        scan_duration_ms=scan_duration_ms,
        total_duration_ms=scan_duration_ms,
    )


def _handle_clean_entry(
    engine: Any,
    loop_name: str,
    entry: Any,
    loop_state: Any,
    scan_result: Any,
    scan_duration_ms: int,
    scan_health: str,
    snap_fp: str,
    should_short_circuit: bool,
    strategy_before: str,
    trust_before: float,
    diff_before: int,
    deepening_reason: str,
    execution_mode: str,
    yc: str,
    new_count: int,
    repeated_count: int,
    resolved_count: int,
    cat_reports: list[CategoryReport],
    no_coverage_categories: set[str] | None = None,
) -> None:
    """Handle a scan that found no issues (clean entry)."""
    # Detect vacuous clean: scanner reported 0 items at difficulty >= 1
    items_scanned = getattr(scan_result, "items_scanned", None)
    is_no_coverage = (
        diff_before >= 1
        and items_scanned is not None
        and items_scanned == 0
    )
    if is_no_coverage:
        # Even no-coverage is a successful scan — reset stale failures
        cs_nc = loop_state.categories.get(entry.name)
        if cs_nc:
            cs_nc.consecutive_failures = 0
        if no_coverage_categories is not None:
            no_coverage_categories.add(entry.name)
        engine.journal_writer.log(
            loop=loop_name, action="no-coverage", category=entry.name,
            result="success", files=[], duration_ms=scan_duration_ms,
        )
        store_cat_report(cat_reports, CategoryReport(
            name=entry.name,
            trust_before=trust_before,
            trust_after=trust_before,
            difficulty_before=diff_before,
            difficulty_after=diff_before,
            status="ok",
            action_summary=f"0 items scanned at d{diff_before}",
            outcome="no-coverage",
            execution_mode=execution_mode,
            deepening_reason=deepening_reason,
            yield_class=yc,
            new_fingerprint_count=new_count,
            repeated_fingerprint_count=repeated_count,
            resolved_fingerprint_count=resolved_count,
            short_circuit_used=should_short_circuit,
            scan_duration_ms=scan_duration_ms,
            total_duration_ms=scan_duration_ms,
        ))
        return

    # Clean scan = success: reset consecutive failures so stale failure
    # state from prior runs doesn't permanently suppress trust.
    cs = loop_state.categories.get(entry.name)
    if cs:
        cs.consecutive_failures = 0

    scan_summary = getattr(scan_result, "summary", "")
    if should_short_circuit and scan_health == "verified":
        engine.journal_writer.log(
            loop=loop_name, action="classify-scan", category=entry.name,
            result="success", files=[], duration_ms=scan_duration_ms,
        )
        engine.ledger.record_convergence(
            loop_name, entry.name, issues=[], snapshot_fingerprint=snap_fp,
        )
        store_cat_report(cat_reports, _build_clean_cat_report(
            cs, entry.name, trust_before, diff_before,
            "ok", "classify clean (snapshot unchanged)",
            strategy_before, execution_mode, deepening_reason,
            yc, new_count, repeated_count, resolved_count,
            True, scan_duration_ms,
        ))
        return

    engine.ledger.record_convergence(
        loop_name, entry.name, issues=[], snapshot_fingerprint=snap_fp,
    )
    cs = loop_state.categories.get(entry.name)
    status = "degraded" if scan_health == "degraded" else "ok"
    summary = "clean scan" if scan_health == "verified" else f"degraded: {scan_summary[:80]}"
    store_cat_report(cat_reports, _build_clean_cat_report(
        cs, entry.name, trust_before, diff_before,
        status, summary,
        strategy_before, execution_mode, deepening_reason,
        yc, new_count, repeated_count, resolved_count,
        should_short_circuit, scan_duration_ms,
    ))

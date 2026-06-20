"""Heal module for adaptive loop engine.

Detects failed, structurally idle, and trust-stuck categories.
Investigates root causes and applies structural fixes before re-enabling.

See ADR-256 and docs/plans/2026-03-07-ops-loops-heal-design.md
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
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from routine_orchestrator.ledger_view import JournalRecord
from .trust_ledger import TrustLedger

logger = logging.getLogger(__name__)

HealSeverity = Literal["critical", "warning", "info"]
HealKind = Literal["failed", "structurally_idle", "trust_stuck"]
HealOutcome = Literal["fixed", "skipped", "unresolved"]

# Detection thresholds
IDLE_MIN_CYCLES = 3
STUCK_MIN_CYCLES = 5
STUCK_ESCALATE_CYCLES = 10
STUCK_TRUST_THRESHOLD = 0.1

# Known error patterns: (regex, pattern_name, fixable, description)
KNOWN_PATTERNS: list[tuple[str, str, bool, str]] = [
    (r"FileNotFoundError.*?((?:state|logs)/\S+)", "missing_path", True, "Missing state/log path"),
    (r"No such file.*?((?:state|logs)/\S+)", "missing_path", True, "Missing state/log path"),
    (r"ModuleNotFoundError", "module_error", False, "Missing Python dependency"),
    (r"ImportError", "module_error", False, "Import failure"),
    (r"[Tt]imeout|TimeoutExpired", "timeout", False, "Execution timeout"),
]


@dataclass
class HealFinding:
    """A single detected problem in an adaptive loop category."""

    kind: HealKind
    severity: HealSeverity
    loop: str
    category: str | None  # None for loop-level findings (structurally_idle)
    message: str
    last_error: str | None = None
    context: dict = field(default_factory=dict)


@dataclass
class InvestigationResult:
    """Result of investigating a heal finding."""

    finding: HealFinding
    root_cause: str | None = None
    pattern: str = "unknown"  # missing_path, empty_data_dir, module_error, timeout, scan_empty, fix_blocked, scan_exception, unknown
    fixable: bool = False
    fix_action: str | None = None
    fix_path: str | None = None


@dataclass
class HealFixResult:
    """Result of attempting to fix a single finding."""

    finding: HealFinding
    outcome: HealOutcome
    investigation: InvestigationResult | None = None
    fix_description: str = ""
    verify_result: str = ""


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def heal_detect(
    ledger: TrustLedger,
    journal_entries: list[JournalRecord | dict] | None = None,
) -> list[HealFinding]:
    """Detect all heal-worthy problems across all loops.

    Returns a list of HealFinding sorted by severity (critical first).
    """
    findings: list[HealFinding] = []
    entries = journal_entries or []

    for loop_name, loop_state in ledger._loops.items():
        findings.extend(_detect_failed(loop_name, loop_state, entries))
        findings.extend(_detect_structurally_idle(loop_name, loop_state))
        findings.extend(_detect_trust_stuck(loop_name, loop_state))

    severity_order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: severity_order.get(f.severity, 3))
    return findings


def _detect_failed(
    loop_name: str, loop_state, entries: list,
) -> list[HealFinding]:
    """Detect categories with consecutive failures > 0."""
    findings = []
    # Build error lookup from journal
    last_errors: dict[str, str] = {}
    for e in reversed(entries):
        cat = e.category if hasattr(e, "category") else e.get("category", "")
        loop = e.loop if hasattr(e, "loop") else e.get("loop", "")
        error = e.error if hasattr(e, "error") else e.get("error")
        result = e.result if hasattr(e, "result") else e.get("result", "")
        if loop == loop_name and result == "failure" and error and cat not in last_errors:
            last_errors[cat] = error

    for cat_name, cs in loop_state.categories.items():
        if cs.consecutive_failures > 0:
            findings.append(HealFinding(
                kind="failed",
                severity="critical",
                loop=loop_name,
                category=cat_name,
                message=(
                    f"{cs.consecutive_failures} consecutive failure(s) "
                    f"(tier {cs.tier}, disable_count={cs.disable_count})"
                ),
                last_error=last_errors.get(cat_name),
                context={
                    "consecutive_failures": cs.consecutive_failures,
                    "disable_count": cs.disable_count,
                    "tier": cs.tier,
                },
            ))
    return findings


def _detect_structurally_idle(
    loop_name: str, loop_state,
) -> list[HealFinding]:
    """Detect loops where all categories have zero activity after enough cycles."""
    if loop_state.cycle_count < IDLE_MIN_CYCLES:
        return []
    # A loop with no categories cannot be structurally idle — it simply
    # has no registered commands yet (e.g. ledger built from config before
    # auto-command discovery).  `all()` on an empty iterable returns True,
    # which caused false-positive idle detection for every loop.
    if not loop_state.categories:
        return []
    all_idle = all(
        cs.success_count == 0 and cs.failure_count == 0 and cs.trust == 0.0
        for cs in loop_state.categories.values()
    )
    if not all_idle:
        return []
    return [HealFinding(
        kind="structurally_idle",
        severity="warning",
        loop=loop_name,
        category=None,
        message=(
            f"{loop_state.cycle_count} cycles, all categories at zero "
            f"(0 successes, 0 failures, 0.0 trust)"
        ),
        context={"cycle_count": loop_state.cycle_count},
    )]


def _detect_trust_stuck(
    loop_name: str, loop_state,
) -> list[HealFinding]:
    """Detect individual categories stuck at zero trust after many cycles."""
    if loop_state.cycle_count < STUCK_MIN_CYCLES:
        return []
    findings = []
    for cat_name, cs in loop_state.categories.items():
        if cs.trust < STUCK_TRUST_THRESHOLD and cs.success_count == 0:
            # Skip categories already caught as failed
            if cs.consecutive_failures > 0:
                continue
            severity: HealSeverity = (
                "warning" if loop_state.cycle_count >= STUCK_ESCALATE_CYCLES
                else "info"
            )
            findings.append(HealFinding(
                kind="trust_stuck",
                severity=severity,
                loop=loop_name,
                category=cat_name,
                message=(
                    f"trust={cs.trust:.2f} after {loop_state.cycle_count} cycles, "
                    f"0 successes (scan always empty or never ran)"
                ),
                context={
                    "cycle_count": loop_state.cycle_count,
                    "trust": cs.trust,
                },
            ))
    return findings


# ---------------------------------------------------------------------------
# Investigation
# ---------------------------------------------------------------------------

def investigate_finding(
    finding: HealFinding,
    entry: object | None = None,
    project_root: Path | None = None,
    journal_entries: list | None = None,
) -> InvestigationResult:
    """Investigate a finding to identify root cause and fixability."""
    project_root = project_root or Path.cwd()

    # For failed categories: match error against known patterns
    if finding.kind == "failed" and finding.last_error:
        for regex, pattern_name, fixable, desc in KNOWN_PATTERNS:
            match = re.search(regex, finding.last_error)
            if match:
                fix_path = match.group(1) if match.lastindex else None
                fix_action = None
                if pattern_name == "missing_path" and fix_path:
                    fix_action = f"Create missing directory: {fix_path}"
                return InvestigationResult(
                    finding=finding,
                    root_cause=f"{desc}: {fix_path or finding.last_error[:80]}",
                    pattern=pattern_name,
                    fixable=fixable,
                    fix_action=fix_action,
                    fix_path=fix_path,
                )
        return InvestigationResult(
            finding=finding,
            root_cause=f"Unknown error: {finding.last_error[:120]}",
            pattern="unknown",
            fixable=False,
        )

    # For structurally idle: report data pipeline issue
    if finding.kind == "structurally_idle":
        return InvestigationResult(
            finding=finding,
            root_cause=(
                f"Loop '{finding.loop}' has zero activity after "
                f"{finding.context.get('cycle_count', '?')} cycles — "
                f"scan() input data pipeline may be empty or disconnected"
            ),
            pattern="empty_data_dir",
            fixable=False,
        )

    # For trust-stuck: dry-run scan to see if pipeline works
    if finding.kind == "trust_stuck" and entry is not None:
        return _investigate_stuck_via_dry_scan(finding, entry, project_root)

    return InvestigationResult(finding=finding)


def _investigate_stuck_via_dry_scan(
    finding: HealFinding, entry: object, project_root: Path,
) -> InvestigationResult:
    """Run a dry scan to check if the command's pipeline is functional."""
    from src.lib.ops_protocol import OpsContext

    ctx = OpsContext(project_root=project_root, difficulty=0, dry_run=True)
    try:
        result = entry.module.scan(ctx)
        issues = getattr(result, "issues", [])
        if not issues:
            return InvestigationResult(
                finding=finding,
                root_cause="scan() returns empty — no issues to fix at current difficulty",
                pattern="scan_empty",
                fixable=False,
            )
        return InvestigationResult(
            finding=finding,
            root_cause=f"scan() found {len(issues)} issues but fix() never ran successfully",
            pattern="fix_blocked",
            fixable=True,
            fix_action="Reset failure counters and re-run fix()",
        )
    except Exception as exc:
        return InvestigationResult(
            finding=finding,
            root_cause=f"scan() threw exception: {exc}",
            pattern="scan_exception",
            fixable=False,
        )


# ---------------------------------------------------------------------------
# Fix pipeline
# ---------------------------------------------------------------------------

def heal_fix(
    findings: list[HealFinding],
    ledger: TrustLedger,
    registry: dict,  # command_name -> AutoCommandEntry
    project_root: Path,
    journal_entries: list,
    force: bool = False,
) -> list[HealFixResult]:
    """Attempt to fix each finding: investigate -> structural fix -> verify -> re-enable.

    Args:
        findings: Output from heal_detect().
        ledger: Trust ledger for state mutations.
        registry: Auto-command registry from discover_auto_commands().
        project_root: Project root path.
        journal_entries: Recent ledger-derived history entries for investigation.
        force: If True, promote even categories with disable_count >= 1.
    """
    results = []

    for finding in findings:
        entry = registry.get(finding.category) if finding.category else None

        # Gate: skip disabled categories unless --force
        if finding.category and not force:
            try:
                ls = ledger.get_loop_state(finding.loop)
                cs = ls.categories.get(finding.category)
                if cs and cs.disable_count >= 1:
                    results.append(HealFixResult(
                        finding=finding,
                        outcome="skipped",
                        fix_description=f"disable_count={cs.disable_count}, use --force to override",
                    ))
                    continue
            except KeyError:
                pass

        # 1. Investigate
        investigation = investigate_finding(
            finding, entry=entry, project_root=project_root,
            journal_entries=journal_entries,
        )

        # 2. If not fixable and not a missing_path, report as unresolved
        if not investigation.fixable and investigation.pattern != "missing_path":
            results.append(HealFixResult(
                finding=finding,
                outcome="unresolved",
                investigation=investigation,
                fix_description=f"Root cause: {investigation.root_cause}",
            ))
            continue

        # 3. Attempt structural fix
        fix_desc = _apply_structural_fix(investigation, project_root)

        # 4. Verify via dry-run scan
        verified = _verify_after_fix(entry, project_root) if entry else True

        if not verified:
            results.append(HealFixResult(
                finding=finding,
                outcome="unresolved",
                investigation=investigation,
                fix_description=fix_desc,
                verify_result="scan() still fails after fix",
            ))
            continue

        # 5. Re-enable
        if finding.category:
            _reset_category(ledger, finding.loop, finding.category, force)

        results.append(HealFixResult(
            finding=finding,
            outcome="fixed",
            investigation=investigation,
            fix_description=fix_desc,
            verify_result="verified",
        ))

    return results


def _apply_structural_fix(
    investigation: InvestigationResult, project_root: Path,
) -> str:
    """Apply a structural fix based on investigation pattern. Returns description."""
    if investigation.pattern == "missing_path" and investigation.fix_path:
        full_path = project_root / investigation.fix_path
        full_path.mkdir(parents=True, exist_ok=True)
        return f"Created missing directory: {investigation.fix_path}"
    return investigation.fix_action or "No structural fix applied"


def _verify_after_fix(entry: object, project_root: Path) -> bool:
    """Run a dry scan to verify the structural fix worked."""
    from src.lib.ops_protocol import OpsContext

    ctx = OpsContext(project_root=project_root, difficulty=0, dry_run=True)
    try:
        entry.module.scan(ctx)
        return True  # scan completed without exception = pipeline works
    except Exception:
        return False


def _reset_category(
    ledger: TrustLedger, loop: str, category: str, force: bool,
) -> None:
    """Reset failure counters for a category. Promote if force=True."""
    try:
        ls = ledger.get_loop_state(loop)
        cs = ls.categories.get(category)
        if not cs:
            return
        if force and cs.disable_count >= 1:
            ledger.promote_category(loop, category)
        else:
            cs.consecutive_failures = 0
            cs.enabled = True
            ledger.save()
    except KeyError:
        pass


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def format_heal_report(findings: list[HealFinding]) -> str:
    """Format findings into a human-readable report string."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not findings:
        return f"=== Heal Findings ({today}) ===\n\nAll loops healthy. No issues detected."

    lines = [f"=== Heal Findings ({today}) ===", ""]

    failed = [f for f in findings if f.kind == "failed"]
    idle = [f for f in findings if f.kind == "structurally_idle"]
    stuck = [f for f in findings if f.kind == "trust_stuck"]

    if failed:
        lines.append(f"CRITICAL: {len(failed)} failed categor{'y' if len(failed) == 1 else 'ies'}")
        for f in failed:
            lines.append(f"  - {f.loop}/{f.category}: {f.message}")
            if f.last_error:
                lines.append(f"    Last error: \"{f.last_error[:120]}\"")
        lines.append("")

    if idle:
        lines.append(f"WARNING: {len(idle)} structurally idle loop{'s' if len(idle) != 1 else ''}")
        for f in idle:
            lines.append(f"  - {f.loop}: {f.message}")
        lines.append("")

    if stuck:
        lines.append(f"WARNING: {len(stuck)} trust-stuck categor{'y' if len(stuck) == 1 else 'ies'}")
        for f in stuck:
            lines.append(f"  - {f.loop}/{f.category}: {f.message}")
        lines.append("")

    lines.append("Run `/routines heal --fix` to attempt repairs.")
    return "\n".join(lines)


def format_heal_fix_report(results: list[HealFixResult]) -> str:
    """Format fix results into a human-readable report."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not results:
        return f"=== Heal Results ({today}) ===\n\nNo findings to fix."

    lines = [f"=== Heal Results ({today}) ===", ""]

    fixed = [r for r in results if r.outcome == "fixed"]
    skipped = [r for r in results if r.outcome == "skipped"]
    unresolved = [r for r in results if r.outcome == "unresolved"]

    if fixed:
        lines.append(f"FIXED: {len(fixed)} categor{'y' if len(fixed) == 1 else 'ies'}")
        for r in fixed:
            cat_label = f"{r.finding.loop}/{r.finding.category}" if r.finding.category else r.finding.loop
            lines.append(f"  - {cat_label}")
            lines.append(f"    Fix: {r.fix_description}")
            lines.append(f"    Verify: {r.verify_result}")
        lines.append("")

    if skipped:
        lines.append(f"SKIPPED: {len(skipped)} categor{'y' if len(skipped) == 1 else 'ies'} (use --force)")
        for r in skipped:
            cat_label = f"{r.finding.loop}/{r.finding.category}" if r.finding.category else r.finding.loop
            lines.append(f"  - {cat_label}: {r.fix_description}")
        lines.append("")

    if unresolved:
        lines.append(f"UNRESOLVED: {len(unresolved)} categor{'y' if len(unresolved) == 1 else 'ies'}")
        for r in unresolved:
            cat_label = f"{r.finding.loop}/{r.finding.category}" if r.finding.category else r.finding.loop
            lines.append(f"  - {cat_label}")
            lines.append(f"    {r.fix_description}")
        lines.append("")

    return "\n".join(lines)

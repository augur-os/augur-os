"""Helper methods for adaptive loop cycle execution.

This module contains utility functions and static methods used by the
AdaptiveLoopEngine during cycle execution, including issue normalization,
yield classification, fingerprint tracking, difficulty management,
self-repair plan generation, and report persistence.
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
import hashlib
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Two-phase snapshot keys for classify/deep execution mode switching
TWO_PHASE_SNAPSHOT_KEYS: dict[str, tuple[str, ...]] = {
    "auto-block-wiring": ("api_routes", "page_routes", "skill_roots", "git_dirty_files"),
    "auto-code-review": ("git_dirty_files",),
    "auto-dead-api": ("api_routes", "api_route_paths", "page_routes", "git_dirty_files"),
    "auto-dead-ui": ("api_routes", "page_routes", "skill_roots", "git_dirty_files"),
    "auto-page-mounts": ("skill_roots", "git_dirty_files"),
    "auto-stale-refs": ("page_routes", "skill_roots", "git_dirty_files"),
    "auto-stale-actions": ("page_routes", "skill_roots", "git_dirty_files"),
    "auto-stale-routes": ("api_routes", "api_route_paths", "git_dirty_files"),
    "auto-test-api": ("api_routes", "api_route_paths", "git_dirty_files"),
    "auto-test-coverage": ("git_dirty_files",),
    "auto-test-pages": ("page_routes", "git_dirty_files"),
}

CLEAN_LOOP_ESCALATION_LIMIT = 2


def normalize_issue(category_name: str, issue: object) -> dict[str, Any]:
    """Backfill Phase 1 issue semantics for legacy categories."""
    from src.lib.ops_protocol import issue_fingerprint

    if isinstance(issue, dict):
        normalized = dict(issue)
    else:
        normalized = {"detail": str(issue)}

    detail = str(
        normalized.get("detail")
        or normalized.get("summary")
        or normalized.get("message")
        or normalized.get("error")
        or normalized.get("action")
        or ""
    )
    path = str(
        normalized.get("path")
        or normalized.get("file")
        or normalized.get("route")
        or ""
    )
    kind = str(normalized.get("kind") or "actionable")
    normalized["kind"] = kind
    normalized.setdefault("root_cause_type", "unknown")
    normalized.setdefault("fixability", "unknown")
    normalized.setdefault(
        "fingerprint",
        issue_fingerprint(
            category=category_name,
            kind=kind,
            path=path,
            detail=detail,
        ),
    )
    return normalized


def count_issue_kinds(issues: list[dict[str, Any]]) -> dict[str, int]:
    """Count issues by kind (actionable, maintenance, environment, etc.)."""
    counts = Counter(str(issue.get("kind") or "actionable") for issue in issues)
    return {
        "actionable": counts.get("actionable", 0),
        "maintenance": counts.get("maintenance", 0),
        "environment": counts.get("environment", 0),
        "scanner-defect": counts.get("scanner-defect", 0),
        "manual": counts.get("manual", 0),
        "broken": counts.get("broken", 0),
    }


def issue_fingerprint_sets(issues: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    """Extract actionable and scanner-defect fingerprint sets from issues."""
    actionable = {
        str(issue.get("fingerprint", ""))
        for issue in issues
        if str(issue.get("kind", "actionable")) == "actionable"
        and str(issue.get("fingerprint", ""))
    }
    scanner = {
        str(issue.get("fingerprint", ""))
        for issue in issues
        if str(issue.get("kind", "")) == "scanner-defect"
        and str(issue.get("fingerprint", ""))
    }
    return actionable, scanner


def yield_class(
    execution_mode: str,
    issues: list[dict[str, Any]],
    issue_counts: dict[str, int],
    previous_actionable: set[str],
    current_actionable: set[str],
    current_scanner: set[str],
) -> tuple[str, int, int, int]:
    """Classify the yield of a scan based on issue fingerprint changes."""
    new_actionable = current_actionable - previous_actionable
    repeated_actionable = current_actionable & previous_actionable
    resolved_actionable = previous_actionable - current_actionable
    if not issues:
        if execution_mode.startswith("classify"):
            return ("classify", 0, 0, len(resolved_actionable))
        return ("clean", 0, 0, len(resolved_actionable))
    if (
        execution_mode.startswith("classify")
        and not previous_actionable
        and not current_scanner
    ):
        return ("classify", len(new_actionable), 0, 0)
    if current_scanner and not current_actionable:
        return (
            "scanner-defect-only",
            0,
            0,
            len(resolved_actionable),
        )
    if issue_counts.get("maintenance", 0) > 0 and issue_counts.get("actionable", 0) == 0:
        return ("maintenance-only", 0, 0, len(resolved_actionable))
    if new_actionable:
        return (
            "new-findings",
            len(new_actionable),
            len(repeated_actionable),
            len(resolved_actionable),
        )
    if resolved_actionable and repeated_actionable:
        return (
            "reduced-findings",
            len(new_actionable),
            len(repeated_actionable),
            len(resolved_actionable),
        )
    if repeated_actionable:
        return (
            "repeat-findings",
            len(new_actionable),
            len(repeated_actionable),
            len(resolved_actionable),
        )
    return (
        "mixed-findings",
        len(new_actionable),
        len(repeated_actionable),
        len(resolved_actionable),
    )


# ---------------------------------------------------------------------------
# ADR-412 Phase 3: Hotspot computation
# ---------------------------------------------------------------------------

_MAX_HOT_PATHS = 5
_MAX_HOT_PATTERNS = 5
_HOT_PATH_MIN_COUNT = 2


def compute_hotspots(
    issues: list[dict[str, Any]],
) -> tuple[list[str], list[str], str]:
    """Compute hotspots from a set of issues (ADR-412 Phase 3).

    Returns (hot_paths, hot_patterns, dominant_root_cause).
    - hot_paths: Top directories/files with the most recurring issues.
    - hot_patterns: Top recurring detail pattern clusters.
    - dominant_root_cause: Most common root_cause_type.
    """
    path_counts: Counter[str] = Counter()
    pattern_counts: Counter[str] = Counter()
    root_cause_counts: Counter[str] = Counter()

    for issue in issues:
        kind = str(issue.get("kind", "actionable"))
        if kind not in ("actionable", "broken", "manual"):
            continue

        # Track path hotspots — use parent directory for clustering
        path = str(issue.get("path") or issue.get("file") or "")
        if path:
            # Cluster by parent dir (or top-level file for shallow paths)
            parts = path.replace("\\", "/").split("/")
            if len(parts) >= 2:
                cluster_key = "/".join(parts[:2])
            else:
                cluster_key = path
            path_counts[cluster_key] += 1

        # Track pattern clusters — normalize detail to first 60 chars
        detail = str(issue.get("detail") or issue.get("message") or "")
        if detail:
            # Normalize: lowercase, collapse whitespace, truncate
            normalized = " ".join(detail.lower().split())[:60]
            pattern_counts[normalized] += 1

        # Track root cause distribution
        rct = str(issue.get("root_cause_type", "unknown"))
        if rct and rct != "unknown":
            root_cause_counts[rct] += 1

    hot_paths = [
        path for path, count in path_counts.most_common(_MAX_HOT_PATHS)
        if count >= _HOT_PATH_MIN_COUNT
    ]
    hot_patterns = [
        pattern for pattern, count in pattern_counts.most_common(_MAX_HOT_PATTERNS)
        if count >= _HOT_PATH_MIN_COUNT
    ]
    dominant_root_cause = root_cause_counts.most_common(1)[0][0] if root_cause_counts else ""

    return hot_paths, hot_patterns, dominant_root_cause


def update_category_hotspots(
    cat_state: Any,
    issues: list[dict[str, Any]],
) -> None:
    """Update a CategoryState's hotspot fields from current issues (ADR-412)."""
    if not issues:
        # Decay hotspots when clean
        if hasattr(cat_state, "hot_paths"):
            cat_state.hot_paths = cat_state.hot_paths[:3]  # Shrink, don't wipe
        if hasattr(cat_state, "hot_patterns"):
            cat_state.hot_patterns = cat_state.hot_patterns[:3]
        return

    hot_paths, hot_patterns, dominant_root_cause = compute_hotspots(issues)
    if hasattr(cat_state, "hot_paths"):
        cat_state.hot_paths = hot_paths
    if hasattr(cat_state, "hot_patterns"):
        cat_state.hot_patterns = hot_patterns
    if hasattr(cat_state, "dominant_root_cause"):
        cat_state.dominant_root_cause = dominant_root_cause


def dependency_invalidations(config: dict[str, Any]) -> dict[str, set[str]]:
    """Build dependency invalidation map from config."""
    config_map = config.get("dependencies", {})
    invalidations: dict[str, set[str]] = {
        "auto-skill-md": {"reindex-project", "auto-rag-reindex"},
        "auto-markdowns": {"auto-rag-reindex"},
    }
    if isinstance(config_map, dict):
        for source, payload in config_map.items():
            if not isinstance(payload, dict):
                continue
            targets = payload.get("invalidates", [])
            if isinstance(targets, list):
                invalidations.setdefault(str(source), set()).update(
                    str(target) for target in targets
                )
    return invalidations


def two_phase_enabled(entry_name: str, entry_config: dict[str, Any]) -> bool:
    """Check if two-phase (classify/deep) execution is enabled for an entry."""
    mode = str(entry_config.get("execution_mode", "")).strip().lower()
    if mode == "two-phase":
        return True
    if mode in {"deep-only", "single-phase"}:
        return False
    return entry_name in TWO_PHASE_SNAPSHOT_KEYS


def snapshot_fingerprint(
    entry_name: str,
    shared_snapshot: dict[str, Any],
) -> str:
    """Compute a fingerprint of the shared snapshot for an entry."""
    if not shared_snapshot:
        return ""
    keys = TWO_PHASE_SNAPSHOT_KEYS.get(entry_name)
    if not keys:
        return ""
    payload = {key: shared_snapshot.get(key) for key in keys}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(encoded.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def should_short_circuit_classify(
    cat_state: Any,
    entry_name: str,
    entry_config: dict[str, Any],
    difficulty: int,
    snap_fingerprint: str,
) -> bool:
    """Determine if a classify scan can be short-circuited."""
    if not cat_state:
        return False
    if difficulty <= 0:
        return False
    if cat_state.strategy != "scan":
        return False
    if not two_phase_enabled(entry_name, entry_config):
        return False
    if not snap_fingerprint:
        return False
    if getattr(cat_state, "force_deep_runs_remaining", 0) > 0:
        return False
    if cat_state.consecutive_clean_scans <= 0:
        return False
    if cat_state.last_actionable_fingerprints or cat_state.last_scanner_defect_fingerprints:
        return False
    # ADR-412: active hotspots require a deep scan to track evolution
    if getattr(cat_state, "hot_paths", None):
        return False
    return cat_state.last_snapshot_fingerprint == snap_fingerprint


def entry_max_difficulty(entry: Any) -> int:
    """Get the maximum difficulty level supported by an entry's DIFFICULTY_SPEC."""
    spec = getattr(getattr(entry, "module", None), "DIFFICULTY_SPEC", None)
    if not isinstance(spec, dict) or not spec:
        return 0
    levels = [level for level in spec.keys() if isinstance(level, int)]
    return max(levels, default=0)


def difficulty_label(entry: Any, level: int) -> str:
    """Get the human-readable label for a difficulty level."""
    spec = getattr(getattr(entry, "module", None), "DIFFICULTY_SPEC", None)
    if not isinstance(spec, dict):
        return ""
    label = spec.get(level)
    return str(label).strip() if isinstance(label, str) else ""


def expansion_targets(entry: Any) -> list[dict[str, Any]]:
    """Return clean-loop family expansion targets declared by a category."""
    targets: list[dict[str, Any]] = []
    raw_targets = getattr(getattr(entry, "module", None), "EXPANSION_TARGETS", None)
    if not isinstance(raw_targets, list):
        raw_targets = []
    for raw in raw_targets:
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("category", "")).strip()
        if not category:
            continue
        try:
            min_clean_streak = max(1, int(raw.get("min_clean_streak", 2)))
        except (TypeError, ValueError):
            min_clean_streak = 2
        try:
            difficulty_val = max(1, int(raw.get("difficulty", 1)))
        except (TypeError, ValueError):
            difficulty_val = 1
        reason = str(raw.get("reason", "")).strip()
        targets.append(
            {
                "category": category,
                "difficulty": difficulty_val,
                "min_clean_streak": min_clean_streak,
                "reason": reason,
            }
        )
    return targets


def candidate_test_files(entry: Any) -> list[str]:
    """Find candidate test files for an entry's module."""
    plugin_root = getattr(entry, "plugin_root", None)
    module_path_str = getattr(getattr(entry, "module", None), "__file__", "")
    module_stem = Path(module_path_str).stem if module_path_str else entry.name.replace("-", "_")
    category_slug = entry.name.replace("-", "_")

    if not plugin_root:
        return []

    root = Path(plugin_root)
    if not root.exists():
        return []

    matches: list[str] = []
    for path in root.rglob("test*.py"):
        name = path.name
        if module_stem in name or category_slug in name:
            matches.append(str(path))
    if matches:
        return sorted(set(matches))[:8]

    fallback = [str(path) for path in root.rglob("test*.py")]
    return sorted(fallback)[:5]


def _to_relative_path(abs_path: str) -> str:
    """Convert absolute module path to relative path from project root."""
    if not abs_path:
        return ""
    try:
        path = Path(abs_path)
        # Try to make it relative to the current working directory or project root
        # Most of the time this will be an absolute path like /path/to/project/skills/...
        # We want to extract just the skills/... part
        parts = path.parts
        if "skills" in parts:
            idx = parts.index("skills")
            return str(Path(*parts[idx:]))
        # Fallback: return as-is if we can't find a relative form
        return str(path)
    except (ValueError, AttributeError):
        return abs_path


def write_self_repair_plan(
    adaptive_dir: Path,
    loop_name: str,
    entry: Any,
    issues: list[dict[str, Any]],
    summary: str,
    ledger: Any,
    journal_reader: Any,
) -> str:
    """Write a self-repair plan JSON file for a stagnant category."""
    plans_dir = adaptive_dir / "self_repair"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plans_dir / f"{loop_name}--{entry.name}.json"
    state = ledger.get_loop_state(loop_name).categories.get(entry.name)

    actionable = [
        {
            "fingerprint": issue.get("fingerprint", ""),
            "detail": issue.get("detail") or issue.get("message") or issue.get("action") or "",
            "path": issue.get("path") or issue.get("file") or "",
        }
        for issue in issues
        if issue.get("kind") == "actionable"
    ][:10]
    scanner_defects = [
        {
            "fingerprint": issue.get("fingerprint", ""),
            "detail": issue.get("detail") or issue.get("message") or issue.get("action") or "",
            "path": issue.get("path") or issue.get("file") or "",
        }
        for issue in issues
        if issue.get("kind") == "scanner-defect"
    ][:10]

    # Get recent failures
    entries = journal_reader.filter(loop=loop_name, category=entry.name, result="failure")
    recent = entries[-5:]
    recent_failures = [
        {
            "timestamp": e.timestamp,
            "action": e.action,
            "error": e.error or "",
        }
        for e in recent
    ]

    plan = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "loop": loop_name,
        "category": entry.name,
        "strategy": "self-repair",
        "summary": summary,
        "module_path": _to_relative_path(getattr(getattr(entry, "module", None), "__file__", "")),
        "plugin_root": str(getattr(entry, "plugin_root", "")),
        "candidate_test_files": candidate_test_files(entry),
        "actionable_fingerprints": state.last_actionable_fingerprints if state else [],
        "scanner_defect_fingerprints": state.last_scanner_defect_fingerprints if state else [],
        "issue_decay_streak": state.issue_decay_streak if state else 0,
        "stagnation_streak": state.stagnation_streak if state else 0,
        "self_repair_count": state.self_repair_count if state else 0,
        "recent_failures": recent_failures,
        "latest_loop_report": str(adaptive_dir / "reports" / f"{loop_name}-latest.json"),
        "recommended_focus": (
            "repair scanner logic and regression tests"
            if scanner_defects
            else "inspect recurring actionable fingerprints for stale heuristics"
        ),
        "actionable_examples": actionable,
        "scanner_defect_examples": scanner_defects,
    }
    plan_path.write_text(json.dumps(plan, indent=2))
    return str(plan_path)


def generate_next_actions(
    report: Any, loop_state: object
) -> list[str]:
    """Compute actionable next steps from cycle results and trust state."""
    from .trust_ledger import (
        DIFFICULTY_ESCALATION_THRESHOLD,
        MAX_DIFFICULTY,
    )

    actions: list[str] = []
    cats = getattr(loop_state, "categories", {})

    # Report-only categories need manual fixes
    for c in report.categories:
        if c.outcome == "report-only" and (c.manual_count > 0 or c.actionable_count > 0):
            actions.append(
                f"Fix {max(c.manual_count, c.actionable_count)} issue(s) in {c.name} (manual)"
            )

    for c in report.categories:
        if c.scanner_defect_count > 0:
            actions.append(f"Repair scanner logic for {c.name}")
        elif c.execution_mode == "deep" and c.yield_class == "repeat-findings":
            actions.append(f"Re-scope {c.name}: deep scan repeated old findings with no decay")
        elif c.execution_mode == "deep" and c.yield_class == "clean" and c.deepening_reason == "forced-after-clean-loop":
            actions.append(f"Keep {c.name} at current depth only if another forced deep stays low-yield")

    for c in report.categories:
        if c.strategy_after == "self-repair":
            if c.self_repair_plan:
                actions.append(f"Enter self-repair mode for {c.name}: {c.self_repair_plan}")
            else:
                actions.append(f"Enter self-repair mode for {c.name}")

    # Broken categories need investigation
    for c in report.categories:
        if c.outcome == "broken":
            actions.append(f"Investigate broken scanner: {c.name}")

    # Categories close to difficulty promotion
    for name, cs in cats.items():
        if not cs.enabled:
            continue
        remaining = DIFFICULTY_ESCALATION_THRESHOLD - (
            cs.consecutive_successes % DIFFICULTY_ESCALATION_THRESHOLD
        )
        if (
            cs.difficulty < MAX_DIFFICULTY
            and 0 < remaining <= 2
            and cs.consecutive_successes > 0
        ):
            actions.append(
                f"Promote {name} d{cs.difficulty}->d{cs.difficulty + 1} "
                f"({remaining} more success(es))"
            )

    # Disabled categories needing attention
    for name, cs in cats.items():
        if not cs.enabled and cs.disable_count > 0:
            actions.append(
                f"Re-enable {name} (disabled {cs.disable_count}x, "
                f"run /routines promote)"
            )

    # Budget exhausted
    budget_remaining = getattr(loop_state, "budget_remaining", 0)
    if budget_remaining == 0:
        actions.append("Increase budget (0 remaining)")

    for note in report.clean_escalations:
        actions.append(note)

    return actions


def save_cycle_report(
    adaptive_dir: Path,
    report: Any,
    loop_state: object,
    shared_snapshot: dict[str, Any] | None = None,
) -> None:
    """Persist a structured JSON report for dashboard API consumption."""
    from .trust_ledger import MAX_DIFFICULTY

    reports_dir = adaptive_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Compute per-loop difficulty as max across enabled categories
    cats = getattr(loop_state, "categories", {})
    enabled_diffs = [
        cs.difficulty for cs in cats.values() if cs.enabled
    ]
    loop_difficulty = max(enabled_diffs) if enabled_diffs else 0

    # Aggregate cycle summary
    clean = sum(1 for c in report.categories if c.outcome == "clean")
    auto_fixed = sum(1 for c in report.categories if c.outcome == "auto-fixed")
    manual = sum(c.manual_count for c in report.categories)
    broken = sum(1 for c in report.categories if c.outcome == "broken")
    total_issues = sum(c.issue_count for c in report.categories)
    actionable = sum(c.actionable_count for c in report.categories)
    maintenance = sum(c.maintenance_count for c in report.categories)
    environment = sum(c.environment_count for c in report.categories)
    scanner_defects = sum(c.scanner_defect_count for c in report.categories)
    manual_issues = sum(c.manual_count for c in report.categories)
    classify_categories = sum(
        1 for c in report.categories if c.execution_mode.startswith("classify")
    )
    classify_shortcuts = sum(1 for c in report.categories if c.short_circuit_used)
    deep_categories = sum(1 for c in report.categories if c.execution_mode == "deep")
    deep_new_findings = sum(
        1 for c in report.categories if c.execution_mode == "deep" and c.yield_class == "new-findings"
    )
    deep_repeat_findings = sum(
        1 for c in report.categories if c.execution_mode == "deep" and c.yield_class == "repeat-findings"
    )
    deep_reduced_findings = sum(
        1 for c in report.categories if c.execution_mode == "deep" and c.yield_class == "reduced-findings"
    )
    deep_low_yield = sum(
        1 for c in report.categories if c.execution_mode == "deep" and c.yield_class in {"clean", "repeat-findings", "maintenance-only"}
    )
    family_expansions = sum(
        1 for note in report.clean_escalations if note.startswith("Expanded from ")
    )
    dormant_enables = sum(
        1 for note in report.clean_escalations if note.startswith("Enabled dormant category ")
    )
    difficulty_escalations = sum(
        1 for note in report.clean_escalations if note.startswith("Raised ")
    )
    issue_decay_categories = sum(1 for c in report.categories if c.resolved_fingerprint_count > 0)
    false_positive_signals = sum(c.scanner_defect_count for c in report.categories)
    self_repair_entered = sum(1 for c in report.categories if c.self_repair_transition == "entered")
    self_repair_recovered = sum(1 for c in report.categories if c.self_repair_transition == "recovered")
    scan_duration_total = sum(c.scan_duration_ms for c in report.categories)
    fix_duration_total = sum(c.fix_duration_ms for c in report.categories)
    category_duration_total = sum(c.total_duration_ms for c in report.categories)

    next_actions = generate_next_actions(report, loop_state)
    snapshot = shared_snapshot or {}
    snapshot_summary = {
        "enabled": bool(snapshot),
        "version": snapshot.get("version"),
        "skill_count": snapshot.get("skill_count", 0),
        "api_route_count": snapshot.get("api_route_count", 0),
        "page_count": snapshot.get("page_count", 0),
        "git_dirty_file_count": len(snapshot.get("git_dirty_files", [])),
        "next_dev_lock_present": bool(
            snapshot.get("runtime", {}).get("next_dev_lock_present", False)
        ),
    }

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cycle_count": getattr(loop_state, "cycle_count", 0),
        "difficulty": {
            "current": loop_difficulty,
            "max": MAX_DIFFICULTY,
            "label": f"d{loop_difficulty} of d{MAX_DIFFICULTY}",
        },
        "cycle_summary": {
            "total_issues": total_issues,
            "actionable_issues": actionable,
            "maintenance_issues": maintenance,
            "environment_issues": environment,
            "scanner_defect_issues": scanner_defects,
            "manual_issues": manual_issues,
            "auto_fixed": auto_fixed,
            "manual_followup": manual,
            "broken": broken,
            "clean": clean,
            "categories_ran": len(report.categories),
            "classify_categories": classify_categories,
            "classify_shortcuts": classify_shortcuts,
            "deep_categories": deep_categories,
            "deep_scans_with_new_findings": deep_new_findings,
            "deep_scans_with_repeat_findings": deep_repeat_findings,
            "deep_scans_with_reduced_findings": deep_reduced_findings,
            "deep_scans_low_yield": deep_low_yield,
            "family_expansions": family_expansions,
            "dormant_categories_enabled": dormant_enables,
            "difficulty_escalations": difficulty_escalations,
            "issue_decay_categories": issue_decay_categories,
            "false_positive_signals": false_positive_signals,
            "self_repair_entered": self_repair_entered,
            "self_repair_recovered": self_repair_recovered,
            "scan_duration_ms_total": scan_duration_total,
            "fix_duration_ms_total": fix_duration_total,
            "category_duration_ms_total": category_duration_total,
            "clean_loop_streak": getattr(loop_state, "consecutive_clean_cycles", 0),
        },
        "categories": [
            {
                "name": c.name,
                "outcome": c.outcome,
                "issue_count": c.issue_count,
                "actionable_count": c.actionable_count,
                "maintenance_count": c.maintenance_count,
                "environment_count": c.environment_count,
                "scanner_defect_count": c.scanner_defect_count,
                "manual_count": c.manual_count,
                "strategy": c.strategy_after,
                "self_repair_plan": c.self_repair_plan,
                "self_repair_transition": c.self_repair_transition,
                "files_changed": c.files_changed[:10],  # Cap for JSON size
                "trust_before": round(c.trust_before, 3),
                "trust_after": round(c.trust_after, 3),
                "difficulty": c.difficulty_after,
                "status": c.status,
                "action_summary": c.action_summary,
                "execution_mode": c.execution_mode,
                "deepening_reason": c.deepening_reason,
                "yield_class": c.yield_class,
                "new_fingerprint_count": c.new_fingerprint_count,
                "repeated_fingerprint_count": c.repeated_fingerprint_count,
                "resolved_fingerprint_count": c.resolved_fingerprint_count,
                "false_positive_rate": c.false_positive_rate,
                "self_repair_success_rate": c.self_repair_success_rate,
                "short_circuit_used": c.short_circuit_used,
                "scan_duration_ms": c.scan_duration_ms,
                "fix_duration_ms": c.fix_duration_ms,
                "total_duration_ms": c.total_duration_ms,
                "hot_paths": c.hot_paths,
                "hot_patterns": c.hot_patterns,
                "dominant_root_cause": c.dominant_root_cause,
            }
            for c in report.categories
        ],
        "next_actions": next_actions,
        "clean_escalations": report.clean_escalations,
        "duration_ms": report.duration_ms,
        "snapshot": snapshot_summary,
    }

    report_path = reports_dir / f"{report.loop_name}-latest.json"
    try:
        report_path.write_text(json.dumps(data, indent=2))
    except OSError:
        return

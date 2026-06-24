"""Trust ledger diagnostics.

Analyzes all loops for issues: zombie enabled categories,
uncaught disables, permanently disabled categories, stale
cooldowns, stuck difficulties, budget exhaustion, death
spirals, script errors, and budget hogs.

Extracted from trust_ledger.py to isolate diagnostic logic.
"""
from __future__ import annotations

from .trust_constants import (
    CONSECUTIVE_FAILURES_TO_DISABLE,
    COOLDOWN_CYCLES,
    MAX_DISABLE_RETRIES,
)
from .trust_state import LoopState


def diagnose_loops(
    loops: dict[str, LoopState],
    journal_entries: list[dict] | None = None,
) -> dict:
    """Analyze all loops for issues. Returns structured report."""
    issues: list[dict] = []

    for loop_name, ls in loops.items():
        for cat_name, cs in ls.categories.items():
            # Zombie enabled
            if cs.enabled and cs.disable_count >= MAX_DISABLE_RETRIES:
                issues.append({
                    "severity": "critical",
                    "loop": loop_name,
                    "category": cat_name,
                    "issue": (
                        f"Zombie enabled: enabled=True but "
                        f"disable_count={cs.disable_count} >= {MAX_DISABLE_RETRIES}"
                    ),
                    "fix": "Run /a-loops heal --fix or check_consistency()",
                    "auto_fixable": True,
                })

            # Uncaught disable
            if cs.enabled and cs.consecutive_failures >= CONSECUTIVE_FAILURES_TO_DISABLE:
                issues.append({
                    "severity": "critical",
                    "loop": loop_name,
                    "category": cat_name,
                    "issue": (
                        f"Uncaught disable: enabled=True but "
                        f"consecutive_failures={cs.consecutive_failures}"
                    ),
                    "fix": "Run /a-loops heal --fix or check_consistency()",
                    "auto_fixable": True,
                })

            # Permanently disabled
            if cs.disable_count >= MAX_DISABLE_RETRIES:
                issues.append({
                    "severity": "critical",
                    "loop": loop_name,
                    "category": cat_name,
                    "issue": (
                        f"Permanently disabled after "
                        f"{cs.disable_count} disable cycles"
                    ),
                    "fix": "/a-loops reset or /a-loops promote",
                    "auto_fixable": False,
                })

            # Stale cooldown: disabled but cooldown would exceed 100 cycles
            if (
                not cs.enabled
                and cs.disabled_at_cycle >= 0
                and cs.disable_count > 0
                and cs.disable_count < MAX_DISABLE_RETRIES
            ):
                cooldown = COOLDOWN_CYCLES * (2 ** max(0, cs.disable_count - 1))
                remaining = cooldown - (ls.cycle_count - cs.disabled_at_cycle)
                if remaining > 100:
                    issues.append({
                        "severity": "warning",
                        "loop": loop_name,
                        "category": cat_name,
                        "issue": (
                            f"Stale cooldown: {remaining} cycles remaining "
                            f"(cooldown={cooldown})"
                        ),
                        "fix": "/a-loops promote to re-enable manually",
                        "auto_fixable": False,
                    })

            # Stuck at d0: many successes but difficulty never escalated
            if cs.success_count > 20 and cs.difficulty == 0:
                issues.append({
                    "severity": "info",
                    "loop": loop_name,
                    "category": cat_name,
                    "issue": (
                        f"Stuck at difficulty 0 despite "
                        f"{cs.success_count} successes"
                    ),
                    "fix": None,
                    "auto_fixable": False,
                })

        # Budget exhausted
        if ls.budget_remaining == 0:
            issues.append({
                "severity": "warning",
                "loop": loop_name,
                "category": None,
                "issue": "Budget exhausted (budget_remaining=0)",
                "fix": (
                    f"/a-loops configure {loop_name} --budget N "
                    "or wait for next cycle"
                ),
                "auto_fixable": False,
            })

    # Journal-based checks
    if journal_entries:
        _diagnose_journal(issues, journal_entries)

    summary = {
        "total_issues": len(issues),
        "critical": sum(1 for i in issues if i["severity"] == "critical"),
        "warning": sum(1 for i in issues if i["severity"] == "warning"),
        "info": sum(1 for i in issues if i["severity"] == "info"),
    }

    return {"issues": issues, "summary": summary}


def _diagnose_journal(issues: list[dict], journal_entries: list[dict]) -> None:
    """Append journal-based diagnostic issues."""
    from collections import Counter, defaultdict

    last_50 = journal_entries[-50:]

    # Death spiral: same action hash failing 5+ times
    failure_actions = Counter(
        (e.get("loop", ""), e.get("action", ""), e.get("category", ""))
        for e in last_50
        if e.get("result") == "failure"
    )
    for (loop_name, action, category), count in failure_actions.items():
        if count >= 5:
            issues.append({
                "severity": "critical",
                "loop": loop_name,
                "category": category,
                "issue": (
                    f"Death spiral: action '{action}' failed "
                    f"{count} times in last 50 entries"
                ),
                "fix": "Investigate root cause, consider /a-loops disable",
                "auto_fixable": False,
            })

    # Script errors in journal
    for e in last_50:
        error = e.get("error", "")
        if error and ("Traceback" in error or "TypeError" in error or "ImportError" in error):
            issues.append({
                "severity": "warning",
                "loop": e.get("loop", "unknown"),
                "category": e.get("category"),
                "issue": f"Script error: {error[:120]}",
                "fix": "Check script compatibility and dependencies",
                "auto_fixable": False,
            })

    # Single-category budget hog (>80% of actions in last cycle)
    loop_totals: dict[str, int] = defaultdict(int)
    loop_cat_totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for e in last_50:
        ln = e.get("loop", "")
        cat = e.get("category", "")
        if ln and cat:
            loop_totals[ln] += 1
            loop_cat_totals[ln][cat] += 1
    for ln, total in loop_totals.items():
        if total < 5:
            continue
        for cat, cat_total in loop_cat_totals[ln].items():
            if cat_total / total > 0.8:
                issues.append({
                    "severity": "warning",
                    "loop": ln,
                    "category": cat,
                    "issue": (
                        f"Budget hog: '{cat}' used {cat_total}/{total} "
                        f"({cat_total * 100 // total}%) of recent actions"
                    ),
                    "fix": "Review category scan scope or budget allocation",
                    "auto_fixable": False,
                })

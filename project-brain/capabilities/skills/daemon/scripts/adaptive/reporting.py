"""Cycle and category reporting dataclasses for the adaptive loop engine.

This module contains the data structures used to produce human-readable
and machine-readable reports from adaptive loop cycles.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .loops.base_loop import LoopResult


@dataclass
class CategoryReport:
    """Per-category trust snapshot for cycle reporting."""

    name: str
    trust_before: float
    trust_after: float
    difficulty_before: int
    difficulty_after: int
    status: str  # "ok", "broken", "degraded", "skipped", "stagnant"
    action_summary: str = ""
    outcome: str = ""  # "clean", "auto-fixed", "design-gated-fixed", "design-written", "report-only", "broken"
    issue_count: int = 0
    actionable_count: int = 0
    maintenance_count: int = 0
    environment_count: int = 0
    scanner_defect_count: int = 0
    manual_count: int = 0
    broken_count: int = 0
    strategy_after: str = "scan"
    self_repair_plan: str = ""
    self_repair_transition: str = ""
    execution_mode: str = "deep"
    deepening_reason: str = ""
    yield_class: str = ""
    new_fingerprint_count: int = 0
    repeated_fingerprint_count: int = 0
    resolved_fingerprint_count: int = 0
    false_positive_rate: float = 0.0
    self_repair_success_rate: float = 0.0
    short_circuit_used: bool = False
    scan_duration_ms: int = 0
    fix_duration_ms: int = 0
    total_duration_ms: int = 0
    files_changed: list[str] = field(default_factory=list)
    # ADR-412: hotspot data propagated from category state
    hot_paths: list[str] = field(default_factory=list)
    hot_patterns: list[str] = field(default_factory=list)
    dominant_root_cause: str = ""


@dataclass
class CycleReport:
    """Human-readable summary of a loop cycle."""

    loop_name: str
    categories: list[CategoryReport] = field(default_factory=list)
    duration_ms: int = 0
    results: list[LoopResult] = field(default_factory=list)
    clean_escalations: list[str] = field(default_factory=list)

    def format(self) -> str:
        """Format as aligned table for terminal display."""
        lines: list[str] = []
        n_skipped = sum(1 for c in self.categories if c.outcome in {"skipped_platform", "skipped_unsupported"})
        n_ran = len(self.categories) - n_skipped

        # Header
        header = f"┌─ {self.loop_name}"
        header += f"  ({n_ran} ran"
        if self.duration_ms:
            header += f", {self.duration_ms / 1000:.1f}s"
        header += ")"

        # Aggregate counts
        n_fixed = sum(1 for c in self.categories if c.outcome in {"auto-fixed", "design-gated-fixed"})
        n_manual = sum(c.manual_count for c in self.categories)
        n_broken = sum(1 for c in self.categories if c.outcome in {"broken", "verification-failed-reverted"})
        n_design = sum(
            1 for c in self.categories if c.outcome in {"design-gated-fixed", "design-written", "blocked-needs-design"}
        )
        n_design_written = sum(1 for c in self.categories if c.outcome == "design-written")
        n_clean = sum(1 for c in self.categories if c.outcome == "clean")
        total_actionable = sum(c.actionable_count for c in self.categories)
        total_maintenance = sum(c.maintenance_count for c in self.categories)
        total_environment = sum(c.environment_count for c in self.categories)

        tags: list[str] = []
        if total_actionable:
            tags.append(f"{total_actionable} actionable")
        if total_maintenance:
            tags.append(f"{total_maintenance} maintenance")
        if total_environment:
            tags.append(f"{total_environment} environment")
        if n_fixed:
            tags.append(f"{n_fixed} fixed")
        if n_manual:
            tags.append(f"{n_manual} manual")
        if n_design:
            tags.append(f"{n_design} design")
        if n_design_written:
            tags.append(f"{n_design_written} gate-written")
        if n_broken:
            tags.append(f"{n_broken} broken")
        n_no_coverage = sum(1 for c in self.categories if c.outcome == "no-coverage")
        if n_clean:
            tags.append(f"{n_clean} clean")
        if n_skipped:
            tags.append(f"{n_skipped} skipped")
        if n_no_coverage:
            tags.append(f"{n_no_coverage} no-coverage")
        if self.clean_escalations:
            tags.append(f"{len(self.clean_escalations)} escalated")
        if tags:
            header += f"  │  {' · '.join(tags)}"
        lines.append(header)

        # Category table
        col_cat = "CATEGORY"
        col_trust = "TRUST"
        col_diff = "DIFF"
        col_out = "OUTCOME"
        col_issues = "#"
        col_files = "FILES"
        col_summary = "SUMMARY"

        # Compute column widths
        w_cat = max(len(col_cat), *(len(c.name) for c in self.categories)) if self.categories else len(col_cat)
        w_trust = 16  # e.g. "10% → 19% (+9%)"
        w_diff = 6    # e.g. "d0→d1"
        w_out = 19    # e.g. "verification-failed"
        w_issues = 3
        w_files = 5
        # summary fills remainder

        sep = f"├{'─' * (w_cat + 2)}┬{'─' * (w_trust + 2)}┬{'─' * (w_diff + 2)}┬{'─' * (w_out + 2)}┬{'─' * (w_issues + 2)}┬{'─' * (w_files + 2)}┬─────────"
        lines.append(sep)

        hdr = (
            f"│ {col_cat:<{w_cat}} "
            f"│ {col_trust:<{w_trust}} "
            f"│ {col_diff:<{w_diff}} "
            f"│ {col_out:<{w_out}} "
            f"│ {col_issues:>{w_issues}} "
            f"│ {col_files:>{w_files}} "
            f"│ {col_summary}"
        )
        lines.append(hdr)

        sep2 = f"├{'─' * (w_cat + 2)}┼{'─' * (w_trust + 2)}┼{'─' * (w_diff + 2)}┼{'─' * (w_out + 2)}┼{'─' * (w_issues + 2)}┼{'─' * (w_files + 2)}┼─────────"
        lines.append(sep2)

        for c in self.categories:
            pct_before = int(c.trust_before * 100)
            pct_after = int(c.trust_after * 100)
            delta = pct_after - pct_before

            if c.status == "broken":
                trust_str = f"{pct_before}%→{pct_after}% BROKEN"
            elif delta > 0:
                trust_str = f"{pct_before}%→{pct_after}% (+{delta}%)"
            elif delta < 0:
                trust_str = f"{pct_before}%→{pct_after}% ({delta}%)"
            else:
                trust_str = f"{pct_after}%"

            diff_str = f"d{c.difficulty_before}"
            if c.difficulty_after != c.difficulty_before:
                diff_str = f"d{c.difficulty_before}→d{c.difficulty_after}"

            outcome = c.outcome or c.status
            issues_str = str(c.actionable_count) if c.actionable_count else "—"
            files_str = str(len(c.files_changed)) if c.files_changed else "—"
            summary = c.action_summary or "—"
            # Truncate summary to keep lines readable
            if len(summary) > 50:
                summary = summary[:47] + "..."

            row = (
                f"│ {c.name:<{w_cat}} "
                f"│ {trust_str:<{w_trust}} "
                f"│ {diff_str:<{w_diff}} "
                f"│ {outcome:<{w_out}} "
                f"│ {issues_str:>{w_issues}} "
                f"│ {files_str:>{w_files}} "
                f"│ {summary}"
            )
            lines.append(row)

        bot = f"└{'─' * (w_cat + 2)}┴{'─' * (w_trust + 2)}┴{'─' * (w_diff + 2)}┴{'─' * (w_out + 2)}┴{'─' * (w_issues + 2)}┴{'─' * (w_files + 2)}┴─────────"
        lines.append(bot)

        return "\n".join(lines)

    @staticmethod
    def format_all(reports: list["CycleReport"]) -> str:
        """Format a combined summary table across multiple loop reports."""
        if not reports:
            return "No cycle reports."

        lines: list[str] = []

        # Summary table
        col_loop = "LOOP"
        col_diff = "DIFFICULTY"
        col_cats = "CATS"
        col_issues = "ISSUES"
        col_fixed = "FIXED"
        col_manual = "MANUAL"
        col_broken = "BROKEN"
        col_clean = "CLEAN"
        col_skipped = "SKIPPED"
        col_time = "TIME"

        w_loop = max(len(col_loop), *(len(r.loop_name) for r in reports))
        w_diff = len(col_diff)
        w = 6  # numeric columns
        num_cols = f"┬{'─' * (w + 2)}" * 7

        sep = f"┌{'─' * (w_loop + 2)}┬{'─' * (w_diff + 2)}{num_cols}┐"
        lines.append(sep)

        hdr = (
            f"│ {col_loop:<{w_loop}} "
            f"│ {col_diff:<{w_diff}} "
            f"│ {col_cats:>{w}} "
            f"│ {col_issues:>{w}} "
            f"│ {col_fixed:>{w}} "
            f"│ {col_manual:>{w}} "
            f"│ {col_broken:>{w}} "
            f"│ {col_clean:>{w}} "
            f"│ {col_skipped:>{w}} │"
        )
        lines.append(hdr)

        num_sep = f"┼{'─' * (w + 2)}" * 7
        sep2 = f"├{'─' * (w_loop + 2)}┼{'─' * (w_diff + 2)}{num_sep}┤"
        lines.append(sep2)

        totals = [0, 0, 0, 0, 0, 0, 0]  # cats, issues, fixed, manual, broken, clean, skipped
        total_design_written = 0
        for r in reports:
            n_cats = len(r.categories)
            n_issues = sum(c.actionable_count for c in r.categories)
            n_fixed = sum(1 for c in r.categories if c.outcome in {"auto-fixed", "design-gated-fixed"})
            n_manual = sum(
                1
                for c in r.categories
                if c.outcome in {"report-only", "blocked-needs-design", "context-insufficient"}
            )
            n_broken = sum(1 for c in r.categories if c.outcome in {"broken", "verification-failed-reverted"})
            n_clean = sum(1 for c in r.categories if c.outcome == "clean")
            n_skipped = sum(1 for c in r.categories if c.outcome in {"skipped_platform", "skipped_unsupported"})
            n_design_written = sum(1 for c in r.categories if c.outcome == "design-written")
            totals[0] += n_cats
            totals[1] += n_issues
            totals[2] += n_fixed
            totals[3] += n_manual
            totals[4] += n_broken
            totals[5] += n_clean
            totals[6] += n_skipped
            total_design_written += n_design_written

            # Compute loop-level difficulty
            diffs = [c.difficulty_after for c in r.categories]
            max_d = max(diffs) if diffs else 0
            from .trust_ledger import MAX_DIFFICULTY
            diff_label = f"d{max_d} of d{MAX_DIFFICULTY}"

            dur = f"{r.duration_ms / 1000:.1f}s" if r.duration_ms else "—"

            row = (
                f"│ {r.loop_name:<{w_loop}} "
                f"│ {diff_label:<{w_diff}} "
                f"│ {n_cats:>{w}} "
                f"│ {n_issues:>{w}} "
                f"│ {n_fixed:>{w}} "
                f"│ {n_manual:>{w}} "
                f"│ {n_broken:>{w}} "
                f"│ {n_clean:>{w}} "
                f"│ {n_skipped:>{w}} │"
            )
            lines.append(row)

        sep3 = f"├{'─' * (w_loop + 2)}┼{'─' * (w_diff + 2)}{num_sep}┤"
        lines.append(sep3)

        total_row = (
            f"│ {'TOTAL':<{w_loop}} "
            f"│ {'':<{w_diff}} "
            f"│ {totals[0]:>{w}} "
            f"│ {totals[1]:>{w}} "
            f"│ {totals[2]:>{w}} "
            f"│ {totals[3]:>{w}} "
            f"│ {totals[4]:>{w}} "
            f"│ {totals[5]:>{w}} "
            f"│ {totals[6]:>{w}} │"
        )
        lines.append(total_row)

        num_bot = f"┴{'─' * (w + 2)}" * 7
        bot = f"└{'─' * (w_loop + 2)}┴{'─' * (w_diff + 2)}{num_bot}┘"
        lines.append(bot)
        if total_design_written:
            lines.append(f"Design gates written: {total_design_written}")

        # Per-loop detail tables
        for r in reports:
            lines.append("")
            lines.append(r.format())

        return "\n".join(lines)

"""Post-run inspection: ground-truth git analysis of what loops actually produced.

After all loops complete, inspects git commits made during the run to classify
them as real code fixes vs reports/syncs/noise. Provides the honest answer to
"did the nightly run actually fix anything?"

Used by the engine's inspect_run() and the --evolve flag.
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
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_skill_assets_dir, get_skill_data_dir


# Paths that indicate a report/sync commit, not a real fix
_REPORT_PATTERNS = {
    "docs/generated/",
    "state/",
    "hardening-",
    "coverage-gaps-report",
    "orphan-plans-report",
    "tech-debt-report",
}

_SYNC_PATTERNS = {
    "CLAUDE.md",
    "AGENTS.md",
    "CODEX.md",
    ".cursorrules",
    ".windsurfrules",
    "repo_health.yaml",
    "registry.yaml",
    "usage-history.yaml",
    "decisions-archive.md",
}

# File extensions that indicate real source code
_CODE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".scss",
    ".yaml", ".yml", ".json", ".md",
}

# Directories that contain real source code
_CODE_DIRS = {"src/", "plugins/", "project-brain/capabilities/skills/"}


@dataclass
class CommitInfo:
    """A single git commit with classification."""
    sha: str
    message: str
    files: list[str]
    classification: str = ""  # "code-fix", "report", "sync", "noise"
    is_adaptive: bool = False  # True if made by adaptive engine


@dataclass
class RunInspection:
    """Ground-truth analysis of a loop run's git output."""
    commits: list[CommitInfo] = field(default_factory=list)
    code_fixes: int = 0
    reports: int = 0
    syncs: int = 0
    noise: int = 0
    total_issues_found: int = 0
    total_categories_ran: int = 0
    categories_with_issues: int = 0
    categories_that_fixed: int = 0

    def format(self) -> str:
        adaptive_commits = [c for c in self.commits if c.is_adaptive]
        other_commits = [c for c in self.commits if not c.is_adaptive]
        lines = [
            "",
            "─── Ground Truth: Git Inspection ───",
            "",
            f"  Adaptive commits: {len(adaptive_commits)}",
            f"    Code fixes:  {self.code_fixes}",
            f"    Reports:     {self.reports}",
            f"    Syncs:       {self.syncs}",
            f"    Noise:       {self.noise}",
        ]
        if other_commits:
            lines.append(f"  Non-adaptive commits: {len(other_commits)} (excluded from counts)")
        lines.append("")

        if self.code_fixes > 0:
            lines.append("  Real fixes:")
            for c in adaptive_commits:
                if c.classification == "code-fix":
                    lines.append(f"    {c.sha} {c.message}")
            lines.append("")

        # Efficiency metric
        if self.total_issues_found > 0:
            fix_rate = (self.code_fixes / self.total_issues_found) * 100
            lines.append(f"  Fix rate: {self.code_fixes}/{self.total_issues_found} issues → {fix_rate:.1f}% converted to code fixes")
        else:
            lines.append("  Fix rate: 0 issues found (scans returned nothing)")

        if self.categories_with_issues > 0:
            lines.append(f"  Categories: {self.categories_that_fixed}/{self.categories_with_issues} with issues produced code fixes")

        lines.append("")
        return "\n".join(lines)


def classify_commit(commit: CommitInfo) -> str:
    """Classify a commit as code-fix, report, sync, or noise."""
    if not commit.files:
        return "noise"

    # Check if ALL files match report patterns
    all_report = all(
        any(p in f for p in _REPORT_PATTERNS)
        for f in commit.files
    )
    if all_report:
        return "report"

    # Check if ALL files match sync patterns
    all_sync = all(
        any(p in f or f.endswith(p) for p in _SYNC_PATTERNS)
        for f in commit.files
    )
    if all_sync:
        return "sync"

    # Check if ANY file is a real source code change
    has_code_change = any(
        any(f.startswith(d) for d in _CODE_DIRS)
        and not any(p in f for p in _REPORT_PATTERNS)
        and not any(p in f or f.endswith(p) for p in _SYNC_PATTERNS)
        for f in commit.files
    )
    if has_code_change:
        return "code-fix"

    return "noise"


def inspect_run(
    project_root: Path,
    start_time: str,
    reports: list | None = None,
) -> RunInspection:
    """Inspect git commits made since start_time and classify them.

    Args:
        project_root: Root of the git repo
        start_time: ISO timestamp or git-compatible date string
        reports: Optional list of CycleReport objects for issue/category stats
    """
    # Get commits since start time
    result = subprocess.run(
        ["git", "log", f"--since={start_time}", "--format=%H|%s", "--no-merges"],
        capture_output=True, text=True,
        cwd=str(project_root),
    )

    commits: list[CommitInfo] = []
    if result.returncode == 0 and result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            if "|" not in line:
                continue
            sha, message = line.split("|", 1)
            sha = sha[:11]

            # Get files changed in this commit
            files_result = subprocess.run(
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
                capture_output=True, text=True,
                cwd=str(project_root),
            )
            files = files_result.stdout.strip().splitlines() if files_result.returncode == 0 else []

            # Adaptive = commits made by the engine's _commit_files(), not manual dev commits
            # Engine commits use specific prefixes; manual commits often have longer messages
            # or Co-Authored-By. Check for engine commit patterns:
            is_adaptive = (
                message.startswith("chore(adaptive):") or
                message.startswith("fix(adaptive):") or
                message.startswith("style(adaptive):") or
                message.startswith("docs(adaptive):") or
                message.startswith("chore(auto):") or
                message.startswith("docs(memory):")
            )

            ci = CommitInfo(sha=sha, message=message, files=files, is_adaptive=is_adaptive)
            ci.classification = classify_commit(ci)
            commits.append(ci)

    inspection = RunInspection(commits=commits)
    # Only count adaptive commits (made by the engine, not by the user)
    adaptive = [c for c in commits if c.is_adaptive]
    inspection.code_fixes = sum(1 for c in adaptive if c.classification == "code-fix")
    inspection.reports = sum(1 for c in adaptive if c.classification == "report")
    inspection.syncs = sum(1 for c in adaptive if c.classification == "sync")
    inspection.noise = sum(1 for c in adaptive if c.classification == "noise")

    # Aggregate from cycle reports if provided
    if reports:
        for r in reports:
            for cat in r.categories:
                inspection.total_categories_ran += 1
                if cat.issue_count > 0:
                    inspection.total_issues_found += cat.issue_count
                    inspection.categories_with_issues += 1
                if cat.outcome in {"auto-fixed", "design-gated-fixed"}:
                    inspection.categories_that_fixed += 1

    return inspection


def generate_evolve_analysis(
    inspection: RunInspection,
    reports: list,
    project_root: Path,
) -> str:
    """Analyze why issues aren't converting to fixes and suggest improvements.

    Returns a structured analysis string for the --evolve flag.
    """
    lines = [
        "",
        "─── Evolve: Self-Improvement Analysis ───",
        "",
    ]

    # Find categories that found issues but produced no code fixes
    wasted = []
    for r in reports:
        for cat in r.categories:
            if cat.issue_count > 0 and cat.outcome not in {"auto-fixed", "design-gated-fixed"}:
                wasted.append({
                    "name": cat.name,
                    "loop": r.loop_name,
                    "issues": cat.issue_count,
                    "outcome": cat.outcome,
                    "summary": cat.action_summary,
                    "actionable_count": int(getattr(cat, "actionable_count", 0) or 0),
                    "scanner_defect_count": int(getattr(cat, "scanner_defect_count", 0) or 0),
                    "broken_count": int(getattr(cat, "broken_count", 0) or 0),
                    "manual_count": int(getattr(cat, "manual_count", 0) or 0),
                    "environment_count": int(getattr(cat, "environment_count", 0) or 0),
                    "maintenance_count": int(getattr(cat, "maintenance_count", 0) or 0),
                })

    # ── Section 1: Instruction Quality (cross-cutting) ──
    # Action descriptions, SKILL.md, and slash commands are all markdown
    # instructions that guide AI agents. Surface them as one concern.
    instruction_categories = _classify_instruction_issues(wasted, project_root)
    if instruction_categories:
        lines.append("  ── Instruction Quality ──")
        lines.append("")
        lines.append("  Action prompts, SKILL.md files, and slash commands are all")
        lines.append("  markdown instructions that guide AI agents. Weak instructions")
        lines.append("  produce weak agent output.")
        lines.append("")

        for surface, items in instruction_categories.items():
            total = sum(i["issues"] for i in items)
            lines.append(f"  {surface} ({total} issues):")
            for item in items:
                lines.append(f"    - {item['name']}: {item['issues']} → {item['detail']}")
            lines.append("")

        lines.append("  → Fix priority: action prompts (user-facing) > SKILL.md (agent-facing) > command evolution (meta)")
        lines.append("")

    # ── Section 2: Wasted scans ──
    if not wasted:
        if not instruction_categories:
            lines.append("  All categories with issues produced fixes. No improvements needed.")
        return "\n".join(lines)

    # Filter out instruction categories already reported above
    instruction_names = set()
    for items in instruction_categories.values():
        for item in items:
            instruction_names.add(item["name"])
    non_instruction_wasted = [w for w in wasted if w["name"] not in instruction_names]

    if non_instruction_wasted:
        lines.append(f"  ── {len(non_instruction_wasted)} categories found issues but produced NO code fixes ──")
        lines.append("")

        # Group by reason
        report_only = [w for w in non_instruction_wasted if w["outcome"] == "report-only"]
        design_written = [w for w in non_instruction_wasted if w["outcome"] == "design-written"]
        design_blocked = [w for w in non_instruction_wasted if w["outcome"] == "blocked-needs-design"]
        context_missing = [w for w in non_instruction_wasted if w["outcome"] == "context-insufficient"]
        broken = [
            w
            for w in non_instruction_wasted
            if w["outcome"] in {"broken", "verification-failed-reverted"}
        ]
        report_upgrade = [
            w for w in report_only
            if _automatable_issue_count(w) > 0
        ]
        report_manual = [
            w for w in report_only
            if _automatable_issue_count(w) == 0 and w["manual_count"] > 0
        ]
        report_environment = [
            w for w in report_only
            if _automatable_issue_count(w) == 0
            and w["manual_count"] == 0
            and w["environment_count"] > 0
        ]
        report_maintenance = [
            w for w in report_only
            if _automatable_issue_count(w) == 0
            and w["manual_count"] == 0
            and w["environment_count"] == 0
            and w["maintenance_count"] > 0
        ]

        if report_upgrade:
            lines.append("  Report-only with automatable debt (scan works, fix() writes reports only):")
            for w in report_upgrade:
                lines.append(f"    - {w['name']}: {w['issues']} issues → {w['summary'][:80]}")
            lines.append("")
            lines.append("  → These modules need fix() upgraded from report-writing to actual code fixes.")
            lines.append("    Priority: modules with the most issues found.")
            lines.append("")

        if design_written:
            lines.append("  Structural findings that produced a design gate artifact:")
            for w in design_written:
                lines.append(f"    - {w['name']}: {w['issues']} issues → {w['summary'][:80]}")
            lines.append("")
            lines.append("  → Review the new design note/ADR, then rerun the loop at higher difficulty to attempt implementation.")
            lines.append("")

        if design_blocked:
            lines.append("  Structural findings blocked until a design gate exists:")
            for w in design_blocked:
                lines.append(f"    - {w['name']}: {w['issues']} issues → {w['summary'][:80]}")
            lines.append("")
            lines.append("  → Write or update the governing ADR/runtime design note before attempting a broad fix.")
            lines.append("")

        if context_missing:
            lines.append("  Structural findings with insufficient project context:")
            for w in context_missing:
                lines.append(f"    - {w['name']}: {w['issues']} issues → {w['summary'][:80]}")
            lines.append("")
            lines.append("  → Pull ADR/wiki or implementation context before retrying the fix path.")
            lines.append("")

        if report_manual:
            lines.append("  Manual follow-up by design:")
            for w in report_manual:
                lines.append(f"    - {w['name']}: {w['issues']} issues → {w['summary'][:80]}")
            lines.append("")
            lines.append("  → These are user or ADR decisions, not adaptive remediation debt.")
            lines.append("")

        if report_environment:
            lines.append("  Environment-gated:")
            for w in report_environment:
                lines.append(f"    - {w['name']}: {w['issues']} issues → {w['summary'][:80]}")
            lines.append("")
            lines.append("  → These require environment repair or setup, not scanner evolution.")
            lines.append("")

        if report_maintenance:
            lines.append("  Maintenance / evolution output:")
            for w in report_maintenance:
                lines.append(f"    - {w['name']}: {w['issues']} issues → {w['summary'][:80]}")
            lines.append("")
            lines.append("  → These are expected scan outputs. Keep evolving scope and coverage, but no fix() upgrade is required.")
            lines.append("")

        if broken:
            lines.append("  Broken (fix() failed):")
            for w in broken:
                lines.append(f"    - {w['name']}: {w['issues']} issues → {w['summary'][:80]}")
            lines.append("")
            lines.append("  → These need debugging. Check journal for error details.")
            lines.append("")

    # ── Section 3: Prioritized improvements ──
    prioritized = [
        w for w in wasted
        if w["outcome"] == "broken" or _automatable_issue_count(w) > 0
    ]
    if prioritized:
        lines.append("  ── Prioritized improvements (by issue count) ──")
        lines.append("")
        sorted_wasted = sorted(prioritized, key=lambda w: w["issues"], reverse=True)
        for i, w in enumerate(sorted_wasted[:5], 1):
            lines.append(f"    {i}. {w['name']} ({w['issues']} issues, {w['outcome']})")
            suggestion = _suggest_improvement(w["name"], w["outcome"])
            if suggestion:
                lines.append(f"       → {suggestion}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Instruction quality: cross-cutting analysis of AI instruction surfaces
# ---------------------------------------------------------------------------

# Categories that produce instruction-quality issues, grouped by surface
_INSTRUCTION_SURFACES: dict[str, dict[str, str]] = {
    "Action Prompts (dashboard → IDE agent)": {
        "auto-markdowns": "missing or non-standard prompt templates — actions lack structured AI instructions",
    },
    "SKILL.md (slash commands → agent instructions)": {
        "auto-skill-md": "missing or incomplete SKILL.md — slash commands lack structured instructions",
        "auto-skill-refs": "broken cross-skill references in SKILL.md files",
    },
    "Command Evolution (runtime → instruction improvement)": {
        "auto-command-track": "command executions not tracked — no data for instruction improvement",
    },
}


def _classify_instruction_issues(
    wasted: list[dict],
    project_root: Path,
) -> dict[str, list[dict]]:
    """Identify wasted categories that are instruction-quality issues.

    Returns a dict of surface → list of {name, issues, detail} for
    categories that belong to the instruction quality dimension.
    """
    result: dict[str, list[dict]] = {}

    for surface, category_map in _INSTRUCTION_SURFACES.items():
        surface_items = []
        for w in wasted:
            if w["name"] in category_map:
                surface_items.append({
                    "name": w["name"],
                    "issues": w["issues"],
                    "detail": category_map[w["name"]],
                })
        if surface_items:
            result[surface] = surface_items

    # Also scan for instruction quality issues even if the category ran clean
    # (i.e. issues=0 in adaptive but known debt exists). Check the filesystem.
    if "Action Prompts (dashboard → IDE agent)" not in result:
        # Quick heuristic: count runAction calls without prompt template .md files
        contextless_count = _count_contextless_actions(project_root)
        if contextless_count > 0:
            result.setdefault("Action Prompts (dashboard → IDE agent)", []).append({
                "name": "auto-markdowns (passive)",
                "issues": contextless_count,
                "detail": f"{contextless_count} runAction calls without prompt templates — run /a-loops run auto-markdowns to scan",
            })

    return result


def _count_contextless_actions(project_root: Path) -> int:
    """Quick heuristic count of runAction calls without prompt template .md files."""
    import re

    # Discover existing templates from vault-backed skill data with assets fallback.
    templates = set()
    for skill_dir in sorted((project_root / "project-brain" / "capabilities" / "skills").glob("*")):
        if not skill_dir.is_dir():
            continue
        skill_name = skill_dir.name
        try:
            data_prompts = get_skill_data_dir(skill_name) / "prompts"
            assets_prompts = get_skill_assets_dir(skill_name) / "prompts"
        except ValueError:
            continue
        for prompts_dir in (data_prompts, assets_prompts):
            if not prompts_dir.exists():
                continue
            for md in prompts_dir.glob("*.md"):
                templates.add(md.stem)

    count = 0
    for tsx in project_root.glob("project-brain/capabilities/skills/*/augur/dashboard/**/*.tsx"):
        try:
            content = tsx.read_text(errors="replace")
        except OSError:
            continue
        for m in re.finditer(r"""runAction\(\s*\{[^}]*?id:\s*['"]([^'"]+)['"]""", content, re.DOTALL):
            if m.group(1) not in templates:
                count += 1
    return count


def _suggest_improvement(category: str, outcome: str) -> str:
    """Suggest a specific improvement for a category."""
    suggestions = {
        "auto-coverage-check": "Add test stub generation for untested modules",
        "auto-code-review": "Wire tsc/lint errors to auto-fix via eslint --fix / code changes",
        "auto-test-dashboard": "Add auto-retry with cache clear for flaky Jest tests",
        "auto-test-mcp-commands": "Add tool registration fix for broken MCP tools",
        "auto-adr-audit": "Add auto-fix for ADR status inconsistencies",
        "auto-tech-debt": "Add file splitting for oversized modules",
        "auto-stale-paths": "Expand ADR-270 drift coverage and graduate report-only findings into targeted fixers",
        "auto-markdowns": "Generate missing prompt templates and migrate inline descriptions to vault prompts/ with assets/seeds/prompts/ fallback",
        "auto-skill-md": "Generate missing SKILL.md with proper sections (Usage, Flags, Examples) from command docs and skill structure",
    }
    if category in suggestions:
        return suggestions[category]
    if outcome == "report-only":
        return "Upgrade fix() from report-only to actual code changes"
    if outcome == "broken":
        return "Debug fix() failure — check journal for stack trace"
    return ""


def _automatable_issue_count(category: dict[str, object]) -> int:
    """Count issues that adaptive remediation can realistically address."""
    return sum(
        int(category.get(key, 0) or 0)
        for key in ("actionable_count", "scanner_defect_count", "broken_count")
    )

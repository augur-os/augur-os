"""auto-inspect: Inspect observability dimensions and context window footprint.

Observation-only module — no auto-fix. Collects metrics:
  d0: SKILL.md count and sizes, ops module count, dashboard page count
  d1: Total token estimate across all skills, page-to-skill ratio
  d2: Per-hub breakdown, orphan skill detection
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
from pathlib import Path

from src.config.paths import get_project_brain_skills_dir
from src.lib.ops_protocol import (
    OpsContext,
    ScanResult,
    FixResult,
    make_issue,
    evolution_gap,
    report_only_fix,
)

name = "auto-inspect"

DIFFICULTY_SPEC = {
    0: "Surface — SKILL.md count/sizes, ops module count, dashboard page count",
    1: "Content — total token estimate, page-to-skill ratio",
    2: "Deep — per-hub breakdown, orphan skill detection",
}

logger = logging.getLogger(__name__)

# Rough token estimate: ~4 chars per token for English text
CHARS_PER_TOKEN = 4


def _shared_skill_dirs(project_root: Path) -> list[Path]:
    """Return project-brain skill directories for project-source inspection."""
    skills_dir = get_project_brain_skills_dir(project_root)
    if not skills_dir.is_dir():
        return []
    return sorted(
        skill_dir
        for skill_dir in skills_dir.iterdir()
        if skill_dir.is_dir() and not skill_dir.name.startswith(".")
    )


def _count_skill_md_stats(project_root: Path) -> tuple[int, int, int]:
    """Count SKILL.md files and total size. Returns (count, total_bytes, total_lines)."""
    count = 0
    total_bytes = 0
    total_lines = 0
    for skill_dir in _shared_skill_dirs(project_root):
        skill_md = skill_dir / "SKILL.md"
        if skill_md.is_file():
            count += 1
            try:
                content = skill_md.read_text(encoding="utf-8")
                total_bytes += len(content.encode("utf-8"))
                total_lines += len(content.splitlines())
            except OSError:
                continue
    return count, total_bytes, total_lines


def _count_ops_modules(project_root: Path) -> int:
    """Count ops module files (scripts/*_ops.py) across all skills."""
    count = 0
    for skill_dir in _shared_skill_dirs(project_root):
        count += sum(1 for ops_file in (skill_dir / "scripts").glob("*_ops.py") if ops_file.is_file())
    return count


def _count_dashboard_pages(project_root: Path) -> int:
    """Count dashboard page.tsx files."""
    app_dir = project_root / "apps" / "dashboard" / "app"
    if not app_dir.is_dir():
        return 0
    return sum(1 for _ in app_dir.rglob("page.tsx"))


def _collect_hub_breakdown(project_root: Path) -> dict[str, int]:
    """Count skills per hub from SKILL.md x-augur-hub frontmatter."""
    import yaml as _yaml

    hubs: dict[str, int] = {}
    for skill_dir in _shared_skill_dirs(project_root):
        skill_md = skill_dir / "SKILL.md"
        try:
            content = skill_md.read_text(encoding="utf-8")
            if not content.startswith("---"):
                continue
            end = content.index("---", 3)
            fm = _yaml.safe_load(content[3:end])
            if isinstance(fm, dict):
                hub = fm.get("x-augur-hub", "unassigned")
                hubs[hub] = hubs.get(hub, 0) + 1
        except Exception:
            hubs["parse-error"] = hubs.get("parse-error", 0) + 1
    return hubs


def _find_orphan_skills(project_root: Path) -> list[str]:
    """Find skills with no SKILL.md or empty SKILL.md."""
    orphans: list[str] = []
    for skill_dir in _shared_skill_dirs(project_root):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            orphans.append(skill_dir.name)
        else:
            try:
                if skill_md.stat().st_size == 0:
                    orphans.append(skill_dir.name)
            except OSError:
                orphans.append(skill_dir.name)
    return orphans


def scan(ctx: OpsContext) -> ScanResult:
    """Inspect observability dimensions — collect metrics about the project."""
    from src.config.paths import get_project_root

    project_root = get_project_root()
    issues: list[dict] = []
    items_scanned = 0

    # --- d0: SKILL.md stats ---
    skill_count, total_bytes, total_lines = _count_skill_md_stats(project_root)
    items_scanned += skill_count

    issues.append(make_issue(
        category="inspect",
        detail=f"SKILL.md census: {skill_count} files, {total_lines:,} total lines, {total_bytes:,} bytes",
        kind="maintenance",
        root_cause_type="unknown",
        fixability="manual",
        metric_skill_count=skill_count,
        metric_total_lines=total_lines,
        metric_total_bytes=total_bytes,
    ))

    # d0: Ops module count
    ops_count = _count_ops_modules(project_root)
    items_scanned += 1
    issues.append(make_issue(
        category="inspect",
        detail=f"Ops modules: {ops_count} *_ops.py files across skills",
        kind="maintenance",
        root_cause_type="unknown",
        fixability="manual",
        metric_ops_count=ops_count,
    ))

    # d0: Dashboard page count
    page_count = _count_dashboard_pages(project_root)
    items_scanned += 1
    issues.append(make_issue(
        category="inspect",
        detail=f"Dashboard pages: {page_count} page.tsx files",
        kind="maintenance",
        root_cause_type="unknown",
        fixability="manual",
        metric_page_count=page_count,
    ))

    # --- d1: Token estimate and ratios ---
    if ctx.difficulty >= 1:
        estimated_tokens = total_bytes // CHARS_PER_TOKEN
        issues.append(make_issue(
            category="inspect",
            detail=f"Estimated total SKILL.md token load: {estimated_tokens:,} tokens",
            kind="maintenance",
            root_cause_type="unknown",
            fixability="manual",
            metric_estimated_tokens=estimated_tokens,
        ))

        # Page-to-skill ratio
        if skill_count > 0:
            ratio = page_count / skill_count
            issues.append(make_issue(
                category="inspect",
                detail=f"Page-to-skill ratio: {ratio:.2f} ({page_count} pages / {skill_count} skills)",
                kind="maintenance",
                root_cause_type="unknown",
                fixability="manual",
                metric_page_skill_ratio=round(ratio, 2),
            ))

        # Ops coverage ratio
        if skill_count > 0:
            ops_ratio = ops_count / skill_count
            issues.append(make_issue(
                category="inspect",
                detail=f"Ops module coverage: {ops_ratio:.0%} ({ops_count}/{skill_count} skills have ops modules)",
                kind="maintenance",
                root_cause_type="unknown",
                fixability="manual",
                metric_ops_coverage=round(ops_ratio, 2),
            ))

    # --- d2: Per-hub breakdown and orphans ---
    if ctx.difficulty >= 2:
        hub_breakdown = _collect_hub_breakdown(project_root)
        if hub_breakdown:
            breakdown_str = ", ".join(f"{h}={c}" for h, c in sorted(hub_breakdown.items()))
            issues.append(make_issue(
                category="inspect",
                detail=f"Hub breakdown: {breakdown_str}",
                kind="maintenance",
                root_cause_type="unknown",
                fixability="manual",
                metric_hub_breakdown=hub_breakdown,
            ))

        orphans = _find_orphan_skills(project_root)
        if orphans:
            issues.append(make_issue(
                category="inspect",
                detail=f"{len(orphans)} orphan skills (no/empty SKILL.md): {', '.join(orphans[:10])}{'...' if len(orphans) > 10 else ''}",
                kind="maintenance",
                root_cause_type="manual_debt",
                fixability="manual",
                metric_orphan_skills=orphans,
            ))

    # d2: evolution gaps (always report — inspection can always be deeper)
    if ctx.difficulty >= 2:
        issues.append(evolution_gap(
            "Inspect module covers basic census metrics. "
            "Consider adding: runtime MCP call latency profiling, "
            "context window utilization per agent session, "
            "skill dependency graph analysis, "
            "block rendering performance metrics.",
            category="inspect",
        ))

    # Inspect is observability — always info severity
    return ScanResult(
        issues=issues,
        summary=f"Collected {len(issues)} observability metrics",
        severity="info",
        health="verified",
        items_scanned=items_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix is report-only for inspect — writes observability data to report file."""
    return report_only_fix(ctx, "inspect-report.json", issues, noun="metric")

"""auto-ui-quality: Nightly UI/UX quality audit autoloop.

Scans all dashboard pages for accessibility, interaction, design system,
and responsiveness issues. Auto-fixes at d2+ with git safety net.
LLM-assisted visual analysis at d3-d4.
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
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Sibling module loader — engine loads this file standalone, not as a package
_SCRIPTS_DIR = Path(__file__).resolve().parent


def _import_sibling(name: str):
    """Import a sibling .py file from the same scripts/ directory."""
    module_path = _SCRIPTS_DIR / f"{name}.py"
    fq_name = f"auto_ui_quality.{name}"
    if fq_name in sys.modules:
        return sys.modules[fq_name]
    spec = importlib.util.spec_from_file_location(fq_name, str(module_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[fq_name] = mod
    spec.loader.exec_module(mod)
    return mod

from src.config.paths import get_project_root, get_runtime_dir
from src.lib.staged_skill_catalog import find_skill_file
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    check_intentional_skip,
    evolution_gap,
    issue_fingerprint,
    make_issue,
)

name = "auto-ui-quality"

DIFFICULTY_SPEC = {
    0: "Inventory — discover pages, flag accessibility errors (aria-label) only",
    1: "Pattern check — cursor-pointer, hardcoded colors, emoji, transitions, icons, responsive classes",
    2: "Safe auto-fix — add cursor-pointer, fix transitions, replace hardcoded colors",
    3: "Visual analysis — Playwright screenshots, LLM audit against ui-ux-pro-max guidelines",
    4: "Full redesign — structural rewrites, layout grouping, search/filter addition",
}


def _get_state_dir() -> Path:
    return get_runtime_dir() / "adaptive" / "ui-quality"


def _get_registry_path() -> Path:
    return _get_state_dir() / "page-scores.json"


def _find_page_files(project_root: Path) -> dict[str, Path]:
    """Find all page.tsx files and map route → file path."""
    pages: dict[str, Path] = {}
    # Primary: apps/dashboard/features/pages/{hub}/**/page.tsx
    skills_pages = project_root / "apps" / "dashboard" / "features" / "pages"
    if skills_pages.exists():
        for page_file in skills_pages.rglob("page.tsx"):
            rel = page_file.relative_to(skills_pages)
            route = str(rel.parent).replace("\\", "/")
            if route != ".":
                pages[route] = page_file
    return pages


def scan(ctx: OpsContext) -> ScanResult:
    """Scan dashboard pages for UI quality issues."""
    _checks = _import_sibling("checks")
    _scorer = _import_sibling("scorer")
    run_all_checks = _checks.run_all_checks
    compute_page_score = _scorer.compute_page_score
    load_registry = _scorer.load_registry
    save_registry = _scorer.save_registry

    project_root = ctx.project_root or get_project_root()
    page_files = _find_page_files(project_root)

    if not page_files:
        return ScanResult(
            issues=[evolution_gap(
                "No dashboard pages found. Check apps/dashboard/features/pages/ exists.",
                category="ui-quality",
            )],
            summary="No pages found",
            severity="warning",
            health="degraded",
        )

    registry = load_registry(_get_registry_path())
    all_issues: list[dict] = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for page_path, page_file in page_files.items():
        # Check intentional skip
        if check_intentional_skip(page_file):
            continue

        try:
            content = page_file.read_text()
        except (OSError, UnicodeDecodeError):
            continue

        result = run_all_checks(content, page_path, difficulty=min(ctx.difficulty, 1))
        page_score = compute_page_score(result["dimension_scores"])

        # Update registry
        registry[page_path] = {
            "score": round(page_score, 1),
            "last_audit": today,
            "issues": {
                "d0": len([i for i in result["issues"] if i.get("confidence") == "high"]),
                "d1": len([i for i in result["issues"] if i.get("confidence") in ("medium", "low")]),
            },
            "check_counts": {
                "applicable": result["applicable"],
                "passing": result["passing"],
            },
        }

        # Convert check issues to ops_protocol issues
        for issue in result["issues"]:
            all_issues.append(make_issue(
                category="ui-quality",
                detail=f"{page_path}: {issue['detail']}",
                path=str(page_file),
                kind="actionable" if ctx.difficulty >= 2 else "maintenance",
                root_cause_type="repo_bug",
                fixability="auto" if issue.get("confidence") == "high" else "manual",
                fingerprint=issue_fingerprint(
                    category="ui-quality",
                    path=page_path,
                    detail=issue["check_id"],
                ),
                check_id=issue["check_id"],
                page_route=page_path,
                dimension=issue.get("dimension", ""),
                confidence=issue.get("confidence", "medium"),
                line=issue.get("line", 0),
            ))

    # Save updated registry
    save_registry(registry, _get_registry_path())

    # Evolution gaps at max difficulty with no issues
    if ctx.difficulty >= 2 and not all_issues:
        all_issues.append(evolution_gap(
            "All pages pass d0-d1 checks. Next: add dark mode contrast checking, "
            "viewport resize testing for responsive breakpoints.",
            category="ui-quality",
        ))

    # Compute summary stats
    scores = [r["score"] for r in registry.values()]
    avg_score = sum(scores) / len(scores) if scores else 0

    return ScanResult(
        issues=all_issues,
        summary=(
            f"Scanned {len(page_files)} pages, avg score {avg_score:.0f}/100, "
            f"{len(all_issues)} issues found"
        ),
        severity="warning" if all_issues else "info",
        health="degraded" if avg_score < 60 else "verified",
        items_scanned=len(page_files),
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix UI quality issues at d2+ with git safety net."""
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} issues")

    if not issues:
        return FixResult(success=True, summary="No issues to fix")

    # d0-d1: scan-only, no fixes expected
    if ctx.difficulty < 2:
        return FixResult(
            success=True,
            summary=f"Scan found {len(issues)} issues (fixes require d2+)",
            fix_type="report",
        )

    _checks = _import_sibling("checks")
    _fixers = _import_sibling("fixers")
    _scorer = _import_sibling("scorer")
    run_all_checks = _checks.run_all_checks
    safe_fix_page = _fixers.safe_fix_page
    compute_page_score = _scorer.compute_page_score
    load_registry = _scorer.load_registry
    priority_sort = _scorer.priority_sort
    save_registry = _scorer.save_registry

    project_root = ctx.project_root or get_project_root()
    page_files = _find_page_files(project_root)
    registry = load_registry(_get_registry_path())

    # Get verify command from engine config
    verify_command = ctx.loop_config.get("verify_command")

    all_actions: list[dict] = []
    all_changes: list[str] = []

    # ── d2: Safe auto-fixes ────────────────────────────────────────
    # Try all pages that exist as files (not just worst N by score).
    # The d2 fixers target specific patterns (cursor-pointer, transition
    # durations) that may not correlate with lowest scores. Pages that
    # only exist in the registry (YAML-generated) have no TSX to fix.
    if ctx.difficulty >= 2:
        # All real TSX pages first, then worst registry pages that exist
        candidate_pages = list(page_files.keys())

        def score_fn(page_path: str) -> float:
            """Re-score a page after fix."""
            pf = page_files.get(page_path)
            if not pf or not pf.exists():
                return 0
            content = pf.read_text()
            result = run_all_checks(content, page_path, difficulty=1)
            return compute_page_score(result["dimension_scores"])

        # Check baseline build once — skip verify for all pages if broken
        baseline_build_ok = _fixers.verify_build(project_root, verify_command)

        fixed_count_d2 = 0
        for page_path in candidate_pages:
            page_file = page_files.get(page_path)
            if not page_file or not page_file.exists():
                continue

            score_before = registry.get(page_path, {}).get("score", 0)
            action = safe_fix_page(
                project_root=project_root,
                page_path=page_path,
                page_file=page_file,
                score_before=score_before,
                score_fn=score_fn,
                verify_command=verify_command,
                baseline_build_ok=baseline_build_ok,
            )
            all_actions.append(action)
            if action.get("action") == "fixed":
                fixed_count_d2 += 1
                all_changes.append(
                    f"{page_path}: {', '.join(action.get('changes', []))}"
                )
                # Update registry with new score
                registry[page_path]["score"] = action.get("score_after", score_before)

    # ── d3-d4: LLM-assisted visual analysis ──────────────────────
    if ctx.difficulty >= 3:
        from scripts.visual import (
            build_llm_prompt,
            check_dashboard_available,
            get_design_recommendations,
            screenshot_page,
        )

        dashboard_up = check_dashboard_available()
        if not dashboard_up:
            all_actions.append({
                "action": "skip_visual",
                "reason": "Dashboard not running at localhost:3000",
            })
        else:
            analysis_limit = ctx.config.get("d3_analysis_limit", 3)
            rewrite_limit = ctx.config.get("max_page_rewrites", 3)
            worst_pages = priority_sort(registry)[:analysis_limit]
            rewrites_done = 0

            search_script = find_skill_file(
                project_root,
                "ui-ux-pro-max",
                "scripts",
                "search.py",
            ) or (
                project_root
                / "project-brain"
                / "capabilities"
                / "skills"
                / "ui-ux-pro-max"
                / "scripts"
                / "search.py"
            )
            runtime_dir = get_runtime_dir()

            for page_path in worst_pages:
                if rewrites_done >= rewrite_limit:
                    break

                page_file = page_files.get(page_path)
                if not page_file or not page_file.exists():
                    continue

                # Screenshot before
                screenshot_before = screenshot_page(
                    page_path, runtime_dir, label="before"
                )

                # Get design recommendations
                design_recs = get_design_recommendations(
                    f"dashboard {page_path}", search_script
                )

                # Build LLM prompt
                score_data = registry.get(page_path, {})
                page_source = page_file.read_text()
                page_issues = [
                    i for i in issues if i.get("page_route") == page_path
                ]

                llm_prompt = build_llm_prompt(
                    page_path=page_path,
                    page_source=page_source,
                    score_breakdown=score_data,
                    issues=page_issues,
                    design_recommendations=design_recs,
                    screenshot_path=screenshot_before,
                )

                all_actions.append({
                    "kind": "llm_escalation",
                    "page": page_path,
                    "prompt": llm_prompt,
                    "reason": f"score {score_data.get('score', 0):.0f}/100, {len(page_issues)} issues",
                })
                rewrites_done += 1

    # Save updated registry
    save_registry(registry, _get_registry_path())

    # ── Write reports ────────────────────────────────────────────
    _write_reports(registry, all_actions, all_changes)

    fixed_count = sum(1 for a in all_actions if a.get("action") == "fixed")
    llm_count = sum(1 for a in all_actions if a.get("kind") == "llm_escalation")

    summary_parts = []
    if fixed_count:
        summary_parts.append(f"Fixed {fixed_count} pages")
    if llm_count:
        summary_parts.append(f"{llm_count} LLM escalation(s) queued")
    if not summary_parts:
        summary_parts.append("No fixes applied")

    return FixResult(
        # Report-only outcomes are not loop failures. Only real exceptions
        # should mark the category failed in the engine.
        success=True,
        actions=all_actions,
        changes=all_changes,
        summary=", ".join(summary_parts),
        fix_type="code-fix" if all_changes else "report",
    )


def _write_reports(
    registry: dict,
    actions: list[dict],
    changes: list[str],
) -> None:
    """Write JSON + markdown reports."""
    state_dir = _get_state_dir()
    reports_dir = state_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    scores = [r["score"] for r in registry.values()]
    avg_score = sum(scores) / len(scores) if scores else 0

    # JSON report
    json_report = {
        "date": today,
        "pages_scanned": len(registry),
        "average_score": round(avg_score, 1),
        "total_issues": sum(
            r.get("issues", {}).get("d0", 0) + r.get("issues", {}).get("d1", 0)
            for r in registry.values()
        ),
        "fixes_applied": len(changes),
        "actions": actions,
    }
    (reports_dir / f"{today}.json").write_text(json.dumps(json_report, indent=2))

    # Markdown report
    sorted_pages = sorted(registry.items(), key=lambda x: x[1].get("score", 0))
    bottom_5 = sorted_pages[:5]

    md_lines = [
        f"# UI Quality Report — {today}\n",
        "## Summary",
        f"- Pages scanned: {len(registry)}",
        f"- Average score: {avg_score:.0f}/100",
        f"- Fixes applied: {len(changes)}",
        "",
        "## Bottom 5 Pages",
        "| Page | Score | d0 Issues | d1 Issues |",
        "|------|-------|-----------|-----------|",
    ]
    for page, data in bottom_5:
        d0 = data.get("issues", {}).get("d0", 0)
        d1 = data.get("issues", {}).get("d1", 0)
        md_lines.append(f"| {page} | {data.get('score', 0):.0f} | {d0} | {d1} |")

    if changes:
        md_lines.extend(["", "## Fixes Applied"])
        for change in changes:
            md_lines.append(f"- {change}")

    (reports_dir / f"{today}.md").write_text("\n".join(md_lines))

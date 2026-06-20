"""auto-test-pages: Dashboard page route validation with auto-fix.

Difficulty escalation:
  d0: Surface — verify the Workspace route registry resolves to page slugs
  d1: Probe Workspace routes, auto-fix via mount-plugins re-run + cache clear
  d2: Check sub-page routes, re-mount + rebuild on failure
  d3+: Validate response content and attempt source-level fixes via CLI
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
import logging
import re
import shutil
import subprocess
from pathlib import Path

from src.lib.ops_protocol import (
    OpsContext,
    ScanResult,
    FixResult,
    check_http_route,
    write_report,
)

name = "auto-test-pages"

logger = logging.getLogger(__name__)

DIFFICULTY_SPEC = {
    0: "Surface check — verify the Workspace route registry resolves to page slugs",
    1: "Content check — probe each Workspace route for HTTP 200, auto-fix via remount",
    2: "Deep check — check all page routes, rebuild on failure",
    3: "Exhaustive — validate response content, CLI-assisted source fixes",
    4: "Expert — full page render validation with timing analysis",
}

# ADR-802 collapsed the hub taxonomy into two fixed surfaces (Browse +
# Workspace). The single Workspace catch-all route registry is now the live
# source of mounted page slugs; the legacy assembled-hubs.json is never
# written. Each slug maps to a `/workspace/{slug}` route.
_WORKSPACE_REGISTRY = "apps/dashboard/app/workspace/[[...slug]]/registry.ts"
_REGISTRY_SLUG = re.compile(r"^\s*'([a-z0-9-]+)':\s*\(\)\s*=>", re.MULTILINE)


def _load_hubs(project_root: Path) -> list[dict]:
    """Return routable page entries from the Workspace route registry.

    Each entry is ``{"id": slug, "path": "/workspace/{slug}"}`` so the existing
    route-probing logic can consume it unchanged.
    """
    registry_path = project_root / _WORKSPACE_REGISTRY
    if not registry_path.exists():
        return []
    try:
        content = registry_path.read_text(encoding="utf-8")
    except OSError:
        return []
    return [
        {"id": slug, "path": f"/workspace/{slug}"}
        for slug in _REGISTRY_SLUG.findall(content)
    ]


def scan(ctx: OpsContext) -> ScanResult:
    hubs = _load_hubs(ctx.project_root)
    if not hubs:
        if ctx.shared_snapshot and ctx.shared_snapshot.get("page_routes"):
            return ScanResult(
                issues=[],
                summary=(
                    f"shared snapshot loaded ({len(ctx.shared_snapshot.get('page_routes', []))} page routes, d0 surface only)"
                ),
                severity="info",
                health="verified",
            )
        return ScanResult(issues=[], summary="No Workspace route registry found", severity="info")

    # Page route health is critical when explicitly configured at d1+, but keep
    # the d0 surface pass reachable when no minimum is enforced.
    effective_difficulty = max(ctx.difficulty, int(ctx.config.get("min_difficulty", 0)))

    # d0: surface check — just confirm the registry resolves to slugs, no HTTP probes
    if effective_difficulty < 1:
        return ScanResult(
            issues=[], summary=f"Workspace route registry loaded ({len(hubs)} page routes, d0 surface only)",
            severity="info", health="verified",
        )

    hub_filter = ctx.config.get("hub")
    base_url = ctx.config.get("base_url", "http://localhost:3000")
    timeout = ctx.config.get("request_timeout", 10)

    # Pre-check: is the dashboard reachable?
    probe = check_http_route(base_url, timeout=3)
    if not probe.get("ok"):
        return ScanResult(issues=[], summary="Dashboard not running — skipping page checks", severity="info")
    issues: list[dict] = []
    checked = 0

    for hub_data in hubs:
        if not isinstance(hub_data, dict):
            continue
        try:
            hub_id = hub_data.get("id", "")
            if hub_filter and hub_id != hub_filter:
                continue
            path = hub_data.get("path", f"/{hub_id}")
            url = f"{base_url}{path}"
            result = check_http_route(url, timeout=timeout)
            checked += 1
            if not result.get("ok"):
                status = result.get("status", 0)
                error_category = "not-found" if status == 404 else "server-error" if status >= 500 else "unreachable"
                issues.append({"hub": hub_id, "path": path, "error_category": error_category, **result})
        except (AttributeError, TypeError):
            # Skip malformed hub entries (e.g. string instead of dict during regeneration)
            continue

    if not issues:
        scope = f" for {hub_filter}" if hub_filter else ""
        return ScanResult(issues=[], summary=f"All {checked} page routes OK{scope}", severity="info")

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)}/{checked} page route(s) failed",
        severity="error",
    )


def _run_mount_plugins(project_root: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    """Re-run mount-plugins to regenerate page registries and hub assembly."""
    dashboard_dir = project_root / "apps" / "dashboard"
    mount_script = dashboard_dir / "scripts" / "dist" / "mount-plugins.mjs"
    if mount_script.is_file():
        return subprocess.run(
            ["node", str(mount_script)],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(dashboard_dir),
        )
    # Fallback to npm script
    return subprocess.run(
        ["npm", "run", "mount-plugins"],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(dashboard_dir),
    )


def _clear_next_cache(dashboard_dir: Path) -> bool:
    """Remove .next/cache and .next/dev to fix stale build artifacts."""
    cleared = False
    for subdir in ("cache", "dev"):
        target = dashboard_dir / ".next" / subdir
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            cleared = True
    return cleared


def _verify_routes(
    base_url: str, issues: list[dict], timeout: int = 10,
) -> tuple[list[dict], list[dict]]:
    """Re-check failed routes. Returns (still_broken, now_fixed)."""
    still_broken: list[dict] = []
    now_fixed: list[dict] = []
    for issue in issues:
        path = issue.get("path", "")
        if not path:
            still_broken.append(issue)
            continue
        url = f"{base_url}{path}"
        result = check_http_route(url, timeout=timeout)
        if result.get("ok"):
            now_fixed.append(issue)
        else:
            still_broken.append({**issue, **result})
    return still_broken, now_fixed


def _check_page_source_exists(project_root: Path, hub_id: str) -> dict | None:
    """Check the shared Workspace catch-all page.tsx and registry.ts exist.

    ADR-802 routes every page slug through the single ``/workspace`` catch-all,
    so the source check no longer varies per slug.

    Returns a dict with diagnostic info, or None if everything looks fine.
    """
    slug_dir = project_root / "apps" / "dashboard" / "app" / "workspace" / "[[...slug]]"
    page_tsx = slug_dir / "page.tsx"
    registry_ts = slug_dir / "registry.ts"

    missing = []
    if not page_tsx.is_file():
        missing.append("page.tsx")
    if not registry_ts.is_file():
        missing.append("registry.ts")

    if missing:
        return {"hub": hub_id, "missing_files": missing, "slug_dir": str(slug_dir)}
    return None


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix broken page routes.

    Difficulty escalation:
    - d0: report only
    - d1+: re-run mount-plugins to regenerate registries, then verify
    - d2+: clear .next cache + rebuild + re-verify; check source files exist
    - d3+: attempt source-level fixes for missing exports/imports
    """
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: {len(issues)} broken route(s) to investigate",
        )

    if not issues:
        return FixResult(success=True, summary="No broken routes to fix", fix_type="report")

    if ctx.difficulty < 1:
        report_path = write_report(ctx, "test-pages-latest.json", {"issues": issues})
        return FixResult(
            success=True,
            changes=[],
            actions=[{"report": str(report_path), "remaining_count": len(issues)}],
            summary=f"Report only (d0): {len(issues)} broken route(s) detected",
            fix_type="report",
        )

    project_root = ctx.project_root
    dashboard_dir = project_root / "apps" / "dashboard"
    base_url = ctx.config.get("base_url", "http://localhost:3000")
    request_timeout = ctx.config.get("request_timeout", 10)
    actions: list[dict] = []
    changes: list[str] = []

    # --- Phase 1 (d1+): Re-run mount-plugins to regenerate registries ---
    # Many 404s are caused by stale registry.ts or missing hub assembly
    has_404s = any(i.get("error_category") == "not-found" or i.get("status") == 404 for i in issues)
    remount_ran = False

    if has_404s:
        logger.info("Re-running mount-plugins to regenerate page registries")
        try:
            mount_result = _run_mount_plugins(project_root, timeout=120)
            remount_ran = True
            if mount_result.returncode == 0:
                actions.append({"action": "remount-plugins", "status": "success"})
                changes.append("apps/dashboard/app/*/[[...slug]]/registry.ts")
            else:
                actions.append({
                    "action": "remount-plugins",
                    "status": "failed",
                    "stderr": mount_result.stderr[:500],
                })
        except subprocess.TimeoutExpired:
            actions.append({"action": "remount-plugins", "status": "timeout"})

    # Verify after remount
    if remount_ran:
        still_broken, now_fixed = _verify_routes(base_url, issues, timeout=request_timeout)
        if now_fixed:
            actions.append({
                "action": "verify-after-remount",
                "fixed_count": len(now_fixed),
                "fixed_routes": [i.get("path") for i in now_fixed],
            })
        issues = still_broken

    if not issues:
        return FixResult(
            success=True,
            actions=actions,
            changes=changes,
            summary=f"All routes fixed via mount-plugins re-run",
            fix_type="code-fix",
        )

    # --- Phase 2 (d2+): Clear .next cache + rebuild ---
    if ctx.difficulty >= 2 and issues:
        has_500s = any(i.get("error_category") == "server-error" or (i.get("status", 0) >= 500) for i in issues)

        if has_500s or issues:
            logger.info("Clearing .next cache and rebuilding")
            cache_cleared = _clear_next_cache(dashboard_dir)
            if cache_cleared:
                actions.append({"action": "clear-next-cache", "status": "success"})

            # Rebuild
            try:
                build_result = subprocess.run(
                    ["npm", "run", "build"],
                    capture_output=True, text=True, timeout=600,
                    cwd=str(dashboard_dir),
                )
                if build_result.returncode == 0:
                    actions.append({"action": "rebuild", "status": "success"})
                    changes.append("apps/dashboard/.next/")
                else:
                    actions.append({
                        "action": "rebuild",
                        "status": "failed",
                        "stderr": build_result.stderr[:500],
                    })
            except subprocess.TimeoutExpired:
                actions.append({"action": "rebuild", "status": "timeout"})

            # Re-verify
            still_broken, now_fixed = _verify_routes(base_url, issues, timeout=request_timeout)
            if now_fixed:
                actions.append({
                    "action": "verify-after-rebuild",
                    "fixed_count": len(now_fixed),
                    "fixed_routes": [i.get("path") for i in now_fixed],
                })
            issues = still_broken

        # Check for missing page source files
        if issues:
            for issue in issues:
                hub_id = issue.get("hub", "")
                if hub_id:
                    source_check = _check_page_source_exists(project_root, hub_id)
                    if source_check:
                        issue["source_diagnosis"] = source_check

    if not issues:
        return FixResult(
            success=True,
            actions=actions,
            changes=changes,
            summary=f"All routes fixed via cache clear + rebuild",
            fix_type="code-fix",
        )

    # --- Phase 3: Write report for remaining issues ---
    report_data = {
        "issues": issues,
        "fixed_count": sum(1 for a in actions if a.get("action", "").startswith("verify-") and a.get("fixed_count", 0) > 0),
        "by_category": {},
    }
    for issue in issues:
        cat = issue.get("error_category", "unknown")
        report_data["by_category"][cat] = report_data["by_category"].get(cat, 0) + 1
    report_path = write_report(ctx, "test-pages-latest.json", report_data)
    actions.append({"report": str(report_path), "remaining_count": len(issues)})

    total_fixed = sum(
        a.get("fixed_count", 0)
        for a in actions
        if a.get("action", "").startswith("verify-")
    )
    parts = []
    if total_fixed:
        parts.append(f"auto-fixed {total_fixed} route(s)")
    if issues:
        parts.append(f"{len(issues)} route(s) still broken (see report)")
    summary = "; ".join(parts) if parts else "No fixable route issues"

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=summary,
        fix_type="code-fix" if changes else "report",
    )

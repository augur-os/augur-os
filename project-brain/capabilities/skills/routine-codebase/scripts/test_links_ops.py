"""
auto-test-links — Broken link scanner for all dashboard pages.

Discovers ALL page routes from the filesystem, fetches each page,
extracts internal links, and tests them for 404s.

Difficulty levels:
  0: Verify the scanner script exists and dashboard is reachable
  1: Scan all static page routes for reachability (HEAD requests)
  2: Full scan — fetch each page, extract links, test all unique links
  3: Same as 2 with detailed per-page breakdown in report
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
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from src.config.paths import get_managed_skill_source_dirs, get_project_root
from src.lib.ops_protocol import (
    OpsContext,
    ScanResult,
    FixResult,
    clear_report,
    make_issue,
    find_page_routes,
    write_report,
)

name = "auto-test-links"

DASHBOARD_PROBE_ATTEMPTS = 3
DASHBOARD_PROBE_TIMEOUT_SECONDS = 2
DASHBOARD_PROBE_SLEEP_SECONDS = 2

DIFFICULTY_SPEC = {
    0: "Full scan — fetch all pages, extract links, test all unique links",
    1: "Full scan (same — scanner is fast enough at all levels)",
    2: "Full scan",
    3: "Full scan",
}

def _get_script_path() -> Path:
    """Resolve script path at call time, not import time (survives skill migration)."""
    return Path(__file__).resolve().parent / "check_links.mjs"


def _collect_auto_page_routes(project_root: Path) -> set[str]:
    """Collect routes for auto-pages that only exist at runtime (browse detail panel).

    These pages have page_type: auto in SKILL.md frontmatter and no physical page.tsx,
    so they legitimately 404 at build time and should be excluded from broken-link reports.
    Also includes hub routes that lack generated layout/page files.
    """
    import yaml as _yaml

    auto_routes: set[str] = set()
    for skills_dir in get_managed_skill_source_dirs(project_root):
        if not skills_dir.is_dir():
            continue
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            content = skill_md.read_text(errors="replace")
            if not content.startswith("---"):
                continue
            end = content.index("---", 3) if "---" in content[3:] else -1
            if end == -1:
                continue
            try:
                fm = _yaml.safe_load(content[3:end])
            except Exception:
                continue
            if not isinstance(fm, dict):
                continue

            hub = fm.get("x-augur-hub", "")
            config = fm.get("x-augur-config") or {}
            contribs = config.get("contributions", {}) if isinstance(config, dict) else {}
            pages = contribs.get("pages", []) if isinstance(contribs, dict) else []
            if not isinstance(pages, list):
                continue

            for page in pages:
                if not isinstance(page, dict):
                    continue
                page_type = page.get("page_type", "auto")
                if page_type == "auto":
                    page_id = page.get("id", "")
                    if page_id and hub:
                        auto_routes.add(f"/{hub}/{skill_dir.name}/{page_id}")
                        auto_routes.add(f"/productivity/{skill_dir.name}/{page_id}")

    # Also check for hub-level routes without generated dirs
    app_dir = project_root / "apps" / "dashboard" / "app"
    assembled = project_root / "apps" / "dashboard" / "lib" / "plugin-runtime" / "assembled-hubs.json"
    if assembled.exists():
        try:
            hubs = json.loads(assembled.read_text())
            for hub_name in hubs:
                hub_dir = app_dir / hub_name
                if not hub_dir.exists():
                    auto_routes.add(f"/{hub_name}")
        except Exception:
            pass

    return auto_routes


def _run_scanner(base_url: str = "http://localhost:3000", timeout: int = 8000) -> dict | None:
    """Run the Node.js scanner and return parsed JSON report."""
    import os
    import shutil

    node_bin = shutil.which("node")
    if not node_bin:
        return None

    env = {
        **os.environ,
        "BASE_URL": base_url,
        "REQUEST_TIMEOUT": str(timeout),
    }
    script = _get_script_path()
    try:
        result = subprocess.run(
            [node_bin, str(script), "--json"],
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            cwd=str(get_project_root()),
        )
        if result.returncode == 2:
            return None  # Script error
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def _is_dashboard_reachable(base_url: str) -> bool:
    """Probe stable dashboard surfaces before declaring the app unreachable.

    Next.js dev hot-reload cycles routinely take 1-3s, during which the dev
    server briefly rejects requests. Three attempts spaced 2s apart give the
    probe enough recovery window to avoid flapping false positives without
    making the scanner significantly slower in the truly-down case.
    """
    probe_paths = [
        "/api/settings/layout/pulse?mode=quick",
        "/api/activity/summary",
        "/api/mcp/summary",
        "/",
    ]

    # Next/Turbopack can keep the process alive while the port is briefly
    # unbound during compile. Keep this bounded so a down dashboard degrades
    # the scan quickly instead of stalling the full autoloop suite.
    for attempt in range(DASHBOARD_PROBE_ATTEMPTS):
        for probe_path in probe_paths:
            try:
                url = f"{base_url.rstrip('/')}{probe_path}"
                if not url.lower().startswith(("http://", "https://")):
                    raise ValueError(f"Non-HTTP URL rejected: {url!r}")
                urllib.request.urlopen(url, timeout=DASHBOARD_PROBE_TIMEOUT_SECONDS)  # nosec B310  # url scheme-validated above (http/https only)
                return True
            except urllib.error.HTTPError:
                return True
            except Exception:
                continue
        if attempt < DASHBOARD_PROBE_ATTEMPTS - 1:
            time.sleep(DASHBOARD_PROBE_SLEEP_SECONDS)

    return False


def scan(ctx: OpsContext) -> ScanResult:
    """Scan for broken links across all dashboard pages."""
    base_url = ctx.config.get("base_url", "http://localhost:3000")
    timeout = ctx.config.get("request_timeout", 8) * 1000

    # Pre-flight: verify script exists and dashboard is reachable
    script_path = _get_script_path()
    if not script_path.exists():
        return ScanResult(
            issues=[make_issue(
                category=name,
                detail=f"Scanner script missing: {script_path}",
                kind="broken",
                root_cause_type="repo_bug",
            )],
            summary="Scanner script not found",
            severity="error",
            health="broken",
        )

    if not _is_dashboard_reachable(base_url):
        return ScanResult(
            issues=[make_issue(
                category=name,
                detail=f"Dashboard not reachable at {base_url}",
                kind="environment",
                root_cause_type="env_runtime",
            )],
            summary="Dashboard not reachable",
            severity="warning",
            health="degraded",
        )

    # All difficulty levels: run the full scanner (cheap enough at ~30s)
    report = _run_scanner(base_url, timeout)
    if report is None:
        return ScanResult(
            issues=[make_issue(
                category=name,
                detail="Scanner script failed to execute",
                kind="scanner-defect",
                root_cause_type="scanner_bug",
            )],
            summary="Scanner execution failed",
            severity="error",
            health="broken",
        )

    s = report["summary"]
    issues = []

    # Build set of auto-page routes that only exist at runtime (browse detail panel).
    # These 404 at build time and are not real broken links.
    auto_page_routes = _collect_auto_page_routes(ctx.project_root)

    # Unreachable pages
    for p in report.get("unreachable_pages", []):
        route = p["route"]
        if route in auto_page_routes or any(route.startswith(r + "/") for r in auto_page_routes):
            continue
        issues.append(make_issue(
            category=name,
            detail=f"Page returns {p['status']}: {route}",
            path=route,
            kind="actionable",
            root_cause_type="repo_bug",
            fixability="manual",
        ))

    # Broken links (unique)
    for b in report.get("unique_broken_links", []):
        link = b["link"]
        if link in auto_page_routes or any(link.startswith(r + "/") for r in auto_page_routes):
            continue
        issues.append(make_issue(
            category=name,
            detail=f"Link returns {b['status']}: {link}",
            path=link,
            kind="actionable",
            root_cause_type="repo_bug",
            fixability="manual",
        ))

    if issues:
        severity = "warning"
        health = "degraded"
        summary = (
            f"{s['pages_scanned']} pages, {s['unique_links']} links — "
            f"{s['pages_unreachable']} unreachable pages, "
            f"{s['unique_broken']} broken links ({s['broken_pct']}%)"
        )
    else:
        clear_report("test-links-latest.json")
        severity = "info"
        health = "verified"
        summary = (
            f"{s['pages_scanned']} pages, {s['unique_links']} links — "
            f"all OK"
        )

    return ScanResult(issues=issues, summary=summary, severity=severity, health=health)


# ---------------------------------------------------------------------------
# Auto-fix helpers
# ---------------------------------------------------------------------------

_LINK_RE = re.compile(r'href="([^"]+)"')


def _build_route_map(project_root: Path) -> dict[str, str]:
    """Build a map from route basename to full route path for redirect detection.

    For example, if /adaptive/overview exists, maps "overview" -> "/adaptive/overview"
    and "adaptive/overview" -> "/adaptive/overview".
    """
    routes = find_page_routes(project_root)
    route_map: dict[str, str] = {}
    for route in routes:
        # Map the full route
        route_map[route.lstrip("/")] = route
        # Map just the last segment (for simple renames)
        segments = route.strip("/").split("/")
        if len(segments) >= 1:
            basename = segments[-1]
            # Only map basename if unambiguous (first wins, skip conflicts)
            if basename and basename not in route_map:
                route_map[basename] = route
    return route_map


def _find_redirect_target(broken_link: str, route_map: dict[str, str]) -> str | None:
    """Try to find where a broken link should redirect to.

    Strategies:
    1. Exact basename match (e.g. /old/foo -> /new/foo)
    2. Segment match (e.g. /hub/old-page -> /hub/new-page if only one page in hub)
    """
    clean = broken_link.strip("/").split("?")[0].split("#")[0]
    if not clean:
        return None

    # Strategy 1: full path exists at different location
    segments = clean.split("/")
    basename = segments[-1] if segments else ""

    # Check if basename matches exactly one route
    if basename and basename in route_map:
        candidate = route_map[basename]
        if candidate != broken_link:
            return candidate

    # Strategy 2: try matching with the last two segments
    if len(segments) >= 2:
        suffix = "/".join(segments[-2:])
        if suffix in route_map:
            candidate = route_map[suffix]
            if candidate != broken_link:
                return candidate

    return None


def _fix_broken_link_in_source(
    project_root: Path,
    broken_link: str,
    new_link: str,
) -> list[str]:
    """Find and fix references to a broken link in page source files.

    Returns list of files modified.
    """
    modified: list[str] = []
    app_dir = project_root / "apps" / "dashboard" / "app"
    if not app_dir.exists():
        return modified

    # Also check skill source directories for dashboard pages
    search_dirs = [app_dir]
    skills_dashboard = project_root / ".claude" / "skills"
    if skills_dashboard.is_dir():
        for skill_dir in skills_dashboard.iterdir():
            dash_dir = skill_dir / "augur" / "dashboard"
            if dash_dir.is_dir():
                search_dirs.append(dash_dir)
    plugins_dir = project_root / "plugins"
    if plugins_dir.is_dir():
        for bundle_dir in plugins_dir.iterdir():
            for skill_dir in (bundle_dir / "skills").iterdir() if (bundle_dir / "skills").is_dir() else []:
                dash_dir = skill_dir / "augur" / "dashboard"
                if dash_dir.is_dir():
                    search_dirs.append(dash_dir)

    for search_dir in search_dirs:
        for tsx_file in search_dir.rglob("*.tsx"):
            try:
                content = tsx_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            if broken_link not in content:
                continue

            # Replace href="broken" with href="new"
            updated = content.replace(f'"{broken_link}"', f'"{new_link}"')
            # Also handle single-quoted hrefs
            updated = updated.replace(f"'{broken_link}'", f"'{new_link}'")
            # Handle template literals
            updated = updated.replace(f"`{broken_link}`", f"`{new_link}`")

            if updated != content:
                tsx_file.write_text(updated, encoding="utf-8")
                try:
                    rel = str(tsx_file.relative_to(project_root))
                except ValueError:
                    rel = str(tsx_file)
                modified.append(rel)

    return modified


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Auto-fix broken links where target page exists at a different path.

    For each broken link, checks if a page with the same basename exists
    at a different route. If found, updates all source references.
    Remaining issues are written to a report.
    """
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: {len(issues)} broken link(s) to investigate",
        )

    if not issues:
        return FixResult(success=True, summary="No broken links to fix", fix_type="report")

    route_map = _build_route_map(ctx.project_root)
    changes: list[str] = []
    actions: list[dict] = []
    unfixed: list[dict] = []

    for issue in issues:
        link = issue.get("path", "")
        if not link:
            unfixed.append(issue)
            continue

        # Try to find a redirect target
        new_target = _find_redirect_target(link, route_map)
        if new_target:
            modified_files = _fix_broken_link_in_source(ctx.project_root, link, new_target)
            if modified_files:
                actions.append({
                    "fixed": link,
                    "redirected_to": new_target,
                    "files_modified": modified_files,
                })
                changes.extend(modified_files)
            else:
                # Found a target but no source files reference the broken link
                unfixed.append({
                    **issue,
                    "suggestion": f"Could redirect to {new_target} but no source files found with this href",
                })
        else:
            unfixed.append(issue)

    # Write report for unfixed issues
    if unfixed:
        report_data = {
            "unfixed_issues": unfixed,
            "fixed_count": len(actions),
        }
        report_path = write_report(ctx, "test-links-latest.json", report_data)
        actions.append({"report": str(report_path), "unfixed_count": len(unfixed)})

    # Summary
    parts = []
    if actions and any("fixed" in a for a in actions):
        fix_count = sum(1 for a in actions if "fixed" in a)
        parts.append(f"auto-fixed {fix_count} broken link(s)")
    if unfixed:
        parts.append(f"{len(unfixed)} issue(s) need manual investigation (see report)")
    summary = "; ".join(parts) if parts else "No fixable issues"

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=summary,
        fix_type="code-fix" if changes else ("report" if unfixed else "verified"),
    )

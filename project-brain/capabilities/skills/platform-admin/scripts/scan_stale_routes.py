"""auto-stale-routes: Scan dashboard hook URLs for missing API route files.

Finds all /api/ URL string literals in .ts/.tsx files across plugins/ and
apps/dashboard/ that use useCachedFetch, useCachedPoll, useCachedMutation,
useAction, or useCachedSearch hooks, then verifies that a corresponding
route.ts file exists under apps/dashboard/app/.

Part of ADR-269 Phase 3.
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
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from src.config.paths import get_all_client_skill_dirs, get_project_root

# Hook function names whose files we scan
HOOK_NAMES = [
    "useCachedFetch",
    "useCachedPoll",
    "useCachedMutation",
    "useAction",
    "useCachedSearch",
]

# Regex to extract /api/... URL literals from source lines
API_URL_RE = re.compile(r"""['"](/api/[^'"]+)['"]""")


def _get_dashboard_app_dir(project_root: Path) -> Path:
    """Return the canonical dashboard app root."""
    return project_root / "apps" / "dashboard" / "app"


def _known_api_routes(project_root: Path, shared_snapshot: dict | None = None) -> set[str]:
    """Return known API routes from shared snapshot or filesystem."""
    if shared_snapshot:
        routes = shared_snapshot.get("api_routes")
        if isinstance(routes, list):
            return {
                route.rstrip("/")
                for route in routes
                if isinstance(route, str) and route
            }

    api_root = _get_dashboard_app_dir(project_root) / "api"
    known: set[str] = set()
    if not api_root.exists():
        return known
    for route_file in api_root.rglob("route.ts"):
        rel = route_file.parent.relative_to(_get_dashboard_app_dir(project_root)).as_posix()
        known.add(f"/{rel}".rstrip("/"))
    for route_file in api_root.rglob("route.js"):
        rel = route_file.parent.relative_to(_get_dashboard_app_dir(project_root)).as_posix()
        known.add(f"/{rel}".rstrip("/"))
    return known


def _find_files_using_hooks(project_root: Path) -> set[str]:
    """Find all .ts/.tsx files that import or call any of the hook functions."""
    search_dirs = [
        str(d) for d in get_all_client_skill_dirs(project_root)
    ] + [
        str(project_root / "apps" / "dashboard"),
    ]
    hook_pattern = "|".join(HOOK_NAMES)
    try:
        cmd = [
            "rg",
            "--files-with-matches",
            "--glob", "*.ts",
            "--glob", "*.tsx",
            f"({hook_pattern})",
            *search_dirs,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return set(proc.stdout.strip().splitlines()) if proc.stdout.strip() else set()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return set()


def _extract_api_urls_from_file(file_path: str) -> list[tuple[str, int]]:
    """Extract all /api/ URL literals from a file.

    Returns list of (url, line_number) tuples.
    """
    results: list[tuple[str, int]] = []
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            for line_no, line in enumerate(f, 1):
                for match in API_URL_RE.finditer(line):
                    url = match.group(1)
                    results.append((url, line_no))
    except OSError:
        pass
    return results


def _determine_hook_name(file_path: str, url: str) -> str:
    """Best-effort: determine which hook uses a given URL by scanning context."""
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return "unknown"

    # Find all hook calls and check if URL appears nearby
    for hook in HOOK_NAMES:
        if hook in content and url in content:
            return hook
    return "unknown"


def _normalize_url(url: str) -> str | None:
    """Strip query params and return None for dynamic/template URLs."""
    if "${" in url or "`" in url:
        return None

    # Strip query params
    url = url.split("?")[0]

    # Strip trailing slash
    url = url.rstrip("/")

    return url if url else None


def _check_route_exists(
    project_root: Path,
    api_path: str,
    shared_snapshot: dict | None = None,
) -> bool:
    """Check if a route.ts file exists for the given API path.

    /api/foo/bar -> apps/dashboard/app/api/foo/bar/route.ts
    Also checks route.js and dynamic [param] segments.
    """
    if api_path.rstrip("/") in _known_api_routes(project_root, shared_snapshot):
        return True

    relative = api_path.lstrip("/")
    dashboard_app_dir = _get_dashboard_app_dir(project_root)
    route_dir = dashboard_app_dir / relative

    for ext in ("route.ts", "route.js"):
        if (route_dir / ext).exists():
            return True

    parts = relative.split("/")
    return _check_dynamic_route(dashboard_app_dir, parts, 0)


def _check_dynamic_route(base: Path, parts: list[str], idx: int) -> bool:
    """Recursively check if a dynamic route segment matches."""
    if idx >= len(parts):
        for ext in ("route.ts", "route.js"):
            if (base / ext).exists():
                return True
        return False

    segment = parts[idx]

    # Try exact match first
    exact = base / segment
    if exact.is_dir():
        if _check_dynamic_route(exact, parts, idx + 1):
            return True

    # Try dynamic segments [param], [...param], [[...param]]
    if base.is_dir():
        try:
            for child in base.iterdir():
                if child.is_dir() and child.name.startswith("[") and child.name.endswith("]"):
                    if _check_dynamic_route(child, parts, idx + 1):
                        return True
        except OSError:
            pass

    return False


def scan_stale_routes(
    project_root: Path,
    shared_snapshot: dict | None = None,
    verbose: bool = False,
) -> list[dict]:
    """Scan for hook URLs with no matching route file.

    Returns list of dicts with keys: url, file, line, hook.
    """
    # Step 1: Find files that use any of the cached fetch hooks
    hook_files = _find_files_using_hooks(project_root)
    if verbose:
        print(f"Found {len(hook_files)} files using cached fetch hooks")

    # Step 2: Extract all /api/ URLs from those files
    url_sources: dict[str, list[tuple[str, int, str]]] = {}
    for file_path in sorted(hook_files):
        raw_urls = _extract_api_urls_from_file(file_path)
        for url, line_no in raw_urls:
            normalized = _normalize_url(url)
            if normalized is None:
                if verbose:
                    print(f"  SKIP (dynamic): {url} in {file_path}:{line_no}")
                continue
            hook_name = _determine_hook_name(file_path, url)
            url_sources.setdefault(normalized, []).append((file_path, line_no, hook_name))

    if verbose:
        print(f"Found {len(url_sources)} unique static API URLs from hook files")

    # Step 3: Check each URL for a matching route file
    missing: list[dict] = []
    for url, sources in sorted(url_sources.items()):
        if not _check_route_exists(project_root, url, shared_snapshot):
            for file_path, line_no, hook_name in sources:
                rel_path = os.path.relpath(file_path, project_root)
                missing.append({
                    "url": url,
                    "file": rel_path,
                    "line": line_no,
                    "hook": hook_name,
                })
                if verbose:
                    print(f"  MISSING: {url} <- {rel_path}:{line_no} ({hook_name})")
        elif verbose:
            print(f"  OK: {url}")

    return missing


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan dashboard hook URLs for missing API route files",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output for each URL checked",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    project_root = get_project_root()
    missing = scan_stale_routes(project_root, verbose=args.verbose)

    if args.json_output:
        print(json.dumps({"missing_routes": missing, "count": len(missing)}, indent=2))
    elif missing:
        print(f"\n{len(missing)} stale route reference(s) found:\n")
        for entry in missing:
            print(f"  {entry['url']}")
            print(f"    <- {entry['file']}:{entry['line']} ({entry['hook']})")
        print(f"\nTotal: {len(missing)} missing route(s)")
    else:
        print("All hook URLs have matching route files.")

    return 1 if missing else 0


# ── Ops protocol interface (for adaptive loop engine) ────────────────────────

name = "auto-stale-routes"


def scan(ctx: object) -> object:
    """Ops protocol scan entry point."""
    from src.lib.ops_protocol import ScanResult

    project_root = getattr(ctx, "project_root", None) or get_project_root()
    shared_snapshot = getattr(ctx, "shared_snapshot", None)
    missing = scan_stale_routes(project_root, shared_snapshot=shared_snapshot)
    issues = [
        {
            "id": f"stale-route-{i}",
            "severity": "warning",
            "message": f"Missing route for {m['url']} (referenced in {m['file']}:{m['line']})",
            "file": m["file"],
            "line": m["line"],
            "url": m["url"],
        }
        for i, m in enumerate(missing)
    ]
    return ScanResult(
        issues=issues,
        summary=f"Found {len(missing)} stale route reference(s)" if missing
        else "All hook URLs have matching route files",
        severity="warning" if missing else "info",
    )


def fix(ctx: object, issues: list[dict]) -> object:
    """Ops protocol fix entry point (report-only, no auto-fix)."""
    from src.lib.ops_protocol import FixResult

    if not issues:
        return FixResult(success=True, summary="No stale routes to fix")
    return FixResult(
        success=True,
        summary=f"Reported {len(issues)} stale route(s) — manual fix required",
    )


if __name__ == "__main__":
    sys.exit(main())

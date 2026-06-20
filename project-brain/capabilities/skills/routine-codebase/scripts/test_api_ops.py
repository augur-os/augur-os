"""auto-test-api: API route health validation with hub scoping and auto-fix."""
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
import re
from pathlib import Path

from src.lib.ops_protocol import (
    OpsContext,
    ScanResult,
    FixResult,
    check_http_route,
    write_report,
)

name = "auto-test-api"
DIFFICULTY_SPEC = {
    0: "Surface check — discover static API routes without probing the live dashboard",
    1: "Content check — probe dashboard health and static API routes",
    2: "Deep check — same as d1 plus source-level root-cause classification",
    3: "Exhaustive — same as d2 (API route validation)",
    4: "Expert — same as d2 (API route validation)",
}

_HTTP_METHOD_RE = re.compile(
    r"export\s+(?:async\s+function|const)\s+(GET|POST|PUT|PATCH|DELETE)\b"
)

# ---------------------------------------------------------------------------
# Pattern detection regexes for root-cause classification
# ---------------------------------------------------------------------------

# Stale plugins/ Python script paths inside route.ts string literals
# e.g. "plugins/observability/skills/example/scripts/foo.py"
_STALE_PLUGIN_PATH_RE = re.compile(
    r"""(?P<quote>['"`])"""
    r"""(?P<path>plugins/(?P<bundle>[a-z_-]+)/skills/(?P<skill>[a-z_-]+)/scripts/(?P<script>[^'"`]+))"""
    r"""(?P=quote)"""
)

# Stale Python imports from plugins.* package tree
# e.g. "from plugins.observability.skills.example.scripts.foo import bar"
_STALE_PLUGIN_IMPORT_RE = re.compile(
    r"""(?P<quote>['"`])"""
    r"""from\s+plugins\.(?P<bundle>[a-z_-]+)\.skills\.(?P<skill>[a-z_-]+)\.(?P<rest>[^'"`]+?)"""
    r"""\s+import\s+[^'"`]+"""
    r"""(?P=quote)"""
)

# runPythonScript / runPythonCode direct calls (Rule #11 violation)
_PYTHON_RUNNER_RE = re.compile(r"\brunPython(?:Script|Code)\b")

# gracefulFallback masking MCP failures
_GRACEFUL_FALLBACK_RE = re.compile(r"gracefulFallback\s*:\s*\{[^}]*enabled\s*:\s*true", re.DOTALL)


def _check_tool_registration(project_root: Path, tool_name: str) -> bool:
    """Check if an MCP tool is registered in any Python MCP server file.

    Searches for @mcp.tool(name="...") patterns and def function name patterns
    in the src/mcp/ directory tree.
    """
    mcp_dirs = [
        project_root / "src" / "mcp",
        project_root / "src" / "mcp" / "tools",
    ]

    for mcp_dir in mcp_dirs:
        if not mcp_dir.is_dir():
            continue
        for py_file in mcp_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if f'name="{tool_name}"' in content or f"name='{tool_name}'" in content:
                return True
            normalized = tool_name.replace("-", "_")
            if f"def {normalized}(" in content:
                return True

    return False


def _exported_methods(route_file: Path) -> set[str]:
    """Return the set of HTTP methods exported by a route.ts file."""
    try:
        text = route_file.read_text(encoding="utf-8")
    except OSError:
        return set()
    return set(_HTTP_METHOD_RE.findall(text))


def _route_file_for(project_root: Path, url_path: str) -> Path:
    """Map a URL path like /api/foo/bar back to its route.ts on disk."""
    rel = url_path.lstrip("/")
    return project_root / "apps" / "dashboard" / "app" / rel / "route.ts"


def _discover_api_routes(
    project_root: Path,
    hub: str | None = None,
    shared_snapshot: dict | None = None,
) -> list[str]:
    """Convert route.ts files to API URL paths."""
    if shared_snapshot:
        snapshot_routes = shared_snapshot.get("api_routes")
        if isinstance(snapshot_routes, list):
            routes = [
                route for route in snapshot_routes
                if isinstance(route, str) and "[" not in route
            ]
            if hub:
                prefix = f"/api/{hub}/"
                routes = [
                    route for route in routes
                    if route == f"/api/{hub}" or route.startswith(prefix)
                ]
            return sorted(set(routes))

    api_dir = project_root / "apps" / "dashboard" / "app" / "api"
    if not api_dir.exists():
        return []

    search_dir = api_dir / hub if hub else api_dir
    if not search_dir.exists():
        return []

    routes = []
    for route_file in sorted(search_dir.rglob("route.ts")):
        rel = route_file.parent.relative_to(project_root / "apps" / "dashboard" / "app")
        url_path = "/" + str(rel).replace("\\", "/")
        # Skip dynamic segments like [id] for automated testing
        if "[" not in url_path:
            routes.append(url_path)
    return routes


# ---------------------------------------------------------------------------
# Root-cause classification
# ---------------------------------------------------------------------------

def _classify_issue(project_root: Path, route: str, http_result: dict) -> dict:
    """Analyze route.ts source to classify the root cause and fixability.

    Returns a dict with:
      - route, status, error (from HTTP probe)
      - pattern: detected failure pattern name
      - fixability: "auto" | "manual" | "unknown"
      - message: human-readable description
      - route_file: absolute path to route.ts
      - fix_detail: data needed by fix() to apply the repair
    """
    route_file = _route_file_for(project_root, route)
    base = {
        "route": route,
        "status": http_result.get("status"),
        "error": http_result.get("error", ""),
        "route_file": str(route_file),
    }

    try:
        source = route_file.read_text(encoding="utf-8")
    except OSError:
        return {
            **base,
            "pattern": "missing-source",
            "fixability": "manual",
            "message": f"route.ts not found at {route_file}",
        }

    # Pattern A: stale plugins/ script path
    match = _STALE_PLUGIN_PATH_RE.search(source)
    if match:
        old_path = match.group("path")
        skill = match.group("skill")
        script = match.group("script")
        new_path = f"project-brain/capabilities/skills/{skill}/scripts/{script}"
        candidate = project_root / new_path
        if candidate.exists():
            return {
                **base,
                "pattern": "stale-plugin-path",
                "fixability": "auto",
                "message": f"Stale plugins/ path: {old_path} -> {new_path}",
                "fix_detail": {"old_path": old_path, "new_path": new_path},
            }
        return {
            **base,
            "pattern": "stale-plugin-path-no-target",
            "fixability": "manual",
            "message": f"Stale plugins/ path {old_path} and no project-brain/capabilities/skills equivalent found",
        }

    # Pattern B: stale plugins.* Python import strings
    match = _STALE_PLUGIN_IMPORT_RE.search(source)
    if match:
        skill = match.group("skill")
        return {
            **base,
            "pattern": "stale-plugin-import",
            "fixability": "manual",
            "message": f"Stale plugins.* Python import string for skill '{skill}'",
        }

    # Pattern C: runPythonScript / runPythonCode bypass (Rule #11)
    if _PYTHON_RUNNER_RE.search(source):
        return {
            **base,
            "pattern": "python-runner-bypass",
            "fixability": "manual",
            "message": "Route uses runPythonScript/runPythonCode instead of MCP (Rule #11)",
        }

    # Pattern D: gracefulFallback masking a real MCP error
    if _GRACEFUL_FALLBACK_RE.search(source):
        return {
            **base,
            "pattern": "graceful-fallback-masking",
            "fixability": "manual",
            "message": "Route has gracefulFallback enabled — may mask real MCP failures",
        }

    # Pattern E: MCP toolName wiring — check if toolName in route matches a registered tool
    tool_match = re.search(r"""toolName\s*:\s*['"]([^'"]+)['"]""", source)
    if tool_match:
        tool_name = tool_match.group(1)
        registered = _check_tool_registration(project_root, tool_name)
        if not registered:
            return {
                **base,
                "pattern": "unregistered-tool",
                "fixability": "manual",
                "message": (
                    f"Route references MCP tool '{tool_name}' which is not registered "
                    f"in any @mcp.tool() decorator. Either register the tool or fix the toolName."
                ),
                "fix_detail": {"tool_name": tool_name},
            }
        # Tool is registered but route still fails — likely an environment issue
        # (MCP server not running, tool throws at runtime)
        status = http_result.get("status")
        if status == 502:
            return {
                **base,
                "pattern": "tool-registered-but-502",
                "fixability": "environment",
                "message": (
                    f"MCP tool '{tool_name}' is registered but returned 502 — "
                    f"MCP server may need restart"
                ),
                "fix_detail": {"tool_name": tool_name},
            }
        if status and status >= 500:
            return {
                **base,
                "pattern": "tool-runtime-error",
                "fixability": "manual",
                "message": (
                    f"MCP tool '{tool_name}' is registered but route returned {status} — "
                    f"tool may throw at runtime. Check tool implementation."
                ),
                "fix_detail": {"tool_name": tool_name},
            }

    # Unknown pattern
    return {
        **base,
        "pattern": "unknown",
        "fixability": "unknown",
        "message": f"Route returned HTTP {http_result.get('status')} — root cause unclear",
    }


# ---------------------------------------------------------------------------
# scan()
# ---------------------------------------------------------------------------

def scan(ctx: OpsContext) -> ScanResult:
    hub = ctx.config.get("hub")
    base_url = ctx.config.get("base_url", "http://localhost:3000")
    timeout = ctx.config.get("request_timeout", 10)
    scope = f" for {hub}" if hub else ""

    routes = _discover_api_routes(ctx.project_root, hub=hub, shared_snapshot=ctx.shared_snapshot)

    # API route health is critical when explicitly configured at d1+, but keep
    # the d0 surface pass reachable when no minimum is enforced.
    effective_difficulty = max(ctx.difficulty, int(ctx.config.get("min_difficulty", 0)))

    if effective_difficulty < 1:
        if not routes:
            return ScanResult(issues=[], summary=f"No API routes found{scope}", severity="info")
        return ScanResult(
            issues=[],
            summary=f"Discovered {len(routes)} static API route(s){scope} (d0 surface)",
            severity="info",
            health="verified",
        )

    # Pre-check: is the dashboard reachable?
    probe = check_http_route(base_url, timeout=3)
    if not probe.get("ok"):
        return ScanResult(issues=[], summary="Dashboard not running — skipping API route checks", severity="info")

    if not routes:
        return ScanResult(issues=[], summary=f"No API routes found{scope}", severity="info")
    issues: list[dict] = []
    slow_routes: list[dict] = []
    post_only_skipped = 0
    param_required_skipped = 0

    for route in routes:
        url = f"{base_url}{route}"
        result = check_http_route(url, timeout=timeout)
        if not result.get("ok"):
            status = result.get("status")

            # 400 Bad Request means the route exists but needs query params
            # or a request body. That's healthy, not broken.
            if status == 400:
                param_required_skipped += 1
                continue

            # A 405 from a route that has no GET export is expected, not broken.
            if status == 405:
                route_file = _route_file_for(ctx.project_root, route)
                methods = _exported_methods(route_file)
                # If we found exported methods and GET is not among them,
                # or if no route file exists (mounted/generated), skip it.
                if not methods or "GET" not in methods:
                    post_only_skipped += 1
                    continue

            # Timeout (no status code) — classify as slow, not broken.
            if status is None:
                slow_routes.append({"route": route, **result})
                continue

            # Classify the root cause from source analysis
            if effective_difficulty >= 2:
                classified = _classify_issue(ctx.project_root, route, result)
            else:
                classified = {"route": route, **result}
            issues.append(classified)

    notes: list[str] = []
    if post_only_skipped:
        notes.append(f"{post_only_skipped} non-GET routes skipped")
    if param_required_skipped:
        notes.append(f"{param_required_skipped} param-required routes skipped")
    if slow_routes:
        notes.append(f"{len(slow_routes)} slow/timeout routes")
    skip_note = f" ({', '.join(notes)})" if notes else ""

    if not issues:
        return ScanResult(issues=[], summary=f"All {len(routes)} API routes OK{scope}{skip_note}", severity="info")

    auto_count = sum(1 for i in issues if i.get("fixability") == "auto")
    manual_count = sum(1 for i in issues if i.get("fixability") == "manual")
    fix_note = ""
    if auto_count or manual_count:
        parts = []
        if auto_count:
            parts.append(f"{auto_count} auto-fixable")
        if manual_count:
            parts.append(f"{manual_count} manual")
        fix_note = f" [{', '.join(parts)}]"

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)}/{len(routes)} API route(s) failed{scope}{skip_note}{fix_note}",
        severity="error",
    )


# ---------------------------------------------------------------------------
# Auto-fix implementations
# ---------------------------------------------------------------------------

def _fix_stale_plugin_path(project_root: Path, issue: dict) -> dict:
    """Replace a stale plugins/ path string with the project-brain/capabilities/skills equivalent.

    Returns an action dict describing what was done.
    """
    route_file = Path(issue["route_file"])
    detail = issue.get("fix_detail", {})
    old_path = detail.get("old_path", "")
    new_path = detail.get("new_path", "")

    if not old_path or not new_path:
        return {"skipped": str(route_file), "reason": "missing fix_detail"}

    try:
        source = route_file.read_text(encoding="utf-8")
    except OSError as exc:
        return {"failed": str(route_file), "reason": str(exc)}

    if old_path not in source:
        return {"skipped": str(route_file), "reason": "old path no longer in source"}

    updated = source.replace(old_path, new_path)
    try:
        route_file.write_text(updated, encoding="utf-8")
    except OSError as exc:
        return {"failed": str(route_file), "reason": str(exc)}

    return {
        "fixed": str(route_file),
        "pattern": "stale-plugin-path",
        "old_path": old_path,
        "new_path": new_path,
    }


# ---------------------------------------------------------------------------
# fix()
# ---------------------------------------------------------------------------

def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix broken API routes.

    Auto-fixable patterns are repaired in-place:
      - stale-plugin-path: replaces plugins/*/skills/*/scripts/* with project-brain/capabilities/skills/*/scripts/*

    All other patterns are written to a report for manual resolution.
    """
    if ctx.dry_run:
        auto = [i for i in issues if i.get("fixability") == "auto"]
        manual = [i for i in issues if i.get("fixability") != "auto"]
        parts = []
        if auto:
            parts.append(f"{len(auto)} auto-fixable")
        if manual:
            parts.append(f"{len(manual)} manual")
        return FixResult(
            success=True,
            summary=f"Dry run: {', '.join(parts) if parts else f'{len(issues)} issue(s)'}",
        )

    auto_issues = [i for i in issues if i.get("fixability") == "auto"]
    manual_issues = [i for i in issues if i.get("fixability") != "auto"]

    changes: list[str] = []
    actions: list[dict] = []

    # --- Auto-fix pass ---
    for issue in auto_issues:
        pattern = issue.get("pattern", "")
        if pattern == "stale-plugin-path":
            action = _fix_stale_plugin_path(ctx.project_root, issue)
        else:
            action = {"skipped": issue.get("route", ""), "reason": f"no auto-fixer for pattern '{pattern}'"}

        actions.append(action)
        if "fixed" in action:
            changes.append(action["fixed"])

    # --- Separate environment issues from code bugs ---
    env_issues = [i for i in manual_issues if i.get("fixability") == "environment"]
    code_issues = [i for i in manual_issues if i.get("fixability") != "environment"]

    # --- Report pass for all non-auto issues with actionable fix instructions ---
    all_report_issues = code_issues + env_issues
    if all_report_issues:
        enriched_issues = []
        for issue in all_report_issues:
            enriched = dict(issue)
            pattern = issue.get("pattern", "")
            route = issue.get("route", "")
            route_file = issue.get("route_file", "")

            # Add pattern-specific fix instructions
            if pattern == "stale-plugin-path-no-target":
                enriched["fix_instruction"] = (
                    f"The route references a plugins/ script path that no longer exists, "
                    f"and no project-brain/capabilities/skills equivalent was found. "
                    f"Either migrate the script to project-brain/capabilities/skills/ or update the route to use MCP tools. "
                    f"File: {route_file}"
                )
                enriched["fix_class"] = "code_bug"
            elif pattern == "stale-plugin-import":
                enriched["fix_instruction"] = (
                    f"The route contains a Python import string using the old plugins.* namespace. "
                    f"Update to use MCP tool calls instead of direct Python imports (Rule #11). "
                    f"File: {route_file}"
                )
                enriched["fix_class"] = "code_bug"
            elif pattern == "python-runner-bypass":
                enriched["fix_instruction"] = (
                    f"Route {route} uses runPythonScript/runPythonCode instead of MCP (Rule #11). "
                    f"Replace with an MCP tool call via the augur MCP server. "
                    f"1. Find the Python function being called "
                    f"2. Register it as an MCP tool in src/mcp/ "
                    f"3. Update the route to call the MCP tool. "
                    f"File: {route_file}"
                )
                enriched["fix_class"] = "code_bug"
            elif pattern == "graceful-fallback-masking":
                enriched["fix_instruction"] = (
                    f"Route {route} has gracefulFallback enabled which may mask real MCP failures. "
                    f"1. Temporarily disable gracefulFallback "
                    f"2. Check if the MCP tool call actually works "
                    f"3. Fix the MCP wiring if it fails "
                    f"4. Only re-enable gracefulFallback for genuine infrastructure failures. "
                    f"File: {route_file}"
                )
                enriched["fix_class"] = "code_bug"
            elif pattern == "unregistered-tool":
                tool_name = issue.get("fix_detail", {}).get("tool_name", "?")
                enriched["fix_instruction"] = (
                    f"Route {route} references MCP tool '{tool_name}' which is not registered. "
                    f"1. Check if the tool exists under a different name in src/mcp/ "
                    f"2. If not, register it as an @mcp.tool in src/mcp/ "
                    f"3. If the tool was removed intentionally, update the route's toolName. "
                    f"File: {route_file}"
                )
                enriched["fix_class"] = "wiring_bug"
            elif pattern == "tool-registered-but-502":
                enriched["fix_instruction"] = (
                    f"Route {route} tool is registered but MCP server returned 502. "
                    f"This is an environment issue — restart the MCP server. "
                    f"If it persists, check the tool's Python code for import errors."
                )
                enriched["fix_class"] = "environment"
            elif pattern == "tool-runtime-error":
                tool_name = issue.get("fix_detail", {}).get("tool_name", "?")
                enriched["fix_instruction"] = (
                    f"Route {route} tool '{tool_name}' is registered but throws at runtime. "
                    f"Check the tool implementation in src/mcp/ for exceptions. "
                    f"Common causes: missing data files, unhandled None, stale imports. "
                    f"File: {route_file}"
                )
                enriched["fix_class"] = "code_bug"
            elif pattern == "missing-source":
                enriched["fix_instruction"] = (
                    f"No route.ts file found at {route_file}. "
                    f"The route may have been moved or deleted. "
                    f"Check if the page still references this API route and update accordingly."
                )
                enriched["fix_class"] = "code_bug"
            else:
                enriched["fix_instruction"] = (
                    f"Route {route} returned HTTP {issue.get('status')} — root cause unclear. "
                    f"Run a wiring audit: grep the toolName in the route against @mcp.tool registrations. "
                    f"File: {route_file}"
                )
                enriched["fix_class"] = "unknown"

            enriched_issues.append(enriched)

        # Separate by fix_class for structured report
        code_bugs = [i for i in enriched_issues if i.get("fix_class") in ("code_bug", "wiring_bug")]
        env_only = [i for i in enriched_issues if i.get("fix_class") == "environment"]
        unknown = [i for i in enriched_issues if i.get("fix_class") == "unknown"]

        report_data = {
            "issues": enriched_issues,
            "code_bugs": code_bugs,
            "environment_issues": env_only,
            "unknown_issues": unknown,
            "fix_summary": {
                "total": len(enriched_issues),
                "code_bugs": len(code_bugs),
                "environment": len(env_only),
                "unknown": len(unknown),
                "by_pattern": {},
            },
        }
        # Aggregate by pattern for quick triage
        for issue in enriched_issues:
            p = issue.get("pattern", "unknown")
            report_data["fix_summary"]["by_pattern"][p] = (
                report_data["fix_summary"]["by_pattern"].get(p, 0) + 1
            )

        report_path = write_report(ctx, "test-api-latest.json", report_data)
        actions.append({"report": str(report_path), "manual_issues": len(code_issues), "env_issues": len(env_issues)})

    # --- Summary ---
    parts = []
    if changes:
        parts.append(f"auto-fixed {len(changes)} route(s)")
    if code_issues:
        patterns = {}
        for i in code_issues:
            p = i.get("pattern", "unknown")
            patterns[p] = patterns.get(p, 0) + 1
        pattern_breakdown = ", ".join(f"{count} {p}" for p, count in sorted(patterns.items()))
        parts.append(f"{len(code_issues)} code bug(s): {pattern_breakdown}")
    if env_issues:
        parts.append(f"{len(env_issues)} environment issue(s) (not actionable)")
    summary = "; ".join(parts) if parts else "No fixable issues"

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=summary,
        fix_type="code-fix" if changes else ("verified" if (code_issues or env_issues) else "report"),
    )

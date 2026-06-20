"""auto-dead-api: Detect orphan API routes and MCP tools."""
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
import re
from pathlib import Path

from src.config.paths import get_all_client_skill_dirs, get_skill_data_dir
from src.lib.frontmatter_utils import load_skill_contract
from src.lib.ops_protocol import (
    FixResult, OpsContext, ScanResult, clear_report, report_only_fix, write_report,
)
import yaml

logger = logging.getLogger(__name__)

name = "auto-dead-api"

DIFFICULTY_SPEC = {
    0: "Surface check — count API routes and MCP tools",
    1: "Content check — orphan routes and tools (never referenced)",
    2: "Deep check — stub routes, placeholder handlers",
    3: "Exhaustive — dead scripts, action yaml with broken endpoints",
}

_EXTERNAL_ENTRYPOINT_PREFIXES = (
    "/api/agents",
    "/api/setup",
    "/api/remote",
    "/api/prompts",
    "/api/mcp",
    "/api/plugin-lifecycle",
    "/api/chat",
    "/api/wizard",
    "/api/insights",
)

_EXTERNAL_ENTRYPOINT_ROUTES = {
    "/api/bridge/plugin-data",
    "/api/context/files",
    "/api/cowork/sync",
    "/api/file-organizer/scan",
    "/api/files/list",
    "/api/llm",
    "/api/productization-plan/[slug]",
    "/api/skills/[skill]",
    "/api/sprint/active",
    "/api/system/open-with",
}


def _route_matches_consumer(route_pattern: str, consumer_ref: str) -> bool:
    """Match consumer refs against static and Next.js dynamic API route patterns."""
    route_parts = [part for part in route_pattern.split("/") if part]
    ref_parts = [part for part in consumer_ref.split("/") if part]
    route_len = len(route_parts)
    ref_len = len(ref_parts)
    i = 0
    j = 0

    while i < route_len and j < ref_len:
        route_part = route_parts[i]
        if route_part.startswith("[[...") and route_part.endswith("]]"):
            return True
        if route_part.startswith("[...") and route_part.endswith("]"):
            return j < ref_len
        if route_part.startswith("[") and route_part.endswith("]"):
            i += 1
            j += 1
            continue
        if route_part != ref_parts[j]:
            return False
        i += 1
        j += 1

    if i == route_len and j == ref_len:
        return True
    if i == route_len - 1 and route_parts[i].startswith("[[...") and route_parts[i].endswith("]]"):
        return True
    if i == route_len - 1 and route_parts[i].startswith("[...") and route_parts[i].endswith("]"):
        return j <= ref_len
    return False


def _collect_api_routes(
    project_root: Path,
    shared_snapshot: dict | None = None,
) -> dict[str, Path]:
    """Map API route path -> file path."""
    routes: dict[str, Path] = {}
    if shared_snapshot:
        route_urls = shared_snapshot.get("api_routes")
        route_paths = shared_snapshot.get("api_route_paths")
        if isinstance(route_urls, list) and isinstance(route_paths, list):
            for route_url, route_path in zip(route_urls, route_paths, strict=False):
                if isinstance(route_url, str) and isinstance(route_path, str):
                    resolved = project_root / route_path
                    if resolved.exists():
                        routes[route_url] = resolved
            if routes:
                return routes
    api_dir = project_root / "apps" / "dashboard" / "app" / "api"
    if not api_dir.exists():
        return routes
    for route_file in api_dir.glob("**/route.ts"):
        rel = route_file.parent.relative_to(
            project_root / "apps" / "dashboard" / "app"
        )
        route = "/" + str(rel).replace("\\", "/")
        routes[route] = route_file
    return routes


def _collect_mcp_tools(project_root: Path) -> dict[str, Path]:
    """Map MCP tool name -> SKILL.md that declares it."""
    tools: dict[str, Path] = {}
    for skills_dir in get_all_client_skill_dirs(project_root):
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            contract = load_skill_contract(skill_md)
            mcp = contract.get("mcp", {})
            if not isinstance(mcp, dict):
                continue
            for tool_name in mcp.get("tools", []):
                if isinstance(tool_name, str):
                    tools[tool_name] = skill_md
    return tools


def _iter_action_yaml_files(project_root: Path) -> list[Path]:
    """Collect action YAML files from assets plus canonical skill data dirs."""
    selected: dict[str, Path] = {}
    for skills_dir in get_all_client_skill_dirs(project_root):
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue

            assets_dir = skill_dir / "assets" / "actions"
            if assets_dir.is_dir():
                for yaml_file in sorted(assets_dir.glob("*.yaml")):
                    selected[f"{skill_dir.name}/{yaml_file.name}"] = yaml_file

            try:
                actions_dir = get_skill_data_dir(skill_dir.name) / "actions"
            except Exception:
                continue
            if not actions_dir.is_dir():
                continue
            for yaml_file in sorted(actions_dir.glob("*.yaml")):
                selected[f"{skill_dir.name}/{yaml_file.name}"] = yaml_file
    return [selected[key] for key in sorted(selected)]


def _normalize_api_ref(ref: str) -> str:
    """Normalize a discovered API reference to its route base."""
    return ref.split("?")[0].rstrip("/")


def _is_external_entrypoint(route_path: str) -> bool:
    """Routes invoked by external clients or browser entry flows are not dead."""
    if route_path in _EXTERNAL_ENTRYPOINT_ROUTES:
        return True
    return any(
        route_path == prefix or route_path.startswith(prefix + "/")
        for prefix in _EXTERNAL_ENTRYPOINT_PREFIXES
    )


def _collect_skill_markdown_api_refs(project_root: Path) -> set[str]:
    """Collect /api route references declared in canonical skill config."""
    refs: set[str] = set()
    relevant_keys = {"endpoint", "submitTool", "api_route", "tool"}

    def _walk(value: object) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in relevant_keys and isinstance(nested, str) and nested.startswith("/api/"):
                    refs.add(_normalize_api_ref(nested))
                _walk(nested)
        elif isinstance(value, list):
            for item in value:
                _walk(item)

    for skills_dir in get_all_client_skill_dirs(project_root):
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            contract = load_skill_contract(skill_md)
            config = contract.get("config")
            if isinstance(config, dict):
                _walk(config)

    return refs


def _collect_page_route_consumers(project_root: Path) -> set[str]:
    """Treat matching dashboard pages as indirect consumers of same-path APIs."""
    refs: set[str] = set()
    app_root = project_root / "apps" / "dashboard" / "app"
    if not app_root.exists():
        return refs

    for page_file in app_root.glob("**/page.tsx"):
        rel = page_file.parent.relative_to(app_root).as_posix()
        if rel == ".":
            continue
        refs.add(f"/api/{rel}")

    return refs


def _strip_ts_comments(content: str) -> str:
    """Remove block and line comments before heuristic route scanning."""
    without_block_comments = re.sub(r"/\*[\s\S]*?\*/", "", content)
    return re.sub(r"(^|[^:])//.*$", r"\1", without_block_comments, flags=re.MULTILINE)


def _collect_api_consumers(project_root: Path) -> set[str]:
    """Find all API paths referenced in .tsx/.ts and action yaml files."""
    refs: set[str] = set()
    # Match string-literal fetch: fetch('/api/...') or fetch("/api/...")
    fetch_re = re.compile(r'fetch\([\'"](/api/[^\'"]+)')
    # Match template-literal fetch: fetch(`/api/...`) — extract static /api/ segments
    fetch_tmpl_re = re.compile(r'fetch\(`(/api/[^`$]+)')
    # Match any /api/ string literal (broader catch for variable assignments, hooks)
    api_str_re = re.compile(r'[\'"](/api/[^\'"\s]+)[\'"]')
    api_tmpl_re = re.compile(r'`(/api/[^`$]+)')

    def _scan_ts_file(content: str) -> None:
        stripped = _strip_ts_comments(content)
        refs.update(
            _normalize_api_ref(match)
            for match in fetch_re.findall(stripped)
            if _normalize_api_ref(match) and _normalize_api_ref(match) != "/api"
        )
        # Template literals: extract the static prefix before any ${...}
        for match in fetch_tmpl_re.findall(stripped):
            static = _normalize_api_ref(match.split("$")[0])
            if static and static != "/api":
                refs.add(static)
        # Broader: any string literal containing /api/ path
        refs.update(
            _normalize_api_ref(match)
            for match in api_str_re.findall(stripped)
            if _normalize_api_ref(match) and _normalize_api_ref(match) != "/api"
        )
        for match in api_tmpl_re.findall(stripped):
            static = _normalize_api_ref(match.split("$")[0])
            if static and static != "/api":
                refs.add(static)

    # Scan plugin dashboard .tsx files
    for skills_dir in get_all_client_skill_dirs(project_root):
        for tsx in skills_dir.glob("*/augur/dashboard/**/*.tsx"):
            _scan_ts_file(tsx.read_text(errors="replace"))

    # Scan apps/dashboard (includes features/ pages, hooks, components, lib) (.tsx and .ts), including route.ts for internal API probes.
    for f in project_root.glob("apps/dashboard/**/*.tsx"):
        _scan_ts_file(f.read_text(errors="replace"))
    for f in project_root.glob("apps/dashboard/**/*.ts"):
        _scan_ts_file(f.read_text(errors="replace"))

    # Scan action yamls for endpoint refs
    for yaml_file in _iter_action_yaml_files(project_root):
        try:
            data = yaml.safe_load(yaml_file.read_text())
            if isinstance(data, dict) and data.get("endpoint"):
                refs.add(data["endpoint"])
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("endpoint"):
                        refs.add(item["endpoint"])
        except Exception:
            continue

    refs.update(_collect_skill_markdown_api_refs(project_root))
    refs.update(_collect_page_route_consumers(project_root))
    return refs


def _collect_tool_consumers(project_root: Path) -> set[str]:
    """Find all MCP tool names referenced in API routes and action yamls."""
    refs: set[str] = set()
    tool_re = re.compile(r'toolName:\s*[\'"]([^\'"]+)[\'"]')
    tool_re2 = re.compile(r'tool:\s*[\'"]?([a-z][\w-]+)[\'"]?')

    # Scan API route files
    api_dir = project_root / "apps" / "dashboard" / "app" / "api"
    if api_dir.exists():
        for ts in api_dir.glob("**/*.ts"):
            content = ts.read_text(errors="replace")
            refs.update(tool_re.findall(content))

    # Scan action yamls
    for yaml_file in _iter_action_yaml_files(project_root):
        try:
            content = yaml_file.read_text()
            refs.update(tool_re2.findall(content))
        except Exception:
            continue

    # Scan createAPIRoute files
    for ts in project_root.glob("apps/dashboard/lib/**/*.ts"):
        content = ts.read_text(errors="replace")
        refs.update(tool_re.findall(content))

    return refs


def scan(ctx: OpsContext) -> ScanResult:
    """Scan for orphan API routes and MCP tools."""
    api_routes = _collect_api_routes(ctx.project_root, ctx.shared_snapshot)
    mcp_tools = _collect_mcp_tools(ctx.project_root)

    if not api_routes and not mcp_tools:
        return ScanResult(
            issues=[], summary="No API routes or MCP tools found", severity="info"
        )

    if ctx.difficulty < 1:
        return ScanResult(
            issues=[],
            summary=f"{len(api_routes)} API routes, {len(mcp_tools)} MCP tools (d0 surface)",
            severity="info",
            health="verified",
        )

    issues: list[dict] = []

    # d1: orphan detection
    api_consumers = _collect_api_consumers(ctx.project_root)
    tool_consumers = _collect_tool_consumers(ctx.project_root)

    for route_path, route_file in api_routes.items():
        if _is_external_entrypoint(route_path):
            continue
        # Check if any consumer references this route (exact or prefix match)
        route_base = route_path.split("?")[0]
        if not any(
            ref == route_base
            or ref.startswith(route_base + "/")
            or route_base.startswith(ref + "/")  # consumer has prefix from template literal
            or _route_matches_consumer(route_base, ref)
            for ref in api_consumers
        ):
            issues.append({
                "type": "orphan_api_route",
                "route": route_path,
                "file": str(route_file.relative_to(ctx.project_root)),
                "detail": f"API route {route_path} — no consumer found in any .tsx or action yaml",
            })

    # MCP tools declared in canonical skill metadata: flag tools that are neither referenced
    # by any API route toolName nor any action YAML tool field.
    # CLI/IDE agents call MCP tools directly, so only flag at d2+ when we have
    # high confidence the tool is truly unreferenced.
    if ctx.difficulty >= 2 and mcp_tools:
        for tool_name, yaml_file in mcp_tools.items():
            if tool_name not in tool_consumers:
                issues.append({
                    "type": "orphan_mcp_tool",
                    "tool_name": tool_name,
                    "file": str(yaml_file.relative_to(ctx.project_root)),
                    "detail": f"MCP tool '{tool_name}' — 0 references in API routes or action YAML",
                })

    # d2: stub detection
    if ctx.difficulty >= 2:
        stub_re = re.compile(
            r'NextResponse\.json\(\s*\{\s*data:\s*\[\]\s*\}\s*\)',
        )
        for route_path, route_file in api_routes.items():
            try:
                content = route_file.read_text(errors="replace")
            except FileNotFoundError:
                continue
            # Stub: returns empty data and has no MCP/tool call
            if stub_re.search(content) and "createAPIRoute" not in content and "toolName" not in content and "callMCPTool" not in content:
                issues.append({
                    "type": "stub_route",
                    "route": route_path,
                    "file": str(route_file.relative_to(ctx.project_root)),
                    "detail": f"API route {route_path} returns hardcoded empty response with no MCP call",
                })

    # d3: action yamls with broken endpoints
    if ctx.difficulty >= 3:
        api_route_set = set(api_routes.keys())
        for yaml_file in _iter_action_yaml_files(ctx.project_root):
            try:
                data = yaml.safe_load(yaml_file.read_text())
                items = [data] if isinstance(data, dict) else (data if isinstance(data, list) else [])
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    endpoint = item.get("endpoint", "")
                    if endpoint and endpoint.startswith("/api/"):
                        base = endpoint.split("?")[0]
                        if base not in api_route_set and not any(
                            base.startswith(r) for r in api_route_set
                        ):
                            issues.append({
                                "type": "broken_action_endpoint",
                                "action_id": item.get("id", "?"),
                                "endpoint": endpoint,
                                "file": str(yaml_file.relative_to(ctx.project_root)),
                                "detail": f"Action '{item.get('id','?')}' endpoint '{endpoint}' — no matching route",
                            })
            except Exception:
                continue

    severity = "warning" if issues else "info"
    if not issues:
        clear_report("dead-api-latest.json")
    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} orphan backend element(s) ({len(api_routes)} routes, {len(mcp_tools)} tools checked)",
        severity=severity,
        items_scanned=len(api_routes) + len(mcp_tools),
    )


_TODO_MARKER = "// TODO_CLEANUP(auto-dead-api): "
_YAML_TODO_MARKER = "# TODO_CLEANUP(auto-dead-api): "


def _add_todo_marker_to_ts(file_path: Path, marker_msg: str) -> bool:
    """Add a TODO_CLEANUP marker to the top of a TypeScript route file.

    Returns True if the marker was added (or already present), False on error.
    """
    try:
        content = file_path.read_text()
    except Exception:
        return False

    full_marker = f"{_TODO_MARKER}{marker_msg}"

    # Already has this marker
    if _TODO_MARKER in content:
        return False

    # Prepend marker after any leading comments/imports header
    file_path.write_text(f"{full_marker}\n{content}")
    return True


def _add_todo_marker_to_yaml(file_path: Path, marker_msg: str) -> bool:
    """Add a TODO_CLEANUP marker to the top of a YAML action file."""
    try:
        content = file_path.read_text()
    except Exception:
        return False

    full_marker = f"{_YAML_TODO_MARKER}{marker_msg}"

    if _YAML_TODO_MARKER in content:
        return False

    file_path.write_text(f"{full_marker}\n{content}")
    return True


def _delete_route_file(file_path: Path) -> bool:
    """Delete an API route file and its parent dir if empty.

    Cleans up the directory tree upward as long as directories are empty.
    """
    try:
        file_path.unlink()
        # Clean up empty parent directories
        parent = file_path.parent
        while parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
        return True
    except Exception:
        return False


def _add_deprecation_comment_to_mcp(skill_md: Path, tool_name: str) -> bool:
    """Add a deprecation comment to SKILL.md for an unreferenced MCP tool.

    Returns True if the comment was added, False if already present or on error.
    """
    try:
        content = skill_md.read_text()
    except Exception:
        return False

    marker = f"# DEPRECATED(auto-dead-api): MCP tool '{tool_name}' has 0 consumer references"
    if marker in content:
        return False

    if not content.startswith("---"):
        return False

    lines = content.splitlines()
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return False

    pattern = re.compile(rf"^(\s*)-\s*{re.escape(tool_name)}\s*$")
    for i in range(1, end_idx):
        match = pattern.match(lines[i])
        if not match:
            continue
        indent = match.group(1)
        lines.insert(i, f"{indent}{marker}")
        skill_md.write_text("\n".join(lines) + ("\n" if content.endswith("\n") else ""))
        return True

    return False


def _route_has_existing_todo(file_path: Path) -> bool:
    """Check if a route file already has a TODO_CLEANUP marker from this scanner."""
    try:
        content = file_path.read_text()
        return _TODO_MARKER in content
    except Exception:
        return False


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix orphan API routes, MCP tools, and broken action endpoints.

    Behavior by difficulty:
    - d0: report only
    - d1-d2: add TODO_CLEANUP markers to orphan route files; delete stub routes;
             add deprecation comments to unreferenced MCP tools in SKILL.md
    - d3+: delete orphan routes entirely (they have no references anywhere);
            delete stub routes; mark broken action endpoints

    Auto-fixable:
    - orphan_api_route: d1-d2 add marker, d3+ delete the route file
    - orphan_mcp_tool: add deprecation comment in SKILL.md
    - stub_route: delete the stub route file (returns empty data, no MCP call)
    - broken_action_endpoint: add TODO_CLEANUP marker to the action YAML

    Report-only: issues where the file doesn't exist or marker already present.
    """
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: {len(issues)} orphan backend issue(s)",
        )

    if not issues:
        return FixResult(success=True, summary="No orphan backend issues to fix")

    marked: list[str] = []
    deleted: list[str] = []
    deprecated: list[str] = []
    unfixed: list[dict] = []

    for issue in issues:
        issue_type = issue.get("type", "")
        file_rel = issue.get("file", "")
        file_path = ctx.project_root / file_rel if file_rel else None

        if issue_type == "orphan_api_route":
            route = issue.get("route", "")
            if not (file_path and file_path.exists()):
                unfixed.append(issue)
                continue

            if ctx.difficulty >= 3:
                # At d3+, delete orphan routes — they have zero references
                if _delete_route_file(file_path):
                    deleted.append(file_rel)
                    logger.info("Deleted orphan route %s (%s)", route, file_rel)
                else:
                    unfixed.append(issue)
            else:
                msg = f"Orphan API route {route} — no consumer found in .tsx or action YAML"
                if _add_todo_marker_to_ts(file_path, msg):
                    marked.append(file_rel)
                else:
                    unfixed.append(issue)

        elif issue_type == "orphan_mcp_tool":
            tool_name = issue.get("tool_name", "")
            if file_path and file_path.exists() and tool_name:
                if _add_deprecation_comment_to_mcp(file_path, tool_name):
                    deprecated.append(f"{tool_name} ({file_rel})")
                else:
                    unfixed.append(issue)
            else:
                unfixed.append(issue)

        elif issue_type == "stub_route":
            route = issue.get("route", "")
            if file_path and file_path.exists():
                if _delete_route_file(file_path):
                    deleted.append(file_rel)
                else:
                    unfixed.append(issue)
            else:
                unfixed.append(issue)

        elif issue_type == "broken_action_endpoint":
            endpoint = issue.get("endpoint", "")
            action_id = issue.get("action_id", "?")
            if file_path and file_path.exists():
                msg = f"Action '{action_id}' endpoint '{endpoint}' has no matching route"
                if _add_todo_marker_to_yaml(file_path, msg):
                    marked.append(file_rel)
                else:
                    unfixed.append(issue)
            else:
                unfixed.append(issue)

        else:
            unfixed.append(issue)

    # Write report for unfixed issues
    if unfixed:
        write_report(ctx, "dead-api-latest.json", {"issues": unfixed})
    else:
        clear_report("dead-api-latest.json")

    # Build summary
    parts: list[str] = []
    if marked:
        parts.append(f"Added TODO_CLEANUP markers to {len(marked)} file(s)")
    if deleted:
        parts.append(f"Deleted {len(deleted)} orphan route(s)")
    if deprecated:
        parts.append(f"Added deprecation comments to {len(deprecated)} MCP tool(s)")
    if unfixed:
        parts.append(f"{len(unfixed)} issue(s) need manual review (report written)")
    if not parts:
        parts.append("No orphan backend issues")

    changes = marked + deleted + deprecated

    return FixResult(
        success=True,
        changes=changes,
        summary=". ".join(parts),
        fix_type="code-fix" if changes else "report",
    )

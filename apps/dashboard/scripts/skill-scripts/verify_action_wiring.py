#!/usr/bin/env python3
"""Verify action wiring from canonical skill action YAML files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, ".")

from src.config.paths import get_project_root, get_skill_data_dir, get_skills_dir

VALID_DISPATCH = {"fire", "ide", "oneshot", "modal"}
TOOL_NAME_PATTERN = re.compile(r'name\s*=\s*["\']([A-Za-z0-9._:-]+)["\']')


def _trim_issues(issues: list[str], max_items: int = 100) -> tuple[list[str], int]:
    if len(issues) <= max_items:
        return issues, 0
    return issues[:max_items], len(issues) - max_items


def discover_action_files(root: Path) -> list[Path]:
    action_files: list[Path] = []
    for skill_dir in get_skills_dir().glob("*"):
        if not skill_dir.is_dir():
            continue
        try:
            action_files.extend(sorted((get_skill_data_dir(skill_dir.name) / "actions").glob("*.yaml")))
        except Exception:
            continue
    return action_files


def discover_registered_mcp_tools(root: Path) -> set[str]:
    tools: set[str] = set()
    scan_dirs = [
        root / "src" / "mcp",
        root / "project-brain" / "capabilities" / "skills",
    ]
    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for match in TOOL_NAME_PATTERN.finditer(content):
                tools.add(match.group(1))
    return tools


def _collect_routes_from(base: Path) -> set[str]:
    routes: set[str] = set()
    if not base.exists():
        return routes
    for route_file in list(base.rglob("route.ts")) + list(base.rglob("route.js")):
        rel = route_file.relative_to(base).as_posix()
        endpoint_tail = rel.rsplit("/route.", 1)[0]
        routes.add(f"/api/{endpoint_tail}")
    return routes


def discover_api_routes(root: Path) -> set[str]:
    routes: set[str] = set()
    routes.update(_collect_routes_from(root / "apps" / "dashboard" / "app" / "api"))
    for plugin_api in root.glob("project-brain/capabilities/skills/*/augur/api"):
        routes.update(_collect_routes_from(plugin_api))
    for plugin_dashboard_api in root.glob("project-brain/capabilities/skills/*/augur/dashboard/api"):
        routes.update(_collect_routes_from(plugin_dashboard_api))
    return routes


def _split_segments(path: str) -> list[str]:
    return [seg for seg in path.strip("/").split("/") if seg]


def endpoint_exists(endpoint: str, routes: set[str]) -> bool:
    normalized = endpoint.split("?", 1)[0].rstrip("/")
    if normalized in routes:
        return True

    endpoint_segments = _split_segments(normalized)
    for route in routes:
        route_segments = _split_segments(route)
        if len(route_segments) != len(endpoint_segments):
            continue
        if all(
            rs.startswith("[") and rs.endswith("]") or rs == es
            for rs, es in zip(route_segments, endpoint_segments, strict=True)
        ):
            return True
    return False


def parse_actions(action_file: Path) -> tuple[list[dict], list[str]]:
    parse_issues: list[str] = []
    try:
        data = yaml.safe_load(action_file.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [], [f"YAML parse error: {exc}"]
    except OSError as exc:
        return [], [f"Read error: {exc}"]

    if data is None:
        return [], [f"Empty YAML file: {action_file.name}"]
    if isinstance(data, dict):
        return [data], parse_issues
    if isinstance(data, list):
        actions = [item for item in data if isinstance(item, dict)]
        if not actions:
            parse_issues.append(f"No action objects found in list: {action_file.name}")
        return actions, parse_issues
    return [], [f"Unsupported YAML structure in {action_file.name}"]


def _resolve_script_path(root: Path, action_file: Path, script_path: str) -> Path:
    path_candidate = Path(script_path)
    if path_candidate.is_absolute():
        return path_candidate
    if script_path.startswith("plugins/"):
        return root / path_candidate
    return action_file.parent / path_candidate


def verify_actions(root: Path) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    dispatch_counts: dict[str, int] = {}

    action_files = discover_action_files(root)
    registered_tools = discover_registered_mcp_tools(root)
    known_routes = discover_api_routes(root)

    action_count = 0
    for action_file in action_files:
        rel = action_file.relative_to(root).as_posix()
        actions, parse_issues = parse_actions(action_file)
        for issue in parse_issues:
            errors.append(f"{rel}: {issue}")
        for action in actions:
            action_count += 1
            action_id = str(action.get("id") or "unknown")
            dispatch = str(action.get("dispatch") or "")
            label = f"{rel}::{action_id}"

            dispatch_counts[dispatch or "missing"] = dispatch_counts.get(dispatch or "missing", 0) + 1

            if not dispatch:
                errors.append(f"{label}: missing required field 'dispatch'")
            elif dispatch not in VALID_DISPATCH:
                warnings.append(f"{label}: unknown dispatch '{dispatch}'")

            endpoint = str(action.get("endpoint") or "").strip()
            if endpoint:
                if not endpoint.startswith("/api/"):
                    errors.append(f"{label}: endpoint must start with /api/ (found '{endpoint}')")
                elif not endpoint_exists(endpoint, known_routes):
                    errors.append(f"{label}: endpoint not found in API routes ('{endpoint}')")

            mcp_tool = str(action.get("mcp_tool") or "").strip()
            mcp_tools = action.get("mcp_tools")
            mcp_tools_list = [tool for tool in mcp_tools if isinstance(tool, str)] if isinstance(mcp_tools, list) else []
            all_mcp_tools = [tool for tool in [mcp_tool, *mcp_tools_list] if tool]
            for tool in all_mcp_tools:
                if tool not in registered_tools:
                    warnings.append(f"{label}: mcp_tool '{tool}' not found in registered MCP tools")

            script_path = str(action.get("script_path") or "").strip()
            if script_path:
                resolved = _resolve_script_path(root, action_file, script_path)
                if not resolved.exists():
                    errors.append(f"{label}: script_path not found ('{script_path}')")

            if dispatch == "fire":
                has_backend = bool(
                    endpoint
                    or all_mcp_tools
                    or script_path
                    or action.get("script")
                    or action.get("href")
                )
                if not has_backend:
                    errors.append(f"{label}: fire action has no backend target (endpoint/mcp_tool/script_path/script)")

            if dispatch in {"ide", "oneshot"}:
                has_context = bool(action.get("prompt") or action.get("agents") or all_mcp_tools)
                if not has_context:
                    warnings.append(f"{label}: {dispatch} action has no prompt/agents/mcp_tool context")

    errors_trimmed, errors_hidden = _trim_issues(errors)
    warnings_trimmed, warnings_hidden = _trim_issues(warnings)
    return {
        "success": len(errors) == 0,
        "summary": {
            "action_files": len(action_files),
            "actions_checked": action_count,
            "dispatch_counts": dispatch_counts,
            "registered_mcp_tools": len(registered_tools),
            "known_api_routes": len(known_routes),
            "errors_count": len(errors),
            "warnings_count": len(warnings),
        },
        "errors": errors_trimmed,
        "warnings": warnings_trimmed,
        "errors_truncated": errors_hidden,
        "warnings_truncated": warnings_hidden,
    }


def main() -> int:
    root = get_project_root()
    result = verify_actions(root)
    print(json.dumps(result, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())

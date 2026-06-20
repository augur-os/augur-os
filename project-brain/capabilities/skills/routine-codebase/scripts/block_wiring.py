"""auto-block-wiring: Validate block data pipelines — dataSource, API routes, MCP tools."""
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
from difflib import get_close_matches
from pathlib import Path

import yaml

from src.config.paths import get_all_client_skill_dirs
from src.lib.ops_protocol import (
    FixResult, OpsContext, ScanResult, clear_report, find_api_routes, find_page_routes,
    report_only_fix, write_report,
)

name = "auto-block-wiring"

CLIENT_ONLY_BLOCK_TYPES = {"markdown", "notes"}

_MCP_TOOL_RE = re.compile(r'@mcp\.tool\(\s*name\s*=\s*["\']([^"\']+)["\']')


def _discover_mcp_tools_from_python(skill_dirs: list[Path], project_root: Path) -> set[str]:
    """Discover MCP tool names from @mcp.tool(name=...) in skill and core Python files."""
    tools: set[str] = set()
    search_dirs = list(skill_dirs) + [project_root / "src" / "mcp"]
    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        for py_file in search_dir.rglob("*.py"):
            try:
                text = py_file.read_text(errors="ignore")
            except Exception:
                continue
            for m in _MCP_TOOL_RE.finditer(text):
                tools.add(m.group(1))
    return tools


def scan(ctx: OpsContext) -> ScanResult:
    """Validate block data pipelines across all skills."""
    skill_dirs = get_all_client_skill_dirs(ctx.project_root)
    if not skill_dirs:
        return ScanResult(issues=[], summary="No skill directories", severity="info")

    api_routes = find_api_routes(ctx.project_root, ctx.shared_snapshot)
    page_routes = find_page_routes(ctx.project_root, ctx.shared_snapshot)
    mcp_tools: set[str] = _discover_mcp_tools_from_python(skill_dirs, ctx.project_root)
    issues: list[dict] = []
    n_blocks = 0

    for skills_dir in skill_dirs:
        for yaml_file in sorted(skills_dir.glob("*/config.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text())
            except Exception:
                continue
            if not isinstance(data, dict):
                continue

            # Collect MCP tools from this file
            mcp = data.get("mcp", {})
            if isinstance(mcp, dict):
                for tool in mcp.get("tools", []):
                    if isinstance(tool, dict) and tool.get("name"):
                        mcp_tools.add(tool["name"])

            contributions = data.get("contributions")
            if not isinstance(contributions, dict):
                continue

            blocks = contributions.get("blocks", [])
            if not isinstance(blocks, list):
                continue

            try:
                rel_yaml = str(yaml_file.relative_to(ctx.project_root))
            except ValueError:
                rel_yaml = str(yaml_file)

            for block in blocks:
                if not isinstance(block, dict):
                    continue
                n_blocks += 1
                block_id = block.get("id", "unknown")
                block_type = block.get("type", "")
                data_source = block.get("dataSource") or block.get("data_source")

                # Check dataSource presence for data-bearing types
                if block_type not in CLIENT_ONLY_BLOCK_TYPES:
                    if not data_source or not isinstance(data_source, dict):
                        issues.append({
                            "type": "missing_datasource",
                            "block_id": block_id,
                            "file": rel_yaml,
                            "detail": f"Block '{block_id}' (type: {block_type}) has no dataSource",
                        })
                        continue

                    api_route = data_source.get("apiRoute", "") or data_source.get("api_route", "")
                    mcp_tool = data_source.get("mcpTool", "") or data_source.get("mcp_tool", "")

                    if not api_route and not mcp_tool:
                        issues.append({
                            "type": "missing_datasource",
                            "block_id": block_id,
                            "file": rel_yaml,
                            "detail": f"Block '{block_id}' dataSource has neither apiRoute nor mcpTool",
                        })

                    # Validate apiRoute resolves
                    if api_route and api_route not in api_routes:
                        issues.append({
                            "type": "missing_api_route",
                            "block_id": block_id,
                            "file": rel_yaml,
                            "api_route": api_route,
                            "detail": f"Block '{block_id}' apiRoute '{api_route}' has no route.ts",
                        })

                    # Validate mcpTool exists
                    if mcp_tool and mcp_tool not in mcp_tools:
                        issues.append({
                            "type": "missing_mcp_tool",
                            "block_id": block_id,
                            "file": rel_yaml,
                            "mcp_tool": mcp_tool,
                            "detail": f"Block '{block_id}' mcpTool '{mcp_tool}' not declared",
                        })

                # Validate expandTo route
                expand_to = block.get("expandTo", "")
                if expand_to and expand_to not in page_routes:
                    issues.append({
                        "type": "missing_expandto_page",
                        "block_id": block_id,
                        "file": rel_yaml,
                        "expand_to": expand_to,
                        "detail": f"Block '{block_id}' expandTo '{expand_to}' has no page.tsx",
                    })

    if not issues:
        clear_report("block-wiring-latest.json")

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} block wiring issue(s)",
        severity="warning" if issues else "info",
        items_scanned=n_blocks,
    )


def _fuzzy_match_tool(name: str, known_tools: set[str], cutoff: float = 0.7) -> str | None:
    """Find the closest matching MCP tool name, if any."""
    matches = get_close_matches(name, list(known_tools), n=1, cutoff=cutoff)
    return matches[0] if matches else None


def _fuzzy_match_route(route: str, known_routes: set[str], cutoff: float = 0.7) -> str | None:
    """Find the closest matching API route, if any."""
    matches = get_close_matches(route, list(known_routes), n=1, cutoff=cutoff)
    return matches[0] if matches else None


def _patch_yaml_field(file_path: Path, block_id: str, field_path: list[str], old_val: str, new_val: str) -> bool:
    """Patch a specific field value in a YAML file using text replacement.

    This does targeted string replacement to avoid reformatting the entire file.
    Only replaces the first occurrence of old_val that appears near the block_id context.
    """
    try:
        content = file_path.read_text()
    except Exception:
        return False

    # Find the old value and replace it — use a targeted approach
    # Look for the exact field: old_val pattern
    field_name = field_path[-1]
    # Match patterns like  mcpTool: old_val  or  mcpTool: "old_val"
    patterns = [
        (f'{field_name}: {old_val}', f'{field_name}: {new_val}'),
        (f'{field_name}: "{old_val}"', f'{field_name}: "{new_val}"'),
        (f"{field_name}: '{old_val}'", f"{field_name}: '{new_val}'"),
    ]

    for old_pattern, new_pattern in patterns:
        if old_pattern in content:
            content = content.replace(old_pattern, new_pattern, 1)
            file_path.write_text(content)
            return True

    return False


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix block wiring issues where safe auto-fixes are possible.

    Auto-fixable:
    - missing_mcp_tool: fuzzy-match to correct tool name in YAML
    - missing_api_route: fuzzy-match to correct route in YAML

    Report-only (ambiguous):
    - missing_datasource: requires understanding block intent
    - missing_expandto_page: requires page creation or block removal
    """
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: {len(issues)} block wiring issue(s)",
        )

    if not issues:
        return FixResult(success=True, summary="No block wiring issues to fix")

    # Rebuild the tool and route sets for fuzzy matching
    skill_dirs = get_all_client_skill_dirs(ctx.project_root)
    mcp_tools = _discover_mcp_tools_from_python(skill_dirs, ctx.project_root)
    api_routes = find_api_routes(ctx.project_root, ctx.shared_snapshot)
    page_routes = find_page_routes(ctx.project_root, ctx.shared_snapshot)

    # Also gather MCP tools from config.yaml files
    for skills_dir in skill_dirs:
        for yaml_file in skills_dir.glob("*/config.yaml"):
            try:
                data = yaml.safe_load(yaml_file.read_text())
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            mcp = data.get("mcp", {})
            if isinstance(mcp, dict):
                for tool in mcp.get("tools", []):
                    if isinstance(tool, dict) and tool.get("name"):
                        mcp_tools.add(tool["name"])

    fixed: list[str] = []
    unfixed: list[dict] = []

    for issue in issues:
        issue_type = issue.get("type", "")
        file_rel = issue.get("file", "")
        block_id = issue.get("block_id", "unknown")
        file_path = ctx.project_root / file_rel

        if not file_path.exists():
            unfixed.append(issue)
            continue

        if issue_type == "missing_mcp_tool":
            # Try fuzzy match against known MCP tools
            bad_tool = issue.get("mcp_tool", "")
            match = _fuzzy_match_tool(bad_tool, mcp_tools)
            if match and match != bad_tool:
                patched = _patch_yaml_field(
                    file_path, block_id, ["dataSource", "mcpTool"], bad_tool, match,
                )
                if patched:
                    fixed.append(f"{file_rel}: block '{block_id}' mcpTool '{bad_tool}' -> '{match}'")
                    continue
            unfixed.append(issue)

        elif issue_type == "missing_api_route":
            # Try fuzzy match against known API routes
            bad_route = issue.get("api_route", "")
            match = _fuzzy_match_route(bad_route, api_routes)
            if match and match != bad_route:
                patched = _patch_yaml_field(
                    file_path, block_id, ["dataSource", "apiRoute"], bad_route, match,
                )
                if patched:
                    fixed.append(f"{file_rel}: block '{block_id}' apiRoute '{bad_route}' -> '{match}'")
                    continue
            unfixed.append(issue)

        elif issue_type == "missing_expandto_page":
            # Try fuzzy match against known page routes
            bad_page = issue.get("expand_to", "")
            match = _fuzzy_match_route(bad_page, page_routes)
            if match and match != bad_page:
                patched = _patch_yaml_field(
                    file_path, block_id, ["expandTo"], bad_page, match,
                )
                if patched:
                    fixed.append(f"{file_rel}: block '{block_id}' expandTo '{bad_page}' -> '{match}'")
                    continue
            unfixed.append(issue)

        else:
            # missing_datasource and other types — report only
            unfixed.append(issue)

    # Write report for unfixed issues
    if unfixed:
        write_report(ctx, "block-wiring-latest.json", {"issues": unfixed})
    else:
        clear_report("block-wiring-latest.json")

    # Build summary
    parts: list[str] = []
    if fixed:
        parts.append(f"Fixed {len(fixed)} block wiring issue(s)")
    if unfixed:
        parts.append(f"{len(unfixed)} issue(s) need manual review (report written)")
    if not parts:
        parts.append("No block wiring issues")

    return FixResult(
        success=True,
        changes=[c.split(":")[0].strip() for c in fixed],  # file paths only
        summary=". ".join(parts),
        fix_type="code-fix" if fixed else "report",
    )

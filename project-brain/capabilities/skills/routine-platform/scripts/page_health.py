"""auto-page-health: Dashboard page MCP tool health verification and auto-fix.

Scans YAML and TSX dashboard pages for MCP tool references, verifies each
tool exists and returns data, and auto-fixes broken YAML tool names at d1+.
"""
from __future__ import annotations

import json
import re
import subprocess
from difflib import get_close_matches
from pathlib import Path

import yaml

from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_project_brain_skills_dir
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-page-health"
DEFAULT_DASHBOARD_PORT = 3000

# ---------------------------------------------------------------------------
# Tool extraction regexes (from verify-page-tools.py)
# ---------------------------------------------------------------------------

_RE_USE_MCP_QUERY = re.compile(
    r"""useMcpQuery\b[^(]*\(\s*"""
    r"""(?:\[[^\]]*\]|'[^']*'|"[^"]*")\s*,\s*"""
    r"""['"]([^'"]+)['"]""",
    re.DOTALL,
)

_RE_USE_MCP_MUTATION = re.compile(
    r"""useMcpMutation\b[^(]*\(\s*['"]([^'"]+)['"]""",
    re.DOTALL,
)

_RE_USE_MCP_POLL = re.compile(
    r"""useMcpPoll\b[^(]*\(\s*"""
    r"""(?:\[[^\]]*\]|'[^']*'|"[^"]*")\s*,\s*"""
    r"""['"]([^'"]+)['"]""",
    re.DOTALL,
)

PASSIVE_YAML_BLOCK_TYPES = {
    "chart",
    "data-list",
    "data-table",
    "metrics-dashboard",
    "stat-grid",
    "timeline",
}
MUTATION_TOOL_PREFIXES = (
    "add-",
    "cancel-",
    "create-",
    "delete-",
    "execute-",
    "save-",
    "sync-",
    "update-",
)
ARGUMENT_REQUIRED_TOOL_PREFIXES = (
    "find-",
    "search-",
)
METADATA_ONLY_KEYS = {"skill", "status", "version"}


# ---------------------------------------------------------------------------
# Page scanning
# ---------------------------------------------------------------------------

def _extract_yaml_tools(yaml_path: Path) -> list[dict]:
    """Extract mcp_tool references from a YAML page config."""
    try:
        content = yaml_path.read_text()
        parsed = yaml.safe_load(content)
    except Exception:
        return []

    if not isinstance(parsed, dict):
        return []

    tools: list[dict] = []
    hub = parsed.get("hub", "")
    route = parsed.get("route", "")
    page = f"{hub}/{route}" if hub and route else str(yaml_path)

    for block in parsed.get("blocks", []):
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type", ""))
        # Direct mcp_tool on block
        if "mcp_tool" in block:
            tools.append({
                "tool": block["mcp_tool"],
                "source": "yaml",
                "page": page,
                "file": str(yaml_path),
                "block_type": block_type,
            })
        # Sources array (metrics-dashboard)
        for source in block.get("sources", []):
            if isinstance(source, dict) and "mcp_tool" in source:
                tools.append({
                    "tool": source["mcp_tool"],
                    "source": "yaml",
                    "page": page,
                    "file": str(yaml_path),
                    "block_type": block_type,
                })

    return tools


def _is_passive_yaml_ref(ref: dict) -> bool:
    return ref.get("source") == "yaml" and ref.get("block_type") in PASSIVE_YAML_BLOCK_TYPES


def _is_mutation_tool_name(tool_name: str) -> bool:
    return tool_name.startswith(MUTATION_TOOL_PREFIXES)


def _is_argument_required_tool_name(tool_name: str) -> bool:
    return tool_name.startswith(ARGUMENT_REQUIRED_TOOL_PREFIXES)


def _is_metadata_only_response(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    keys = {str(key) for key in payload.keys()}
    return bool(keys) and keys <= METADATA_ONLY_KEYS


def _yaml_data_source_issues(refs: list[dict]) -> list[dict]:
    issues: list[dict] = []
    for ref in refs:
        if not _is_passive_yaml_ref(ref):
            continue
        tool = str(ref["tool"])
        if _is_mutation_tool_name(tool):
            issues.append({
                "action": "yaml-passive-mutation-tool",
                "file": ref["file"],
                "tool": tool,
                "page": ref["page"],
                "source_type": ref["source"],
                "block_type": ref.get("block_type", ""),
                "error": "passive YAML data blocks cannot use mutation tools",
            })
        elif _is_argument_required_tool_name(tool):
            issues.append({
                "action": "yaml-passive-argument-required-tool",
                "file": ref["file"],
                "tool": tool,
                "page": ref["page"],
                "source_type": ref["source"],
                "block_type": ref.get("block_type", ""),
                "error": "passive YAML data blocks cannot use search/find tools that require arguments",
            })
    return issues


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _coerce_port(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _load_marker(project_root: Path) -> dict[str, object]:
    marker_path = project_root / ".augur-worktree.yaml"
    if not marker_path.exists():
        return {}

    try:
        parsed = yaml.safe_load(marker_path.read_text(encoding="utf-8")) or {}
    except Exception:
        parsed = {}
    if isinstance(parsed, dict):
        return parsed

    marker: dict[str, object] = {}
    for raw_line in marker_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        marker[key.strip()] = _strip_quotes(value)
    return marker


def _load_worktree_registry() -> dict[str, dict[str, object]]:
    try:
        from src.config.paths import get_runtime_dir

        registry_path = get_runtime_dir() / "worktree_registry.yaml"
    except Exception:
        return {}

    if not registry_path.exists():
        return {}

    try:
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    if isinstance(raw, dict) and isinstance(raw.get("worktrees"), dict):
        raw = raw["worktrees"]
    if not isinstance(raw, dict):
        return {}
    return {
        str(path): entry
        for path, entry in raw.items()
        if isinstance(path, str) and isinstance(entry, dict)
    }


def _project_yaml_port(project_root: Path) -> int | None:
    project_yaml = project_root / "project.yaml"
    if not project_yaml.exists():
        return None
    try:
        parsed = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    return _coerce_port(parsed.get("port"))


def _dashboard_port(project_root: Path) -> int:
    root = project_root.resolve()
    marker_port = _coerce_port(_load_marker(root).get("dashboard_port"))
    if marker_port is not None:
        return marker_port

    registry_port = _coerce_port(_load_worktree_registry().get(str(root), {}).get("dashboard_port"))
    if registry_port is not None:
        return registry_port

    return _project_yaml_port(root) or DEFAULT_DASHBOARD_PORT


def _dashboard_tool_url(project_root: Path) -> str:
    return f"http://localhost:{_dashboard_port(project_root)}/api/mcp/tool"


def _yaml_probe_issue(ref: dict, action: str, error: str) -> dict:
    return {
        "action": action,
        "file": ref["file"],
        "tool": ref["tool"],
        "page": ref["page"],
        "source_type": ref["source"],
        "block_type": ref.get("block_type", ""),
        "error": error,
    }


def _has_name_based_yaml_data_issue(ref: dict) -> bool:
    tool = str(ref["tool"])
    return _is_mutation_tool_name(tool) or _is_argument_required_tool_name(tool)


def _extract_tsx_tools(tsx_path: Path, pages_dir: Path) -> list[dict]:
    """Extract MCP tool references from a TSX page."""
    try:
        content = tsx_path.read_text(errors="replace")
    except Exception:
        return []

    tools: list[dict] = []
    rel = str(tsx_path.relative_to(pages_dir)).replace("/page.tsx", "")

    for m in _RE_USE_MCP_QUERY.finditer(content):
        tools.append({"tool": m.group(1), "source": "tsx", "page": rel, "file": str(tsx_path)})
    for m in _RE_USE_MCP_MUTATION.finditer(content):
        tools.append({"tool": m.group(1), "source": "tsx", "page": rel, "file": str(tsx_path)})
    for m in _RE_USE_MCP_POLL.finditer(content):
        tools.append({"tool": m.group(1), "source": "tsx", "page": rel, "file": str(tsx_path)})

    return tools


def _probe_tool(tool_name: str, api_url: str | None = None) -> dict:
    """Call an MCP tool via the dashboard API to verify it exists and returns data."""
    import urllib.error
    import urllib.request

    try:
        body = json.dumps({"tool": tool_name, "args": {}}).encode()
        target_url = api_url or f"http://localhost:{DEFAULT_DASHBOARD_PORT}/api/mcp/tool"
        if not target_url.lower().startswith(("http://", "https://")):
            raise ValueError(f"Non-HTTP URL rejected: {target_url!r}")
        req = urllib.request.Request(
            target_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310  # target_url scheme-validated above
            status = resp.status
            data = json.loads(resp.read())
            metadata_only = _is_metadata_only_response(data)
            response_error = str(data.get("error")) if isinstance(data, dict) and data.get("error") else ""
            has_data = bool(data) and not metadata_only and not response_error
            result = {"exists": True, "has_data": has_data, "status": status, "metadata_only": metadata_only}
            if metadata_only:
                result["error"] = "metadata-only response"
            elif response_error:
                result["error"] = response_error
            return result
    except urllib.error.HTTPError as e:
        return {"exists": e.code != 404, "has_data": False, "metadata_only": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"exists": False, "has_data": False, "metadata_only": False, "error": str(e)[:100]}


def _get_all_tool_names() -> set[str]:
    """Get all registered MCP tool names by scanning Python source files.

    Scans @mcp.tool(name=...) registrations across skills/ and src/mcp/
    rather than relying on the curated dashboard list-mcp-tools endpoint
    (which only returns a UI-focused subset).
    """
    _RE_TOOL_NAME = re.compile(r'''name\s*=\s*["']([^"']+)["']''')
    tools: set[str] = set()

    search_dirs = [
        PROJECT_ROOT / "project-brain" / "capabilities" / "skills",
        PROJECT_ROOT / "src" / "mcp",
    ]

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        for py_file in search_dir.rglob("*.py"):
            try:
                content = py_file.read_text(errors="replace")
            except Exception:
                continue
            if "@mcp.tool" not in content and "mcp.tool(" not in content:
                continue
            for m in _RE_TOOL_NAME.finditer(content):
                tools.add(m.group(1))

    return tools




# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def scan(ctx: OpsContext) -> ScanResult:
    """Scan all dashboard pages for broken MCP tool references."""
    project_root = ctx.project_root
    skills_dir = get_project_brain_skills_dir(project_root)
    pages_dir = skills_dir / "dashboard" / "pages"

    # Collect all tool references
    all_refs: list[dict] = []

    # 1. Scan YAML pages
    for yaml_path in sorted(skills_dir.rglob("augur/pages/*.yaml")):
        all_refs.extend(_extract_yaml_tools(yaml_path))

    # 2. Scan TSX pages
    if pages_dir.exists():
        for tsx_path in sorted(pages_dir.rglob("page.tsx")):
            all_refs.extend(_extract_tsx_tools(tsx_path, pages_dir))

    if not all_refs:
        return ScanResult(issues=[], summary="No page tool references found", severity="info")

    yaml_data_issues = _yaml_data_source_issues(all_refs)
    passive_yaml_refs = [ref for ref in all_refs if _is_passive_yaml_ref(ref)]
    probeable_passive_yaml_refs = [
        ref for ref in passive_yaml_refs if not _has_name_based_yaml_data_issue(ref)
    ]

    # 3. Check each tool against MCP registry (registry-based, not probe-based,
    #    because mutation/search tools return 500 when called with empty args)
    unique_tools = {ref["tool"] for ref in all_refs}
    all_known = _get_all_tool_names()
    broken_tools: dict[str, str] = {}  # tool -> error message
    yaml_metadata_issues: list[dict] = []
    probe_url = _dashboard_tool_url(project_root)

    if all_known:
        # Registry available — check tool existence without probing
        for tool in sorted(unique_tools):
            if tool not in all_known:
                broken_tools[tool] = "tool not in MCP registry"
        for ref in probeable_passive_yaml_refs:
            probe_result = _probe_tool(str(ref["tool"]), probe_url)
            if probe_result.get("metadata_only"):
                yaml_metadata_issues.append(_yaml_probe_issue(
                    ref,
                    "yaml-passive-metadata-only-tool",
                    "passive YAML data blocks cannot use metadata-only tool responses",
                ))
            elif not probe_result.get("has_data"):
                error = str(probe_result.get("error") or "response shape could not be verified")
                yaml_metadata_issues.append(_yaml_probe_issue(
                    ref,
                    "yaml-passive-unverified-tool-response",
                    f"passive YAML data source response shape could not be verified: {error}",
                ))
    else:
        # Dashboard not running — fall back to probe, but only flag 404s.
        probe_results: dict[str, dict] = {}
        for tool in sorted(unique_tools):
            probe_results[tool] = _probe_tool(tool, probe_url)
            if not probe_results[tool].get("exists"):
                broken_tools[tool] = probe_results[tool].get("error", "tool not found")

        for ref in probeable_passive_yaml_refs:
            probe_result = probe_results.get(ref["tool"], {})
            if probe_result.get("metadata_only"):
                yaml_metadata_issues.append(_yaml_probe_issue(
                    ref,
                    "yaml-passive-metadata-only-tool",
                    "passive YAML data blocks cannot use metadata-only tool responses",
                ))
            elif probe_result.get("exists") and not probe_result.get("has_data"):
                error = str(probe_result.get("error") or "response shape could not be verified")
                yaml_metadata_issues.append(_yaml_probe_issue(
                    ref,
                    "yaml-passive-unverified-tool-response",
                    f"passive YAML data source response shape could not be verified: {error}",
                ))

    if not broken_tools and not yaml_data_issues and not yaml_metadata_issues:
        return ScanResult(
            issues=[],
            summary=f"All {len(unique_tools)} tools verified across {len(all_refs)} references",
            severity="info",
        )

    # 4. Build issues for broken tools, with fuzzy-match suggestions
    issues: list[dict] = []
    # Get all known tool names for fuzzy matching
    all_known = _get_all_tool_names()

    for ref in all_refs:
        if ref["tool"] not in broken_tools:
            continue

        suggestion = None
        if all_known:
            matches = get_close_matches(ref["tool"], sorted(all_known), n=1, cutoff=0.6)
            suggestion = matches[0] if matches else None

        issues.append({
            "action": "broken-tool",
            "file": ref["file"],
            "tool": ref["tool"],
            "page": ref["page"],
            "source_type": ref["source"],
            "error": broken_tools[ref["tool"]],
            "suggestion": suggestion,
        })

    if yaml_data_issues:
        issues = yaml_data_issues + issues
    if yaml_metadata_issues:
        issues.extend(yaml_metadata_issues)

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} issue(s) across {len(all_refs)} reference(s)",
        severity="error" if issues else "info",
    )


# ---------------------------------------------------------------------------
# Fix
# ---------------------------------------------------------------------------

def _commit_files(project_root: Path, message: str, paths: list[str]) -> str | None:
    """Stage and commit specific files. Returns commit hash or None."""
    for p in paths:
        subprocess.run(["git", "add", p], capture_output=True, cwd=str(project_root))
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        return None
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if line.startswith("["):
                parts = line.split()
                for part in parts:
                    if len(part) >= 7 and part.rstrip("]").isalnum():
                        return part.rstrip("]")
    return None


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Auto-fix broken tool names in YAML configs via fuzzy matching."""
    if ctx.dry_run:
        fixable = [i for i in issues if i.get("source_type") == "yaml" and i.get("suggestion")]
        return FixResult(
            success=True,
            summary=f"Dry run: would fix {len(fixable)} of {len(issues)} broken tool(s)",
            fix_type="report",
        )

    actions: list[dict] = []
    changes: list[str] = []
    fixed_count = 0
    skipped_count = 0

    # Group issues by file for batch updates
    by_file: dict[str, list[dict]] = {}
    for issue in issues:
        by_file.setdefault(issue["file"], []).append(issue)

    for file_path, file_issues in by_file.items():
        path = Path(file_path)

        # Only auto-fix YAML files
        if not file_path.endswith(".yaml"):
            for issue in file_issues:
                actions.append({
                    "skipped": file_path,
                    "tool": issue["tool"],
                    "reason": "TSX file — manual migration required",
                })
                skipped_count += 1
            continue

        # Read YAML, apply fixes
        if not path.exists():
            for issue in file_issues:
                actions.append({"skipped": file_path, "tool": issue["tool"], "reason": "file not found"})
                skipped_count += 1
            continue

        try:
            content = path.read_text()
        except Exception:
            for issue in file_issues:
                actions.append({"skipped": file_path, "tool": issue["tool"], "reason": "read error"})
                skipped_count += 1
            continue

        modified = False
        for issue in file_issues:
            suggestion = issue.get("suggestion")
            if not suggestion:
                actions.append({
                    "unresolved": file_path,
                    "tool": issue["tool"],
                    "reason": "no close match found in MCP registry",
                })
                skipped_count += 1
                continue

            old_tool = issue["tool"]
            # Replace in YAML content (handles both mcp_tool: value and mcp_tool: 'value')
            new_content = content.replace(f"mcp_tool: {old_tool}", f"mcp_tool: {suggestion}")
            new_content = new_content.replace(f"mcp_tool: '{old_tool}'", f"mcp_tool: '{suggestion}'")
            new_content = new_content.replace(f'mcp_tool: "{old_tool}"', f'mcp_tool: "{suggestion}"')

            if new_content != content:
                content = new_content
                modified = True
                actions.append({
                    "fixed": file_path,
                    "tool": old_tool,
                    "replaced_with": suggestion,
                })
                fixed_count += 1
            else:
                actions.append({
                    "unresolved": file_path,
                    "tool": old_tool,
                    "reason": "replacement pattern not found in file",
                })
                skipped_count += 1

        if modified:
            path.write_text(content)
            changes.append(file_path)

    # Commit all changes
    if changes:
        rel_changes = []
        for c in changes:
            try:
                rel_changes.append(str(Path(c).relative_to(ctx.project_root)))
            except ValueError:
                rel_changes.append(c)
        _commit_files(
            ctx.project_root,
            f"fix(auto-page-health): auto-fix {fixed_count} broken MCP tool name(s)",
            rel_changes,
        )

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=f"Fixed {fixed_count}, skipped {skipped_count} broken tool reference(s)",
        fix_type="code-fix" if fixed_count > 0 else "report",
    )

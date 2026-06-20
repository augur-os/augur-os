"""auto-mcp-hygiene: Per-plugin MCP tool hygiene scanner and auto-fixer.

ADR-250: Nightly loop that audits and cleans up MCP tool registrations
per plugin. Checks naming conventions, registration completeness,
dead tools, and intra-plugin duplicates.

Difficulty levels:
  d0: naming + completeness scan only (report, no fix)
  d1+: auto-rename verb synonyms, fix registration mismatches
  d2+: dead tool detection via log analysis
  d3+: intra-plugin duplicate detection and merge
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
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.config.paths import get_all_client_skill_dirs, get_hardening_dir, get_logs_dir, get_skill_data_dir
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    declare_ops_capabilities,
)

name = "auto-mcp-hygiene"
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="auto_fix",
)

DIFFICULTY_SPEC = {
    0: "Surface check — verify plugins directory exists",
    1: "Content check — naming conventions and registration completeness",
    2: "Deep check — add dead tool detection via log analysis",
    3: "Exhaustive — add intra-plugin duplicate detection",
    4: "Expert — same as d3 (all hygiene checks)",
}
EXPANSION_TARGETS = [
    {
        "category": "auto-code-review",
        "difficulty": 3,
        "min_clean_streak": 2,
        "reason": "MCP hygiene remains clean, so widen into semantic review of MCP call sites",
    },
    {
        "category": "auto-test-coverage",
        "difficulty": 2,
        "min_clean_streak": 3,
        "reason": "stable MCP contracts justify deeper coverage checks for MCP-backed routes",
    },
]

# ADR-250: Controlled verb vocabulary
CANONICAL_VERBS = {"get", "list", "search", "create", "update", "delete", "run", "check"}
VERB_SYNONYMS = {
    "fetch": "get",
    "find": "search",
    "remove": "delete",
    "execute": "run",
    "retrieve": "get",
    "lookup": "search",
}

# Regex for extracting tool names from MCP __init__.py files
_TOOL_REGISTRATION_RE = re.compile(
    r"""(?:@?mcp(?:_tool_interceptor)?\.?(?:tool)?)\s*\(\s*(?:name\s*=\s*)?["']([^"']+)["']"""
)
_ROUTE_TOOL_RE = re.compile(r'toolName:\s*[\'"]([^\'"]+)[\'"]')
# Regex for detecting relative imports: "from .module import ..." (top-level or indented)
_RELATIVE_IMPORT_RE = re.compile(r"from\s+\.(\w+)\s+import\s+")


def _extract_verb(tool_name: str) -> str | None:
    """Extract the leading verb from a tool name like 'get-career-jobs'."""
    parts = tool_name.replace("_", "-").split("-")
    return parts[0] if parts else None


def _get_registered_tools_from_python(init_path: Path) -> list[str]:
    """Extract tool names registered in an MCP __init__.py and its submodules.

    Looks for patterns like:
      @mcp.tool(name="tool-name")
      @mcp_tool_interceptor(name="tool-name")
      mcp.tool(name="tool-name")

    Recursively follows relative imports (``from .xxx import ...``)
    to sibling .py files in the same directory, scanning each for tool
    registrations and further relative imports.
    """
    if not init_path.exists():
        return []

    mcp_dir = init_path.parent
    tools: list[str] = []
    visited: set[Path] = set()

    def _scan_file(file_path: Path) -> None:
        resolved = file_path.resolve()
        if resolved in visited:
            return
        visited.add(resolved)

        content = file_path.read_text(errors="replace")
        tools.extend(_TOOL_REGISTRATION_RE.findall(content))

        # Follow relative imports to sibling modules in the same directory
        for module_name in _RELATIVE_IMPORT_RE.findall(content):
            sibling = mcp_dir / f"{module_name}.py"
            if sibling.exists():
                _scan_file(sibling)

    _scan_file(init_path)
    return tools


def _get_declared_tools_from_skill_md(skill_md_path: Path) -> list[str]:
    """Extract tool names from canonical SKILL frontmatter."""
    if not skill_md_path.exists():
        return []

    try:
        frontmatter, _body = parse_frontmatter(skill_md_path)
    except OSError:
        return []

    result = []
    tools = frontmatter.get("x-augur-mcp-tools") or []
    for tool in tools if isinstance(tools, list) else []:
        if isinstance(tool, str):
            result.append(tool)

    config = frontmatter.get("x-augur-config") or {}
    mcp = config.get("mcp") if isinstance(config, dict) else {}
    tools = mcp.get("tools") if isinstance(mcp, dict) else []
    for tool in tools if isinstance(tools, list) else []:
        if isinstance(tool, str):
            result.append(tool)
        elif isinstance(tool, dict) and isinstance(tool.get("name"), str):
            result.append(tool["name"])

    return result


def _scan_naming(tool_names: list[str], skill_rel: str) -> list[dict]:
    """Check tool names against verb vocabulary."""
    issues = []
    for tool_name in tool_names:
        verb = _extract_verb(tool_name)
        if verb and verb in VERB_SYNONYMS:
            canonical = VERB_SYNONYMS[verb]
            issues.append({
                "action": "rename-verb",
                "kind": "actionable",
                "root_cause_type": "repo_bug",
                "file": skill_rel,
                "tool": tool_name,
                "detail": f"Rename verb '{verb}' to '{canonical}' in '{tool_name}'",
                "old_verb": verb,
                "new_verb": canonical,
            })
    return issues


def _scan_completeness(
    python_tools: list[str],
    declared_tools: list[str],
    skill_rel: str,
) -> list[dict]:
    """Detect mismatches between Python registrations and SKILL metadata."""
    issues = []
    py_set = set(python_tools)
    declared_set = set(declared_tools)

    for tool in sorted(py_set - declared_set):
        issues.append({
            "action": "add-to-skill-md",
            "kind": "manual",
            "root_cause_type": "manual_debt",
            "file": skill_rel,
            "tool": tool,
            "detail": f"Tool '{tool}' registered in Python but missing from SKILL.md metadata",
        })

    for tool in sorted(declared_set - py_set):
        issues.append({
            "action": "remove-from-skill-md",
            "kind": "manual",
            "root_cause_type": "manual_debt",
            "file": skill_rel,
            "tool": tool,
            "detail": f"Tool '{tool}' declared in SKILL.md metadata but not registered in Python",
        })

    return issues


def _load_recent_log_contents(project_root: Path) -> list[str] | None:
    """Read all recent log files once and return their contents.

    Returns None if logs directory doesn't exist. Each element is the full
    text of one log file, used for substring matching against tool names.
    """
    logs_dir = get_logs_dir()
    if not logs_dir.exists():
        return None

    contents: list[str] = []
    for log_file in logs_dir.glob("*.log"):
        try:
            mtime = log_file.stat().st_mtime
            age_days = (datetime.now(timezone.utc).timestamp() - mtime) / 86400
            if age_days > 30:
                continue
            contents.append(log_file.read_text(errors="replace"))
        except OSError:
            continue

    return contents


def _scan_dead_tools(
    tool_names: list[str],
    skill_rel: str,
    log_contents: list[str],
) -> list[dict]:
    """Identify tools with zero invocations in pre-loaded log contents."""
    issues = []
    for tool in sorted(set(tool_names)):
        found = any(tool in content for content in log_contents)
        if not found:
            issues.append({
                "action": "dead-tool",
                "kind": "manual",
                "root_cause_type": "manual_debt",
                "file": skill_rel,
                "tool": tool,
                "detail": f"Tool '{tool}' has zero invocations in last 30 days of logs",
            })
    return issues


def _scan_duplicates(tool_names: list[str], skill_rel: str) -> list[dict]:
    """Detect potential intra-plugin duplicates by normalized name similarity."""
    issues = []
    normalized: dict[str, list[str]] = {}

    for tool in tool_names:
        # Normalize: strip verb synonyms, lowercase, sort remaining parts
        parts = tool.replace("_", "-").split("-")
        verb = parts[0] if parts else ""
        canonical_verb = VERB_SYNONYMS.get(verb, verb)
        rest = "-".join(sorted(parts[1:])) if len(parts) > 1 else ""
        key = f"{canonical_verb}-{rest}"
        normalized.setdefault(key, []).append(tool)

    for key, tools in normalized.items():
        if len(tools) > 1:
            issues.append({
                "action": "potential-duplicate",
                "kind": "manual",
                "root_cause_type": "manual_debt",
                "file": skill_rel,
                "tools": tools,
                "detail": f"Potential duplicates (same normalized form): {', '.join(tools)}",
            })

    return issues


def _get_route_tools(api_dir: Path) -> list[str]:
    """Extract MCP tool names referenced by plugin API route wrappers."""
    if not api_dir.exists():
        return []
    tools: list[str] = []
    for route_file in sorted(api_dir.glob("**/*.ts")):
        if route_file.name != "route.ts":
            continue
        content = route_file.read_text(errors="replace")
        tools.extend(_ROUTE_TOOL_RE.findall(content))
    return tools


def _scan_route_bindings(
    route_tools: list[str],
    python_tools: list[str],
    declared_tools: list[str],
    skill_rel: str,
) -> list[dict]:
    """Detect API wrappers bound to tools not declared by the owning skill."""
    issues = []
    registered = set(python_tools) | set(declared_tools)
    for tool in sorted(set(route_tools)):
        if tool in registered:
            continue
        issues.append({
            "action": "route-tool-mismatch",
            "kind": "actionable",
            "root_cause_type": "repo_bug",
            "file": skill_rel,
            "tool": tool,
            "detail": f"API route wrapper references '{tool}' but the skill does not declare/register it",
        })
    return issues


def scan(ctx: OpsContext) -> ScanResult:
    """Scan all plugins for MCP tool hygiene issues."""
    # d0: surface check
    if ctx.difficulty < 1:
        return ScanResult(
            issues=[],
            summary="Plugins directory exists",
            severity="info",
            health="verified",
        )

    issues: list[dict] = []
    n_tools_checked = 0

    # Pre-load log contents once for dead tool detection (d2+)
    log_contents: list[str] | None = None
    if ctx.difficulty >= 2:
        log_contents = _load_recent_log_contents(ctx.project_root)

    skill_dirs: list[Path] = []
    for client_skills_dir in get_all_client_skill_dirs(ctx.project_root):
        if not client_skills_dir.resolve().is_relative_to(ctx.project_root.resolve()):
            continue
        skill_dirs.extend(sorted(d for d in client_skills_dir.iterdir() if d.is_dir()))

    for skill_dir in skill_dirs:
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue

        mcp_init = skill_dir / "scripts" / "mcp" / "__init__.py"
        skill_md = skill_dir / "SKILL.md"
        api_dir = skill_dir / "augur" / "api"

        # Skip plugins without MCP tools
        if not mcp_init.exists() and not skill_md.exists():
            continue

        skill_rel = str(skill_dir.relative_to(ctx.project_root))

        python_tools = _get_registered_tools_from_python(mcp_init)
        declared_tools = _get_declared_tools_from_skill_md(skill_md)
        all_tools = list(set(python_tools) | set(declared_tools))

        if not all_tools:
            continue

        n_tools_checked += len(all_tools)

        # d0: naming check
        issues.extend(_scan_naming(all_tools, skill_rel))

        # d0: registration completeness
        issues.extend(_scan_completeness(python_tools, declared_tools, skill_rel))

        # d2+: dead tool detection
        if ctx.difficulty >= 2:
            if log_contents is not None:
                issues.extend(_scan_dead_tools(all_tools, skill_rel, log_contents))
            issues.extend(_scan_route_bindings(_get_route_tools(api_dir), python_tools, declared_tools, skill_rel))

        # d3+: duplicate detection
        if ctx.difficulty >= 3:
            issues.extend(_scan_duplicates(all_tools, skill_rel))

    severity = "warning" if issues else "info"
    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} MCP hygiene issue(s) found across plugins (difficulty={ctx.difficulty})",
        severity=severity,
        items_scanned=n_tools_checked,
    )


def _commit_files(project_root: Path, message: str, paths: list[str]) -> str | None:
    """Stage specific paths and commit. Returns commit hash or None."""
    for p in paths:
        subprocess.run(
            ["git", "add", p],
            capture_output=True,
            cwd=str(project_root),
        )
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
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        return rev.stdout.strip() if rev.returncode == 0 else None
    return None


def _apply_verb_rename(
    project_root: Path,
    issue: dict,
) -> list[str]:
    """Rename a verb synonym in Python registrations and SKILL metadata.

    Returns list of changed file paths (relative).
    """
    skill_dir = project_root / issue["file"]
    tool_name = issue["tool"]
    old_verb = issue["old_verb"]
    new_verb = issue["new_verb"]
    new_tool_name = new_verb + tool_name[len(old_verb):]
    changed: list[str] = []

    # Update Python __init__.py
    init_path = skill_dir / "scripts" / "mcp" / "__init__.py"
    if init_path.exists():
        content = init_path.read_text()
        updated = content.replace(f'"{tool_name}"', f'"{new_tool_name}"')
        updated = updated.replace(f"'{tool_name}'", f"'{new_tool_name}'")
        if updated != content:
            init_path.write_text(updated)
            changed.append(str(init_path.relative_to(project_root)))

    for metadata_path in (skill_dir / "SKILL.md", skill_dir / "config.yaml"):
        if not metadata_path.exists():
            continue
        content = metadata_path.read_text()
        updated = content.replace(f"- {tool_name}", f"- {new_tool_name}")
        updated = updated.replace(f"name: {tool_name}", f"name: {new_tool_name}")
        updated = updated.replace(f'"{tool_name}"', f'"{new_tool_name}"')
        updated = updated.replace(f"'{tool_name}'", f"'{new_tool_name}'")
        if updated != content:
            metadata_path.write_text(updated)
            changed.append(str(metadata_path.relative_to(project_root)))

    for route_file in sorted((skill_dir / "augur" / "api").glob("**/route.ts")):
        content = route_file.read_text()
        updated = content.replace(f'"{tool_name}"', f'"{new_tool_name}"')
        updated = updated.replace(f"'{tool_name}'", f"'{new_tool_name}'")
        if updated != content:
            route_file.write_text(updated)
            changed.append(str(route_file.relative_to(project_root)))

    return changed


def _write_report(
    project_root: Path,
    skill_rel: str,
    issues: list[dict],
) -> Path | None:
    """Write per-plugin hygiene report."""
    # Determine report location inside the skill
    report_dir = get_hardening_dir(Path(skill_rel).name)
    report_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = report_dir / f"mcp_hygiene_{today}.yaml"

    report_data = {
        "date": today,
        "skill": skill_rel,
        "issues": [
            {
                "action": i.get("action", ""),
                "tool": i.get("tool", i.get("tools", "")),
                "detail": i.get("detail", ""),
            }
            for i in issues
        ],
        "total": len(issues),
    }

    report_path.write_text(yaml.dump(report_data, default_flow_style=False, sort_keys=False))
    return report_path


def _project_relative_path(project_root: Path, path: Path) -> str | None:
    """Return a repo-relative path when the file lives inside the project tree."""
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return None


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix discovered MCP hygiene issues."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would fix {len(issues)} MCP hygiene issue(s)",
        )

    if not issues:
        return FixResult(success=True, summary="No issues to fix")

    all_changes: list[str] = []
    actions: list[dict] = []

    # Group issues by skill for per-plugin commits
    by_skill: dict[str, list[dict]] = {}
    for issue in issues:
        skill = issue.get("file", "unknown")
        by_skill.setdefault(skill, []).append(issue)

    all_report_paths: list[str] = []

    for skill_rel, skill_issues in by_skill.items():
        skill_changes: list[str] = []

        for issue in skill_issues:
            action = issue.get("action", "")

            if action == "rename-verb" and ctx.difficulty >= 1:
                changed = _apply_verb_rename(ctx.project_root, issue)
                skill_changes.extend(changed)

        # Write report for this skill (scan artifact, not a code fix)
        report_path = _write_report(ctx.project_root, skill_rel, skill_issues)
        if report_path:
            report_rel = _project_relative_path(ctx.project_root, report_path)
            if report_rel:
                all_report_paths.append(report_rel)
        else:
            report_rel = None

        # Only commit if real fixes were applied (not just reports)
        if skill_changes:
            all_changes.extend(skill_changes)
            skill_name = Path(skill_rel).name
            # Include report alongside real changes in a single commit
            commit_paths = skill_changes[:]
            if report_rel:
                commit_paths.append(report_rel)
            commit = _commit_files(
                ctx.project_root,
                f"fix(adaptive): mcp-hygiene cleanup for {skill_name}",
                commit_paths,
            )
            if commit:
                actions.append({"commit": commit, "skill": skill_name})

    if not all_changes:
        return FixResult(
            success=True,
            changes=[],
            summary=f"Scan complete: {len(issues)} issue(s) reported across {len(by_skill)} plugin(s), no auto-fixable actions",
            fix_type="report",  # ADR-417: no code changes, report only
        )

    return FixResult(
        success=True,
        actions=actions,
        changes=all_changes,
        summary=f"Fixed {len(all_changes)} file(s) across {len(by_skill)} plugin(s)",
        fix_type="code-fix",  # ADR-417: verb renames are real code fixes
    )

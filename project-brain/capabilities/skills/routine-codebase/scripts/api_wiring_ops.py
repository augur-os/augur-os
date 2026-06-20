"""auto-api-wiring: Validate API route toolName references match MCP tool registrations.

Scans all API route files for toolName declarations and cross-references against
actual @mcp.tool(name=...) registrations in Python. Also detects direct fs/spawn
bypasses in API routes (CLAUDE.md rule #11).

Categories:
  A — toolName doesn't match any registered MCP tool
  B — CRUD splits (create-/update-/delete- when only manage- exists)
  D — Direct fs/spawn/exec usage in API routes
  E — Fuzzy match closest registered tool for unresolved names
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
from difflib import get_close_matches
from pathlib import Path

import subprocess

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, report_only_fix

name = "auto-api-wiring"

DIFFICULTY_SPEC = {
    0: "Surface — count API routes and MCP tool registrations",
    1: "Cat A — toolName must match registered MCP tool",
    2: "Cat B — detect CRUD splits vs manage-* pattern",
    3: "Cat D — detect fs/spawn/exec bypasses in routes",
    4: "Cat E — fuzzy match unresolved toolNames to closest tools",
}

# Patterns to extract toolName from TypeScript route files
_TOOL_NAME_RE = re.compile(r"""toolName:\s*['"]([^'"]+)['"]""")

# Pattern to extract @mcp.tool(name="...") from Python files
_MCP_TOOL_RE = re.compile(r"""name\s*=\s*['"]([^'"]+)['"]""")

# Imports/usage that indicate direct fs/spawn bypass
_FS_BYPASS_PATTERNS = [
    re.compile(r"""from\s+['"]fs['"]"""),
    re.compile(r"""from\s+['"]fs/promises['"]"""),
    re.compile(r"""import\s+fs\b"""),
    re.compile(r"""require\s*\(\s*['"]fs(?:/promises)?['"]\s*\)"""),
    re.compile(r"""from\s+['"]child_process['"]"""),
    re.compile(r"""require\s*\(\s*['"]child_process['"]\s*\)"""),
    re.compile(r"""\bspawn\s*\("""),
    re.compile(r"""\bexecSync\s*\("""),
    re.compile(r"""\bexecFile\s*\("""),
    re.compile(r"""\bfs\.\w+\s*\("""),
]

# ADR-266 exemption marker
_EXEMPTION_RE = re.compile(r"@fs-exempt:|ADR-266\s+exemption|TODO_BUG\(adr-266\)", re.IGNORECASE)


_ROUTE_GLOBS = [
    "plugins/*/skills/*/augur/api/**/route.ts",
    "project-brain/capabilities/skills/*/augur/api/**/route.ts",
    "apps/dashboard/app/api/**/route.ts",
]

_MCP_GLOBS = [
    "src/mcp/augur_core/**/*.py",
    "src/mcp/augur_framework/**/*.py",
    "src/mcp/augur_shared/**/*.py",
    "plugins/*/skills/*/scripts/mcp/*.py",
    "project-brain/capabilities/skills/*/scripts/mcp/*.py",
    "project-brain/capabilities/skills/*/scripts/**/*.py",
]


def _iter_route_files(project_root: Path):
    """Yield all API route files from all known locations, deduplicating."""
    seen: set[str] = set()
    for pattern in _ROUTE_GLOBS:
        for f in sorted(project_root.glob(pattern)):
            content = f.read_text(errors="replace")
            # Skip auto-generated copies to avoid double-counting
            if "AUTO-GENERATED FILE" in content[:300]:
                continue
            rel = str(f.relative_to(project_root))
            if rel not in seen:
                seen.add(rel)
                yield f, rel, content


def _collect_route_tool_names(project_root: Path) -> list[dict]:
    """Extract toolName from all API route files."""
    results = []
    for route_file, rel, content in _iter_route_files(project_root):
        for match in _TOOL_NAME_RE.finditer(content):
            results.append({
                "tool_name": match.group(1),
                "file": rel,
                "line": content[: match.start()].count("\n") + 1,
            })
    return results


def _collect_mcp_registrations(project_root: Path) -> set[str]:
    """Extract all @mcp.tool(name=...) from Python MCP scripts."""
    tools: set[str] = set()
    seen_files: set[str] = set()
    for pattern in _MCP_GLOBS:
        for py_file in sorted(project_root.glob(pattern)):
            rel = str(py_file.relative_to(project_root))
            if rel in seen_files:
                continue
            # Skip vendored / virtualenv directories
            if ".venv" in rel or "site-packages" in rel:
                continue
            seen_files.add(rel)
            content = py_file.read_text(errors="replace")
            # Only match name= that appears near @mcp.tool
            for block in re.finditer(r"@mcp\.tool\([^)]*\)", content, re.DOTALL):
                for name_match in _MCP_TOOL_RE.finditer(block.group(0)):
                    tools.add(name_match.group(1))
    return tools


def _check_fs_bypass(project_root: Path) -> list[dict]:
    """Detect direct fs/spawn/exec usage in API route files."""
    issues = []
    for route_file, rel, content in _iter_route_files(project_root):
        # Skip files with ADR-266 exemption
        if _EXEMPTION_RE.search(content):
            continue

        lines = content.splitlines()
        for pattern in _FS_BYPASS_PATTERNS:
            for match in pattern.finditer(content):
                line_num = content[: match.start()].count("\n")
                line_text = lines[line_num] if line_num < len(lines) else ""
                # Skip matches inside comments
                stripped = line_text.lstrip()
                if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
                    continue
                issues.append({
                    "category": "D",
                    "type": "fs_bypass",
                    "file": rel,
                    "line": line_num + 1,
                    "detail": f"Direct fs/spawn usage: {match.group(0).strip()[:60]}",
                })
                break  # One hit per pattern per file is enough
    return issues


def scan(ctx: OpsContext) -> ScanResult:
    """Validate API route → MCP tool wiring."""
    route_refs = _collect_route_tool_names(ctx.project_root)
    mcp_tools = _collect_mcp_registrations(ctx.project_root)

    if ctx.difficulty < 1:
        return ScanResult(
            issues=[],
            summary=f"{len(route_refs)} API route toolName refs, {len(mcp_tools)} MCP tools registered (d0 surface)",
            severity="info",
            health="verified",
        )

    issues: list[dict] = []
    unresolved_names: list[dict] = []

    # d1: Cat A — toolName must match registered MCP tool
    for ref in route_refs:
        if ref["tool_name"] not in mcp_tools:
            issue = {
                "category": "A",
                "type": "missing_tool",
                "tool_name": ref["tool_name"],
                "file": ref["file"],
                "line": ref["line"],
                "detail": f"toolName '{ref['tool_name']}' not found in MCP registrations",
            }
            issues.append(issue)
            unresolved_names.append(ref)

    # d2: Cat B — detect CRUD splits
    if ctx.difficulty >= 2:
        crud_prefixes = ("create-", "update-", "delete-", "add-", "toggle-", "remove-")
        for ref in unresolved_names:
            tool = ref["tool_name"]
            for prefix in crud_prefixes:
                if tool.startswith(prefix):
                    noun = tool[len(prefix):]
                    # Check if manage-{noun} or manage-{noun}s exists
                    manage_candidates = [f"manage-{noun}", f"manage-{noun}s"]
                    found = [c for c in manage_candidates if c in mcp_tools]
                    if found:
                        # Find the existing issue and annotate it
                        for iss in issues:
                            if iss.get("tool_name") == tool:
                                iss["category"] = "B"
                                iss["type"] = "crud_split"
                                iss["suggested_tool"] = found[0]
                                iss["detail"] = (
                                    f"Route calls '{tool}' but MCP has '{found[0]}' "
                                    f"with action param — use manage-* pattern"
                                )
                                break
                    break

    # d3: Cat D — fs/spawn bypass
    if ctx.difficulty >= 3:
        issues.extend(_check_fs_bypass(ctx.project_root))

    # d4: Cat E — fuzzy match
    if ctx.difficulty >= 4:
        tool_list = sorted(mcp_tools)
        for ref in unresolved_names:
            tool = ref["tool_name"]
            # Skip if already categorized as B
            matching_issue = next((i for i in issues if i.get("tool_name") == tool), None)
            if matching_issue and matching_issue.get("category") == "B":
                continue
            matches = get_close_matches(tool, tool_list, n=3, cutoff=0.6)
            if matches and matching_issue:
                matching_issue["category"] = "E"
                matching_issue["type"] = "fuzzy_match"
                matching_issue["suggestions"] = matches
                matching_issue["detail"] = (
                    f"toolName '{tool}' not found. Close matches: {', '.join(matches)}"
                )

    severity = "warning" if issues else "info"
    health = "degraded" if any(i.get("category") == "A" for i in issues) else "verified"

    cat_counts = {}
    for iss in issues:
        cat = iss.get("category", "?")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    cat_summary = ", ".join(f"Cat {k}: {v}" for k, v in sorted(cat_counts.items()))

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} wiring issue(s) ({cat_summary})" if issues else "All API routes correctly wired",
        severity=severity,
        health=health,
    )


def _replace_tool_name(project_root: Path, file_path: str, old_name: str, new_name: str) -> bool:
    """Replace a toolName value in a route file. Returns True if changed."""
    full_path = project_root / file_path
    try:
        content = full_path.read_text()
    except OSError:
        return False
    # Replace the exact toolName string, preserving quote style
    for quote in ('"', "'"):
        old = f"toolName: {quote}{old_name}{quote}"
        new = f"toolName: {quote}{new_name}{quote}"
        if old in content:
            content = content.replace(old, new, 1)
            full_path.write_text(content)
            return True
    return False


def fix(ctx: OpsContext, issues: list[dict]):
    """Auto-fix Cat B (CRUD splits) and Cat E (single fuzzy match) toolName issues.

    Cat A (missing, no suggestion) and Cat D (fs bypass) remain report-only
    since they require human judgment.
    """
    if ctx.dry_run:
        fixable = sum(1 for i in issues if i.get("category") in ("B", "E"))
        return FixResult(
            success=True,
            summary=f"Dry run: {fixable} auto-fixable, {len(issues) - fixable} manual",
        )

    changes: list[str] = []
    manual: list[dict] = []

    for issue in issues:
        cat = issue.get("category")
        tool_name = issue.get("tool_name", "")
        file_path = issue.get("file", "")

        if cat == "B":
            # CRUD split -> use manage-* tool
            suggested = issue.get("suggested_tool")
            if suggested and _replace_tool_name(ctx.project_root, file_path, tool_name, suggested):
                changes.append(file_path)
            else:
                manual.append(issue)

        elif cat == "E":
            # Fuzzy match -> use first suggestion only if there's exactly one
            suggestions = issue.get("suggestions", [])
            if len(suggestions) == 1:
                if _replace_tool_name(ctx.project_root, file_path, tool_name, suggestions[0]):
                    changes.append(file_path)
                else:
                    manual.append(issue)
            else:
                manual.append(issue)
        else:
            # Cat A (no suggestion) and Cat D (fs bypass) are manual
            manual.append(issue)

    if not changes:
        return report_only_fix(ctx, "api-wiring-latest.json", issues, noun="wiring issue")

    # Commit the fixes
    for p in changes:
        subprocess.run(["git", "add", p], capture_output=True, cwd=str(ctx.project_root))
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True, cwd=str(ctx.project_root),
    )
    sha = None
    if result.returncode != 0:
        result = subprocess.run(
            ["git", "commit", "-m", "fix(api-wiring): auto-correct toolName references"],
            capture_output=True, text=True, cwd=str(ctx.project_root),
        )
        if result.returncode == 0:
            rev = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, cwd=str(ctx.project_root),
            )
            sha = rev.stdout.strip() if rev.returncode == 0 else None

    summary = f"Fixed {len(changes)} toolName(s) in route files"
    if manual:
        summary += f"; {len(manual)} issue(s) remain (manual)"
    if sha:
        summary += f" (commit {sha})"

    return FixResult(
        success=True,
        changes=changes,
        actions=[{"commit": sha}] if sha else [],
        summary=summary,
        fix_type="code-fix",
    )

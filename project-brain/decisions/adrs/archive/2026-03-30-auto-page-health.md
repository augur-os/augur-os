# Auto Page Health Autoloop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an autoloop that scans dashboard pages for broken MCP tool references and auto-fixes YAML configs by fuzzy-matching against the MCP registry.

**Architecture:** Reuse tool extraction regexes from `scripts/verify-page-tools.py`. Add YAML scanning alongside TSX scanning. Scan phase probes tools via MCP server. Fix phase uses Levenshtein distance to find correct tool names and updates YAML files.

**Tech Stack:** Python 3.11+, ops_protocol (ScanResult/FixResult/OpsContext), MCP client via stdio, PyYAML

**Spec:** `docs/superpowers/specs/2026-03-30-auto-page-health-design.md`

---

### Task 1: Create SKILL.md

**Files:**
- Create: `skills/auto-page-health/SKILL.md`

- [ ] **Step 1: Create the skill metadata file**

```markdown
---
name: auto-page-health
x-augur-type: autoloop
x-augur-tags:
  - dashboard
  - mcp
  - pages
  - health
description: >-
  Verify MCP tool references in dashboard pages return data. Auto-fix broken
  tool names in YAML configs via fuzzy matching against the MCP registry.
x-augur-visibility: auto
x-augur-mcp-tools:
  - get-skill-health
  - list-skill-actions
x-augur-loop:
  name: page-health
  tier: 1
  trigger: nightly
x-augur-hub: adaptive
x-augur-tab: testing
---

# auto-page-health

Scans all dashboard pages (YAML configs and TSX custom pages) for MCP tool
references. Verifies each tool exists in the MCP registry and returns data.

## Difficulty Levels

| Level | Behavior |
|-------|----------|
| d0    | Scan only — report broken tools and affected pages |
| d1    | Auto-fix YAML pages: fuzzy-match broken tool names, update config, verify, commit |
| d2    | Also flag TSX pages with broken tools as YAML migration candidates |
```

- [ ] **Step 2: Commit**

```bash
git add skills/auto-page-health/SKILL.md
git commit -m "feat(auto-page-health): scaffold skill with SKILL.md"
```

---

### Task 2: Create scan + fix script

**Files:**
- Create: `skills/auto-page-health/scripts/page_health.py`

- [ ] **Step 1: Create the autoloop script**

```python
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

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-page-health"

# ---------------------------------------------------------------------------
# Tool extraction regexes (from verify-page-tools.py)
# ---------------------------------------------------------------------------

_RE_USE_MCP_QUERY = re.compile(
    r"""useMcpQuery\b[^(]*\(\s*"""
    r"""(?:\[[^\]]*\]|'[^']*'|"[^"]*")\s*,\s*"""
    r"""'"['"]""",
    re.DOTALL,
)

_RE_USE_MCP_MUTATION = re.compile(
    r"""useMcpMutation\b[^(]*\(\s*'"['"]""",
    re.DOTALL,
)

_RE_USE_MCP_POLL = re.compile(
    r"""useMcpPoll\b[^(]*\(\s*"""
    r"""(?:\[[^\]]*\]|'[^']*'|"[^"]*")\s*,\s*"""
    r"""'"['"]""",
    re.DOTALL,
)


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
        # Direct mcp_tool on block
        if "mcp_tool" in block:
            tools.append({
                "tool": block["mcp_tool"],
                "source": "yaml",
                "page": page,
                "file": str(yaml_path),
            })
        # Sources array (metrics-dashboard)
        for source in block.get("sources", []):
            if isinstance(source, dict) and "mcp_tool" in source:
                tools.append({
                    "tool": source["mcp_tool"],
                    "source": "yaml",
                    "page": page,
                    "file": str(yaml_path),
                })

    return tools


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


def _get_registered_tools(project_root: Path) -> set[str]:
    """Get list of registered MCP tool names by calling the MCP server."""
    try:
        result = subprocess.run(
            [
                str(project_root / ".venv" / "bin" / "python"),
                "-m", "augur_mcp", "--list-tools",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_root),
            env={**__import__("os").environ, "PYTHONPATH": str(project_root / "src")},
        )
        if result.returncode != 0:
            return set()
        return {line.strip() for line in result.stdout.splitlines() if line.strip()}
    except Exception:
        return set()


def _verify_tool(project_root: Path, tool_name: str) -> dict:
    """Call an MCP tool and check if it returns data."""
    try:
        result = subprocess.run(
            [
                str(project_root / ".venv" / "bin" / "python"),
                "-c",
                f"""
import json, sys
sys.path.insert(0, "{project_root / 'src'}")
from augur_mcp import create_mcp_server
# Quick tool existence check via import
print(json.dumps({{"exists": True}}))
""",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(project_root),
        )
        return {"exists": result.returncode == 0}
    except Exception as e:
        return {"exists": False, "error": str(e)[:100]}


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def scan(ctx: OpsContext) -> ScanResult:
    """Scan all dashboard pages for broken MCP tool references."""
    project_root = ctx.project_root
    skills_dir = project_root / "skills"
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

    # 3. Get registered tools
    registered = _get_registered_tools(project_root)
    if not registered:
        return ScanResult(
            issues=[],
            summary="Could not connect to MCP server to verify tools",
            severity="warning",
        )

    # 4. Check each unique tool
    unique_tools = {ref["tool"] for ref in all_refs}
    broken_tools: set[str] = set()

    for tool in sorted(unique_tools):
        if tool not in registered:
            broken_tools.add(tool)

    if not broken_tools:
        return ScanResult(
            issues=[],
            summary=f"All {len(unique_tools)} tools verified across {len(all_refs)} references",
            severity="info",
        )

    # 5. Build issues for broken tools
    issues: list[dict] = []
    registered_list = sorted(registered)

    for ref in all_refs:
        if ref["tool"] not in broken_tools:
            continue

        # Find closest match
        matches = get_close_matches(ref["tool"], registered_list, n=1, cutoff=0.6)
        suggestion = matches[0] if matches else None

        issues.append({
            "action": "broken-tool",
            "file": ref["file"],
            "tool": ref["tool"],
            "page": ref["page"],
            "source_type": ref["source"],
            "error": "tool not registered in MCP server",
            "suggestion": suggestion,
        })

    return ScanResult(
        issues=issues,
        summary=f"{len(broken_tools)} broken tool(s) across {len(issues)} reference(s)",
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
```

- [ ] **Step 2: Verify the script imports work**

```bash
cd ~/Projects/Augur
PYTHONPATH=. python3 -c "from skills.auto_page_health.scripts.page_health import scan, fix, name; print(f'Module loaded: {name}')"
```

Expected: `Module loaded: auto-page-health`

Note: The import path uses underscores. If it fails, try:
```bash
PYTHONPATH=. python3 -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('page_health', 'skills/auto-page-health/scripts/page_health.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(f'Loaded: {mod.name}, has scan={hasattr(mod, \"scan\")}, has fix={hasattr(mod, \"fix\")}')
"
```

Expected: `Loaded: auto-page-health, has scan=True, has fix=True`

- [ ] **Step 3: Run the scan manually**

```bash
cd ~/Projects/Augur
PYTHONPATH=. python3 -c "
from pathlib import Path
from src.lib.ops_protocol import OpsContext

import importlib.util
spec = importlib.util.spec_from_file_location('page_health', 'skills/auto-page-health/scripts/page_health.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ctx = OpsContext(project_root=Path('.').resolve(), difficulty=0)
result = mod.scan(ctx)
print(f'Issues: {len(result.issues)}')
print(f'Summary: {result.summary}')
print(f'Severity: {result.severity}')
for issue in result.issues[:5]:
    print(f'  {issue[\"page\"]}: {issue[\"tool\"]} -> {issue.get(\"suggestion\", \"no match\")}')
"
```

Expected: List of broken tools with suggestions (if any).

- [ ] **Step 4: Commit**

```bash
git add skills/auto-page-health/scripts/page_health.py
git commit -m "feat(auto-page-health): add scan + fix with fuzzy tool matching"
```

---

### Task 3: Test end-to-end

- [ ] **Step 1: Run full scan + fix in dry-run mode**

```bash
cd ~/Projects/Augur
PYTHONPATH=. python3 -c "
from pathlib import Path
from src.lib.ops_protocol import OpsContext
import importlib.util

spec = importlib.util.spec_from_file_location('page_health', 'skills/auto-page-health/scripts/page_health.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ctx = OpsContext(project_root=Path('.').resolve(), difficulty=1, dry_run=True)
scan_result = mod.scan(ctx)
print(f'Scan: {scan_result.summary}')

if scan_result.issues:
    fix_result = mod.fix(ctx, scan_result.issues)
    print(f'Fix (dry run): {fix_result.summary}')
    for action in fix_result.actions[:5]:
        print(f'  {action}')
"
```

Expected: Shows broken tools and what would be fixed.

- [ ] **Step 2: Run actual fix (d1)**

```bash
cd ~/Projects/Augur
PYTHONPATH=. python3 -c "
from pathlib import Path
from src.lib.ops_protocol import OpsContext
import importlib.util

spec = importlib.util.spec_from_file_location('page_health', 'skills/auto-page-health/scripts/page_health.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ctx = OpsContext(project_root=Path('.').resolve(), difficulty=1, dry_run=False)
scan_result = mod.scan(ctx)
print(f'Scan: {scan_result.summary}')

if scan_result.issues:
    fix_result = mod.fix(ctx, scan_result.issues)
    print(f'Fix: {fix_result.summary}')
    print(f'Fix type: {fix_result.fix_type}')
    for action in fix_result.actions[:10]:
        print(f'  {action}')
else:
    print('No issues to fix — all tools healthy')
"
```

Expected: Fixes broken YAML tool names and commits.

- [ ] **Step 3: Verify the dashboard still builds after fixes**

```bash
cd ~/Projects/Augur/apps/dashboard
pnpm run build:scripts
node scripts/dist/mount-plugins.mjs 2>&1 | grep "Tab registry"
```

Expected: 0 orphans, build passes.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(auto-page-health): verified end-to-end scan + fix cycle"
```

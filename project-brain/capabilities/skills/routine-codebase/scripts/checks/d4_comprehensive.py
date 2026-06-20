"""d4: Exhaustive — Jest + TypeScript + data shape + response time + view CRUD + evolution."""
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
import subprocess
import time
import urllib.request
from pathlib import Path

import yaml

from src.lib.ops_protocol import check_http_route, evolution_gap, make_issue

# Block type shape expectations
BLOCK_TYPE_EXPECTS = {
    "data-table": {"shape": "array", "desc": "array of objects"},
    "data-list": {"shape": "array", "desc": "array of objects"},
    "card-grid": {"shape": "array", "desc": "array of objects"},
    "stat-grid": {"shape": "array", "desc": "array of {value, label}"},
    "stat-card": {"shape": "object", "desc": "object with value fields"},
    "progress": {"shape": "object", "desc": "object with progress data"},
    "calendar": {"shape": "array", "desc": "array of events"},
    "activity-feed": {"shape": "array", "desc": "array of activities"},
    "chart": {"shape": "any", "desc": "chart data (varies)"},
    "markdown": {"shape": "any", "desc": "markdown content"},
    "notes": {"shape": "any", "desc": "notes data"},
    "embed": {"shape": "any", "desc": "embed config"},
    "action-bar": {"shape": "any", "desc": "action definitions"},
    "ops-board": {"shape": "any", "desc": "ops data"},
}


def _unwrap_tool_data(data):
    """Mirror the client-side unwrapToolData() from useBlockData.ts."""
    if not data or not isinstance(data, dict) or isinstance(data, list):
        return data
    if "connected" in data:
        return data
    if "error" in data and data["error"] is True:
        return data
    keys = list(data.keys())
    # Single-key dict with array value
    if len(keys) == 1 and isinstance(data[keys[0]], list):
        return data[keys[0]]
    # Well-known data keys
    for key in ("items", "data", "results", "entries", "rows", "records", "list",
                 "stories", "resumes", "notes", "documents", "files", "skills",
                 "agents", "events", "actions", "tools", "sessions", "jobs",
                 "startups", "categories", "accounts", "transactions", "logs",
                 "templates", "projects", "opportunities", "organizations",
                 "teams", "ideas", "candidates", "commits", "notifications",
                 "inbox", "services", "plugins", "automations", "providers",
                 "emails", "memos", "loops", "battlecards", "investor_qa",
                 "competitor_landscape", "lights", "scenes", "reminders"):
        if key in data and isinstance(data[key], list):
            return data[key]
    # total + one array key
    array_keys = [k for k in keys if isinstance(data[k], list)]
    non_array_keys = [k for k in keys if not isinstance(data[k], list)]
    if len(array_keys) == 1 and all(k in ("total", "count", "page", "hasMore") for k in non_array_keys):
        return data[array_keys[0]]
    # All scalar values -> convert to [{value, label}] for stat-grid/stat-card
    all_scalar = all(isinstance(data[k], (str, int, float, bool)) for k in keys)
    if all_scalar and 2 <= len(keys) <= 12:
        return [{"value": data[k], "label": k} for k in keys]
    return data


def _collect_block_defs(project_root: Path) -> list[dict]:
    """Collect blocks with their types and tools from SKILL.md files."""
    block_defs: list[dict] = []
    for yf in (project_root / "project-brain" / "capabilities" / "skills").glob("*/SKILL.md"):
        try:
            text = yf.read_text()
            if not text.startswith("---"):
                continue
            _, fm, _ = text.split("---", 2)
            data = yaml.safe_load(fm)
        except Exception:
            continue
        if not data:
            continue
        config = data.get("x-augur-config", {}) or {}
        if "contributions" not in config:
            continue
        skill_name = data.get("name", "?")
        for block in config.get("contributions", {}).get("blocks", []):
            ds = block.get("data_source", {})
            tool = ds.get("mcp_tool") if ds else None
            if tool:
                block_defs.append({
                    "bid": f"{skill_name}:{block.get('id', '?')}",
                    "type": block.get("type", "?"),
                    "tool": tool,
                })
    return block_defs


def _check_data_shapes(base_url: str, timeout: int, block_defs: list[dict]) -> list[dict]:
    """Test data shape for each block and track slow/empty responses."""
    issues: list[dict] = []
    slow_tools: list[dict] = []

    for bdef in block_defs:
        expected = BLOCK_TYPE_EXPECTS.get(bdef["type"], {})
        expected_shape = expected.get("shape", "any")
        if expected_shape == "any":
            continue  # Skip types with flexible shapes

        try:
            start = time.time()
            req = urllib.request.Request(
                f"{base_url}/api/blocks/data",
                data=json.dumps({"tool": bdef["tool"], "args": {}}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310  # base_url validated by check_http_route guard above
                elapsed = time.time() - start
                result = json.loads(resp.read())
                tool_data = _unwrap_tool_data(result.get("data"))

                # Check response time
                if elapsed > 5.0:
                    slow_tools.append({
                        "bid": bdef["bid"],
                        "tool": bdef["tool"],
                        "elapsed": round(elapsed, 1),
                    })

                if tool_data is None:
                    continue

                actual_data = tool_data

                # Skip shape check for "not connected" responses and error responses
                if isinstance(actual_data, dict) and ("connected" in actual_data or ("error" in actual_data and isinstance(actual_data["error"], str))):
                    continue

                # Check shape
                if expected_shape == "array" and not isinstance(actual_data, list):
                    issues.append(make_issue(
                        category="webmcp-shape",
                        detail=f"Block {bdef['bid']} ({bdef['type']}) expects {expected['desc']} but got {type(actual_data).__name__} from {bdef['tool']}",
                        path=f"mcp:{bdef['tool']}",
                        kind="actionable",
                        root_cause_type="repo_bug",
                    ))
                elif expected_shape == "object" and not isinstance(actual_data, dict):
                    if not isinstance(actual_data, list):
                        issues.append(make_issue(
                            category="webmcp-shape",
                            detail=f"Block {bdef['bid']} ({bdef['type']}) expects {expected['desc']} but got {type(actual_data).__name__}",
                            path=f"mcp:{bdef['tool']}",
                            kind="actionable",
                            root_cause_type="repo_bug",
                        ))

        except Exception:
            pass  # Already caught by d3

    # Report slow tools
    for slow in slow_tools:
        issues.append(make_issue(
            category="webmcp-perf",
            detail=f"Block {slow['bid']} tool '{slow['tool']}' took {slow['elapsed']}s (>5s threshold)",
            path=f"mcp:{slow['tool']}",
            kind="maintenance",
            root_cause_type="repo_bug",
        ))

    return issues


def _check_view_crud(base_url: str, timeout: int) -> list[dict]:
    """Test view CRUD operations."""
    issues: list[dict] = []

    try:
        # Create a test view
        req = urllib.request.Request(
            f"{base_url}/api/views",
            data=json.dumps({"title": "__webmcp_test_view"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310  # base_url validated by check_http_route guard above
            view_data = json.loads(resp.read())
            view_id = view_data.get("id") or view_data.get("view", {}).get("id")

            if view_id:
                # Read it back
                req2 = urllib.request.Request(f"{base_url}/api/views/{view_id}")
                with urllib.request.urlopen(req2, timeout=timeout) as resp2:  # nosec B310  # base_url validated by check_http_route guard above
                    read_data = json.loads(resp2.read())
                    if not read_data.get("title") and not read_data.get("id"):
                        issues.append(make_issue(
                            category="webmcp-views",
                            detail="View CRUD: created view but read-back returned no data",
                            kind="actionable",
                        ))

                # Delete it
                req3 = urllib.request.Request(
                    f"{base_url}/api/views/{view_id}",
                    method="DELETE",
                )
                urllib.request.urlopen(req3, timeout=timeout)  # nosec B310  # base_url validated by check_http_route guard above
            else:
                issues.append(make_issue(
                    category="webmcp-views",
                    detail="View CRUD: create returned no view ID",
                    kind="actionable",
                ))
    except Exception as e:
        issues.append(make_issue(
            category="webmcp-views",
            detail=f"View CRUD test failed: {e}",
            kind="actionable",
        ))

    return issues


def _check_jest(project_root: Path) -> list[dict]:
    """Run Jest tests for WebMCP."""
    issues: list[dict] = []

    test_dir = project_root / "tests" / "dashboard" / "lib" / "webmcp"
    if not test_dir.exists():
        return issues

    try:
        result = subprocess.run(
            ["npx", "jest", str(test_dir), "--no-cache", "--json"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(project_root / "apps" / "dashboard"),
        )
        if result.returncode != 0:
            try:
                jest_out = json.loads(result.stdout)
                for suite in jest_out.get("testResults", []):
                    if suite.get("status") == "failed":
                        failures = [
                            t.get("fullName", "?")
                            for t in suite.get("assertionResults", [])
                            if t.get("status") == "failed"
                        ]
                        issues.append(make_issue(
                            category="webmcp-jest",
                            detail=f"Test suite {Path(suite['name']).name} failed: {', '.join(failures[:3])}",
                            path=suite.get("name", ""),
                            kind="actionable",
                            root_cause_type="repo_bug",
                        ))
            except (json.JSONDecodeError, KeyError):
                issues.append(make_issue(
                    category="webmcp-jest",
                    detail=f"Jest failed (exit {result.returncode})",
                    kind="actionable",
                ))
    except subprocess.TimeoutExpired:
        issues.append(make_issue(
            category="webmcp-jest",
            detail="Jest timed out (120s)",
            kind="environment",
        ))

    return issues


def _check_typescript(project_root: Path) -> list[dict]:
    """Run TypeScript type checking."""
    issues: list[dict] = []

    try:
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(project_root / "apps" / "dashboard"),
        )
        if result.returncode != 0:
            # Count TS errors
            error_lines = [l for l in result.stdout.splitlines() if "error TS" in l]
            webmcp_errors = [l for l in error_lines if "webmcp" in l.lower()]
            issues.append(make_issue(
                category="webmcp-tsc",
                detail=f"TypeScript: {len(error_lines)} total errors, {len(webmcp_errors)} in webmcp files",
                kind="actionable",
                root_cause_type="repo_bug",
            ))
    except subprocess.TimeoutExpired:
        issues.append(make_issue(
            category="webmcp-tsc",
            detail="TypeScript check timed out (120s)",
            kind="environment",
        ))

    return issues


def check_evolution(project_root: Path, base_url: str) -> list[dict]:
    """When all current checks pass, identify untested areas to raise the bar.

    A permanently green loop is a useless loop. This function ensures the scanner
    always reports honest coverage gaps so the bar keeps rising.
    """
    gaps: list[dict] = []

    # Gap 1: No browser rendering tests
    playwright_webmcp_tests = list((project_root / "tests").rglob("*webmcp*playwright*"))
    e2e_webmcp_tests = list((project_root / "tests").rglob("*webmcp*e2e*"))
    if not playwright_webmcp_tests and not e2e_webmcp_tests:
        gaps.append(evolution_gap(
            "No browser rendering tests — blocks verified via API only, not actual DOM rendering. "
            "Next: add Playwright tests that load dashboard pages and verify blocks render visible content."
        ))

    if not any((project_root / "tests").rglob("*webmcp*round*trip*")):
        gaps.append(evolution_gap(
            "No WebMCP round-trip tests — tools tested via unit tests but never via navigator.modelContext "
            "in a real browser. Next: add Playwright test that calls blocks.read() via page.evaluate() "
            "and verifies response matches rendered DOM."
        ))

    gaps.append(evolution_gap(
        "No empty state UX validation — blocks with 0 items may show blank space instead of helpful "
        "empty states. Next: for each block type, verify the empty state renders a message, not nothing."
    ))

    gaps.append(evolution_gap(
        "No error recovery tests — if MCP server dies mid-request, do blocks show error+retry or "
        "white screen? Next: test block behavior when /api/blocks/data returns 500 or times out."
    ))

    gaps.append(evolution_gap(
        "No accessibility validation — blocks may lack ARIA labels, keyboard navigation, screen reader "
        "support. Next: add axe-core checks for block components."
    ))

    gaps.append(evolution_gap(
        "No performance budget — unknown page load time with N blocks, memory usage from polling intervals. "
        "Next: measure hub page TTI with Playwright, set budgets (e.g., <3s for 6 blocks)."
    ))

    return gaps


def check_d4_exhaustive(project_root: Path, base_url: str, timeout: int) -> list[dict]:
    """Jest + TypeScript + data shape validation + response times + view CRUD."""
    issues: list[dict] = []

    probe = check_http_route(base_url, timeout=3)
    dashboard_up = probe.get("ok", False)

    if dashboard_up:
        block_defs = _collect_block_defs(project_root)

        # Data shape checks
        issues.extend(_check_data_shapes(base_url, timeout, block_defs))

        # View CRUD
        issues.extend(_check_view_crud(base_url, timeout))

    # Jest + TypeScript (runs regardless of dashboard state)
    issues.extend(_check_jest(project_root))
    issues.extend(_check_typescript(project_root))

    return issues

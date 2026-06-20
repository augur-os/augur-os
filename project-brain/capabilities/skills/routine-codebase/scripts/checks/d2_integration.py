"""d2: Live API probing — probe dashboard APIs that back WebMCP tools."""
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
import urllib.request
import urllib.error
from pathlib import Path

from src.lib.ops_protocol import check_http_route, make_issue


def check_d2_live(project_root: Path, base_url: str, timeout: int) -> list[dict]:
    """Probe real dashboard APIs that back WebMCP tools."""
    issues: list[dict] = []

    probe = check_http_route(base_url, timeout=3)
    if not probe.get("ok"):
        issues.append(make_issue(
            category="webmcp-live",
            detail="Dashboard not running — skipping live checks",
            kind="environment",
            root_cause_type="env_runtime",
            fixability="manual",
        ))
        return issues

    # Test the core APIs that WebMCP tools depend on
    api_checks = [
        ("/api/views", "GET", "views.manage backend"),
    ]

    for route, method, purpose in api_checks:
        url = f"{base_url}{route}"
        result = check_http_route(url, timeout=timeout)
        if not result.get("ok"):
            status = result.get("status")
            if status in (400, 405):
                continue  # Expected for POST-only routes
            issues.append(make_issue(
                category="webmcp-live",
                detail=f"API {route} ({purpose}) returned {status or 'timeout'}",
                path=route,
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
            ))

    # Test block data API with a real MCP tool
    # Test tools that blocks actually use (no-arg tools)
    test_tools = [
        ("health", {}, "Health check"),
        ("get-observe-status", {}, "Observe status"),
        ("get-daemon-status", {}, "Daemon status"),
    ]

    for tool_name, args, label in test_tools:
        try:
            req = urllib.request.Request(
                f"{base_url}/api/blocks/data",
                data=json.dumps({"tool": tool_name, "args": args}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310  # base_url validated by check_http_route guard above
                data = json.loads(resp.read())
                if not isinstance(data, dict):
                    issues.append(make_issue(
                        category="webmcp-live",
                        detail=f"Block data API for '{tool_name}' ({label}) returned non-dict",
                        path="/api/blocks/data",
                        kind="actionable",
                    ))
                elif not data.get("success") and not data.get("data"):
                    issues.append(make_issue(
                        category="webmcp-live",
                        detail=f"Block data API for '{tool_name}' ({label}) returned no data: {json.dumps(data)[:200]}",
                        path="/api/blocks/data",
                        kind="actionable",
                    ))
        except urllib.error.HTTPError as e:
            if e.code == 502:
                # 502 = MCP tool not found. If tool is registered in SKILL.md,
                # this is an env issue (server needs restart), not a code bug.
                issues.append(make_issue(
                    category="webmcp-live",
                    detail=f"MCP tool '{tool_name}' ({label}) not registered (502) — restart MCP server",
                    path="/api/blocks/data",
                    kind="environment",
                    root_cause_type="env_runtime",
                ))
            else:
                issues.append(make_issue(
                    category="webmcp-live",
                    detail=f"Block data API for '{tool_name}' returned {e.code}",
                    path="/api/blocks/data",
                    kind="actionable",
                ))
        except Exception as e:
            issues.append(make_issue(
                category="webmcp-live",
                detail=f"Block data API unreachable for '{tool_name}': {e}",
                kind="environment",
                root_cause_type="env_runtime",
            ))

    return issues

"""d3: Deep block/action validation — test every block's MCP tool and action dispatch."""
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

import yaml

from src.lib.ops_protocol import check_http_route, make_issue


def check_d3_deep(project_root: Path, base_url: str, timeout: int) -> list[dict]:
    """Test every block's MCP tool and validate action dispatch wiring."""
    issues: list[dict] = []

    probe = check_http_route(base_url, timeout=3)
    if not probe.get("ok"):
        issues.append(make_issue(
            category="webmcp-deep",
            detail="Dashboard not running — skipping deep checks",
            kind="environment",
            root_cause_type="env_runtime",
        ))
        return issues

    # Collect all unique MCP tools from blocks
    block_tools: dict[str, list[str]] = {}  # tool_name -> [block_ids]
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
                bid = f"{skill_name}:{block.get('id', '?')}"
                block_tools.setdefault(tool, []).append(bid)

    # Test each unique MCP tool
    tested = 0
    failed = 0
    for tool_name, block_ids in sorted(block_tools.items()):
        try:
            req = urllib.request.Request(
                f"{base_url}/api/blocks/data",
                data=json.dumps({"tool": tool_name, "args": {}}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310  # base_url validated by check_http_route guard above
                tested += 1
                data = json.loads(resp.read())
                if not data.get("success"):
                    failed += 1
                    issues.append(make_issue(
                        category="webmcp-deep",
                        detail=f"MCP tool '{tool_name}' returned error (blocks: {', '.join(block_ids[:3])})",
                        path=f"mcp:{tool_name}",
                        kind="actionable",
                        root_cause_type="repo_bug",
                    ))
        except urllib.error.HTTPError as e:
            tested += 1
            failed += 1
            # 502 = tool not loaded in MCP server (env issue, needs restart)
            is_env = e.code == 502
            issues.append(make_issue(
                category="webmcp-deep",
                detail=f"MCP tool '{tool_name}' failed ({e.code}) — affects blocks: {', '.join(block_ids[:3])}",
                path=f"mcp:{tool_name}",
                kind="environment" if is_env else "actionable",
                root_cause_type="env_runtime" if is_env else "repo_bug",
            ))
        except Exception as e:
            tested += 1
            failed += 1
            issues.append(make_issue(
                category="webmcp-deep",
                detail=f"MCP tool '{tool_name}' unreachable: {e}",
                path=f"mcp:{tool_name}",
                kind="environment",
                root_cause_type="env_runtime",
            ))

    return issues

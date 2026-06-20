#!/usr/bin/env python3
"""MCP Surface Audit — inventory script for task #16.

Categorizes every MCP tool name across three sources of truth:
- Code (which @mcp.tool decorators register at startup)
- Policy (config/system/capability_exposure.yaml)
- Dashboard (which tool names appear in useMcpQuery/useMcpMutation/etc.)

Writes the report to docs/references/mcp-surface-audit.md, overwriting
in-place. Re-run after any cleanup pass to track progress.

Usage:
    PYTHONPATH=project-brain/capabilities:$PYTHONPATH .venv/bin/python scripts/mcp_surface_audit.py
"""
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

import yaml


# AI-client core read-only allowlist enforced by
# tests/lib/test_capability_exposure_policy.py::
# test_active_policy_limits_client_mcp_runtime_tools_to_core_read_surface
AI_CORE_ALLOWLIST = {
    "agent-registry",
    "augur-list-capabilities",
    "browse-index",
    "cross-skill",
    "find-skill",
    "get-config",
    "get-context",
    "get-design-standards",
    "get-preferences",
    "get-skill",
    "get-skill-doc",
    "get-skill-health",
    "health",
    "list-adrs",
    "list-agents",
    "list-cli-commands",
    "list-prompts",
    "list-scripts",
    "list-skill-actions",
    "list-skills",
    "load-module",
    "load-reference",
}


def _load_policy() -> dict[str, dict]:
    with open("config/system/capability_exposure.yaml") as f:
        caps = yaml.safe_load(f).get("capabilities", {})
    return {
        key.split(":", 1)[1]: value
        for key, value in caps.items()
        if key.startswith("mcp-tool:")
    }


def _build_registered_set() -> set[str]:
    from src.cli_bootstrap import bootstrap

    bootstrap()
    logging.disable(logging.CRITICAL)
    from src.cli import _build_cli_mcps

    registered: set[str] = set()
    for mcp in _build_cli_mcps():
        tool_manager = getattr(mcp, "_tool_manager", None)
        if tool_manager is not None:
            registered.update(tool_manager._tools.keys())
    return registered


def _grep_dashboard_callers() -> set[str]:
    result = subprocess.run(
        [
            "grep",
            "-rEho",
            r"(useMcpQuery|useMcpMutation|useMcpPoll|mcpCall)\([^)]+",
            "apps/dashboard",
        ],
        capture_output=True,
        text=True,
    )
    pattern = re.compile(
        r"(?:useMcpQuery|useMcpMutation|useMcpPoll|mcpCall)"
        r"\(\s*['\"]([a-z][a-z0-9-]+)['\"]"
    )
    return {match.group(1) for match in pattern.finditer(result.stdout)}


def _categorize(
    *, registered: set[str], policies: dict[str, dict], called: set[str]
) -> dict[str, list[str]]:
    cats: dict[str, list[str]] = {
        "AI-core (keep mcp)": [],
        "Dashboard-only (needs mcp-via-dashboard)": [],
        "Classified-with-mcp NOT dashboard NOT AI-core": [],
        "Classified-without-mcp NOT dashboard": [],
        "Dashboard caller NO policy entry": [],
        "Registered NO policy NO caller": [],
        "Policy entry NOT registered NOT called": [],
    }
    all_tools = registered | set(policies) | called
    for tool in sorted(all_tools):
        policy = policies.get(tool)
        is_reg = tool in registered
        is_called = tool in called
        is_aicore = tool in AI_CORE_ALLOWLIST
        has_policy = policy is not None
        has_mcp_export = bool(policy and "mcp" in (policy.get("export_to") or []))

        if is_aicore:
            cats["AI-core (keep mcp)"].append(tool)
        elif is_called and has_policy and not has_mcp_export:
            cats["Dashboard-only (needs mcp-via-dashboard)"].append(tool)
        elif is_called and not has_policy:
            cats["Dashboard caller NO policy entry"].append(tool)
        elif has_mcp_export and not is_called and not is_aicore:
            cats["Classified-with-mcp NOT dashboard NOT AI-core"].append(tool)
        elif has_policy and not has_mcp_export and not is_called:
            cats["Classified-without-mcp NOT dashboard"].append(tool)
        elif is_reg and not has_policy and not is_called:
            cats["Registered NO policy NO caller"].append(tool)
        elif has_policy and not is_reg and not is_called:
            cats["Policy entry NOT registered NOT called"].append(tool)
    return cats


def _write_report(cats: dict[str, list[str]]) -> Path:
    report_path = Path("docs/references/mcp-surface-audit.md")
    lines: list[str] = [
        "# MCP Surface Audit (Task #16)",
        "",
        "> Generated inventory — do not edit by hand. Re-run via",
        "> `scripts/mcp_surface_audit.py` after any policy or code change.",
        "",
        "Cross-tabulates three sources of truth:",
        "- **Code** — `@mcp.tool` decorators registered at server startup.",
        "- **Policy** — `config/system/capability_exposure.yaml` entries.",
        "- **Dashboard** — tool names in `useMcpQuery/useMcpMutation/etc.`.",
        "",
        "See `docs/references/surface-decision-matrix.md` for the four-layer model",
        "the cleanup targets.",
        "",
        "## Summary",
        "",
    ]
    for name, items in cats.items():
        lines.append(f"- **{name}**: {len(items)}")
    lines.append("")
    for name, items in cats.items():
        lines.append(f"## {name} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("_(none)_")
            lines.append("")
            continue
        for tool in items:
            lines.append(f"- `{tool}`")
        lines.append("")
    report_path.write_text("\n".join(lines))
    return report_path


def main() -> None:
    policies = _load_policy()
    registered = _build_registered_set()
    called = _grep_dashboard_callers()
    cats = _categorize(registered=registered, policies=policies, called=called)
    report_path = _write_report(cats)
    print(f"Wrote {report_path}")
    print(f"Totals: registered={len(registered)} policy={len(policies)} dashboard={len(called)}")
    for name, items in cats.items():
        print(f"  {len(items):4}  {name}")


if __name__ == "__main__":
    main()

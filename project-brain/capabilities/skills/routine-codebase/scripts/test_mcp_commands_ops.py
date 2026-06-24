"""auto-test-mcp-commands: Categorized MCP tool invocation testing."""
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
import asyncio
import os
import site
import sys
from pathlib import Path

import yaml

from src.lib.frontmatter_utils import load_skill_contract
from src.lib.ops_protocol import OpsContext, ScanResult, make_issue, report_only_fix

name = "auto-test-mcp-commands"


def _prefer_installed_mcp() -> None:
    """Ensure the third-party MCP package wins over local scripts/mcp modules."""
    search_roots = [path for path in site.getsitepackages() if path]
    user_site = site.getusersitepackages()
    if user_site:
        search_roots.append(user_site)

    for root in reversed(search_roots):
        if root in sys.path:
            sys.path.remove(root)
        sys.path.insert(0, root)

    current = sys.modules.get("mcp")
    current_path = Path(getattr(current, "__file__", "")) if current else None
    if current_path and "site-packages" not in str(current_path):
        for name in list(sys.modules):
            if name == "mcp" or name.startswith("mcp."):
                sys.modules.pop(name, None)

_DEFAULT_MUTATING_PREFIXES = [
    "create-", "delete-", "update-", "run-", "add-", "set-",
    "toggle-", "publish-", "send-", "apply-", "install-", "uninstall-",
]


def classify_tool(tool_name: str, mutating_prefixes: list[str]) -> str:
    """Classify a tool as 'read' or 'mutating' based on name prefix."""
    if tool_name.startswith(tuple(mutating_prefixes)):
        return "mutating"
    return "read"


def _discover_tools(project_root: Path) -> list[dict]:
    """Discover MCP tools from canonical SKILL.md metadata.

    Only canonical sources (repo skills/ + vault skills/). Client wrapper
    folders (.gemini/skills, .opencode/skills, etc.) are packaging output,
    not loop sources — see project-brain/capabilities/skills/daemon/commands/a-loops.md.
    """
    from src.config.paths import get_managed_skill_source_dirs

    tools: list[dict] = []
    for root in get_managed_skill_source_dirs(project_root):
        for skill_md in sorted(root.glob("*/SKILL.md")):
            contract = load_skill_contract(skill_md)
            if not contract:
                continue
            mcp_tools = contract.get("mcp", {}).get("tools", [])
            skill = contract.get("name", skill_md.parent.name)
            for tool in mcp_tools:
                tool_name = tool if isinstance(tool, str) else tool.get("name", "")
                if tool_name:
                    tools.append({"name": tool_name, "skill": skill})
    return tools


def _expects_direct_mcp_registration(project_root: Path, tool_name: str) -> bool:
    """Return whether policy says a declared tool should appear in direct MCP."""
    policy_path = project_root / "config" / "system" / "capability_exposure.yaml"
    if not policy_path.is_file():
        return True

    try:
        from src.lib.capabilities.exposure_policy import load_capability_policy

        policy = load_capability_policy(policy_path)
    except Exception:
        return True

    capabilities = policy.get("capabilities") or {}
    if not isinstance(capabilities, dict):
        return True

    entry = capabilities.get(f"mcp-tool:{tool_name}")
    if not isinstance(entry, dict):
        return True

    status = str(entry.get("classification_status") or "").strip()
    export_raw = entry.get("export_to") or []
    if isinstance(export_raw, str):
        export_to = {part.strip() for part in export_raw.split(",") if part.strip()}
    elif isinstance(export_raw, (list, tuple, set)):
        export_to = {str(part).strip() for part in export_raw if str(part).strip()}
    else:
        export_to = set()

    if status == "blocked":
        return False
    if status in {"approved", "deprecated"} and "mcp" not in export_to:
        return False
    return True


def _get_server_params(
    project_root: Path,
    module: str = "src.mcp.augur_framework",
    extra_args: list[str] | None = None,
    add_client_args: bool = True,
):
    """Build MCP StdioServerParameters for the Augur framework MCP server."""
    _prefer_installed_mcp()
    from mcp import StdioServerParameters

    root = str(project_root)
    venv_python = os.path.join(root, ".venv", "bin", "python")
    python_cmd = venv_python if os.path.isfile(venv_python) else sys.executable

    module_args = ["-m", module, *(extra_args or [])]
    if add_client_args:
        module_args.extend(["--client-id", "test-scanner", "--no-lock"])

    return StdioServerParameters(
        command=python_cmd,
        args=module_args,
        env={
            "AUGUR_ROOT": root,
            "PYTHONPATH": f"{root}:{os.path.join(root, 'src', 'mcp')}",
            "PYTHONUNBUFFERED": "1",
            "AUGUR_DASHBOARD_MCP_INCLUDE_CORE_TOOLS": "1",
        },
    )


def _get_bundle_server_params(project_root: Path, bundle_name: str):
    """Build MCP StdioServerParameters for one excluded bundle server."""
    return _get_server_params(
        project_root,
        module="src.mcp.augur_shared.bundle_server",
        extra_args=[bundle_name],
        add_client_args=False,
    )


def _invoke_tool(tool_name: str, timeout: int = 15) -> dict:
    """Invoke a read-safe MCP tool via the MCP protocol."""
    from src.config.paths import get_project_root

    async def _run():
        _prefer_installed_mcp()
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        params = _get_server_params(get_project_root())
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await asyncio.wait_for(
                    session.call_tool(tool_name, {}), timeout=timeout,
                )
                text = result.content[0].text if result.content else ""
                is_error = getattr(result, "isError", False)
                return {"ok": not is_error, "stdout": text[:500]}

    try:
        return asyncio.run(_run())
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _fetch_tool_list(timeout: int = 30) -> tuple[bool, str]:
    """Fetch the MCP tool list via the MCP protocol. Returns (success, tool_names_str)."""
    from src.config.paths import get_project_root

    async def _run():
        _prefer_installed_mcp()
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        params = _get_server_params(get_project_root())
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await asyncio.wait_for(session.list_tools(), timeout=timeout)
                tool_names = "\n".join(t.name for t in result.tools)
                return True, tool_names

    try:
        return asyncio.run(_run())
    except Exception as e:
        return False, str(e)


def _fetch_bundle_tool_list(bundle_name: str, timeout: int = 30) -> tuple[bool, str]:
    """Fetch the MCP tool list for a bundle-server-isolated skill."""
    from src.config.paths import get_project_root

    async def _run():
        _prefer_installed_mcp()
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        params = _get_bundle_server_params(get_project_root(), bundle_name)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await asyncio.wait_for(session.list_tools(), timeout=timeout)
                tool_names = "\n".join(t.name for t in result.tools)
                return True, tool_names

    try:
        return asyncio.run(_run())
    except Exception as e:
        return False, str(e)


def _load_monolith_exclusions() -> set[str]:
    """Return skills intentionally served by bundle servers instead of framework."""
    try:
        from src.cli_config.manifest import load_manifest

        return set(load_manifest().monolith_exclusions)
    except Exception:
        return set()


def scan(ctx: OpsContext) -> ScanResult:
    tools = _discover_tools(ctx.project_root)
    tools = [
        tool
        for tool in tools
        if _expects_direct_mcp_registration(ctx.project_root, tool["name"])
    ]

    if not tools:
        return ScanResult(
            issues=[],
            summary="No MCP tools found for direct registration",
            severity="info",
        )

    mutating_prefixes = ctx.config.get("mutating_prefixes", _DEFAULT_MUTATING_PREFIXES)
    timeout = ctx.config.get("tool_timeout", 15)
    issues: list[dict] = []
    tested = 0

    # Fetch tool list once — this is the source of truth for tool existence
    tool_list_ok, tool_list_output = _fetch_tool_list(timeout=30)
    server_tool_names: set[str] = set()
    if tool_list_ok:
        server_tool_names = set(tool_list_output.strip().splitlines())
        exclusions = _load_monolith_exclusions()
        excluded_declared_skills = sorted({tool["skill"] for tool in tools if tool["skill"] in exclusions})
        for skill_name in excluded_declared_skills:
            bundle_ok, bundle_output = _fetch_bundle_tool_list(skill_name, timeout=30)
            if bundle_ok:
                server_tool_names.update(bundle_output.strip().splitlines())

    invoke_registered_read_tools = ctx.difficulty >= 2

    for tool in tools:
        category = classify_tool(tool["name"], mutating_prefixes)
        tested += 1
        in_server = tool_list_ok and tool["name"] in server_tool_names

        if not tool_list_ok:
            # Server unreachable — cannot determine status
            issues.append(make_issue(
                category="mcp-tool-runtime",
                detail=f"{tool['name']} could not be checked: {tool_list_output}",
                kind="environment",
                root_cause_type="env_runtime",
                fixability="manual",
                tool=tool["name"],
                skill=tool["skill"],
                tool_category=category,
                error=tool_list_output,
            ))
        elif not in_server:
            # Declared in canonical skill metadata but not registered in server.
            issues.append(make_issue(
                category="mcp-tool-registration",
                detail=f"{tool['name']} is declared in {tool['skill']} but not registered in the MCP server",
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="manual",
                tool=tool["name"],
                skill=tool["skill"],
                tool_category="stale_config",
                error="Declared in SKILL.md but not registered in MCP server",
            ))
        elif category == "read" and invoke_registered_read_tools:
            # Tool exists in server; invoke to verify read tools
            result = _invoke_tool(tool["name"], timeout=timeout)
            if not result.get("ok"):
                # Tool is registered but invocation failed — likely needs
                # arguments. That is metadata/test coverage debt, not a broken
                # registration.
                issues.append(make_issue(
                    category="mcp-tool-invocation",
                    detail=f"{tool['name']} is registered but cannot be called with empty args",
                    kind="maintenance",
                    root_cause_type="manual_debt",
                    fixability="manual",
                    tool=tool["name"],
                    skill=tool["skill"],
                    tool_category="needs_args",
                    error=result.get("error") or result.get("stderr", "unknown"),
                ))
        # else: mutating tool exists in server schema — counted as healthy

    # Partition issues by category
    stale = [i for i in issues if i.get("tool_category") == "stale_config"]
    needs_args = [i for i in issues if i.get("tool_category") == "needs_args"]
    broken = [i for i in issues if i.get("tool_category") not in ("stale_config", "needs_args")]

    parts: list[str] = []
    if broken:
        parts.append(f"{len(broken)} broken")
    if stale:
        parts.append(f"{len(stale)} stale tool declarations")
    if needs_args:
        parts.append(f"{len(needs_args)} require arguments")

    healthy = tested - len(broken) - len(stale)
    if not parts:
        return ScanResult(issues=[], summary=f"All {tested} MCP tools OK ({healthy} registered)", severity="info")

    summary = f"{tested} tools scanned: {', '.join(parts)}, {healthy} healthy"
    severity = "error" if broken else "warning"

    return ScanResult(
        issues=issues,
        summary=summary,
        severity=severity,
    )


def fix(ctx: OpsContext, issues: list[dict]):
    return report_only_fix(ctx, "test-mcp-commands-latest.json", issues, noun="broken tool")

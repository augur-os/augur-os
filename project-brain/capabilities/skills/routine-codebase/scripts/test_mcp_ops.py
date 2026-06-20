"""auto-test-mcp: MCP server handshake and tool listing verification."""
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
import json
import os
import site
import sys
from pathlib import Path

from src.lib.ops_protocol import OpsContext, ScanResult, report_only_fix

name = "auto-test-mcp"
DIFFICULTY_SPEC = {
    0: "Surface check — verify augur MCP entrypoint prerequisites without opening a session",
    1: "Content check — open MCP session and call system health/list-tools",
    2: "Deep check — validate core tools, coverage, and client-config startup",
    3: "Exhaustive — same as d2 with stricter coverage thresholds",
    4: "Expert — same as d3",
}
EXPANSION_TARGETS = [
    {
        "category": "auto-test-mcp-commands",
        "difficulty": 3,
        "min_clean_streak": 2,
        "reason": "handshake stays clean, so widen into categorized MCP command invocation coverage",
    }
]
_HEALTH_TOOL = "get-system-health"
_REQUIRED_CORE_TOOLS = (_HEALTH_TOOL, "discover-augur", "list-mcp-tools")

# Known client config paths (platform -> config file -> MCP server key)
_CLIENT_CONFIGS = {
    "claude_desktop": {
        "config_path": Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
        "server_key": "augur",
    },
}


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


def _get_server_params(project_root: Path):
    """Build MCP StdioServerParameters for the Augur framework MCP server."""
    _prefer_installed_mcp()
    from mcp import StdioServerParameters

    root = str(project_root)
    venv_python = os.path.join(root, ".venv", "bin", "python")
    python_cmd = venv_python if os.path.isfile(venv_python) else sys.executable

    return StdioServerParameters(
        command=python_cmd,
        args=["-m", "src.mcp.augur_framework", "--client-id", "test-scanner", "--no-lock"],
        env={
            "AUGUR_ROOT": root,
            "PYTHONPATH": f"{root}:{os.path.join(root, 'src', 'mcp')}",
            "PYTHONUNBUFFERED": "1",
        },
    )


async def _check_mcp_health_async(project_root: Path, timeout: int = 30) -> dict:
    """Connect to augur MCP server, call the current health tool, return parsed result."""
    _prefer_installed_mcp()
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    params = _get_server_params(project_root)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Get tool count via list_tools
            tools_result = await asyncio.wait_for(session.list_tools(), timeout=timeout)
            tool_names = [tool.name for tool in tools_result.tools]
            tool_count = len(tool_names)

            # Call health tool for detailed status.
            health_result = await asyncio.wait_for(
                session.call_tool(_HEALTH_TOOL, {}), timeout=timeout,
            )
            text = health_result.content[0].text if health_result.content else "{}"
            health_data = json.loads(text)
            return {"ok": True, "tools": tool_count, "tool_names": tool_names, **health_data}


def _check_mcp_health(project_root: Path, timeout: int = 30) -> dict:
    """Call augur MCP health tool via MCP protocol and return parsed result."""
    try:
        return asyncio.run(_check_mcp_health_async(project_root, timeout=timeout))
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _surface_prereqs(project_root: Path) -> dict:
    """Validate MCP entrypoint prerequisites without starting the server."""
    root = Path(project_root)
    mcp_module = root / "src" / "mcp" / "augur_framework" / "__main__.py"
    venv_python = root / ".venv" / "bin" / "python"
    fallback_python = Path(sys.executable)
    issues: list[str] = []
    if not mcp_module.is_file():
        issues.append("augur_framework entrypoint missing")
    if not venv_python.is_file() and not fallback_python.is_file():
        issues.append("python launcher missing")

    if issues:
        return {"ok": False, "error": "; ".join(issues)}
    return {"ok": True, "summary": "MCP entrypoint prerequisites present"}


def _load_client_configs() -> list[dict]:
    """Load MCP server configs from known AI client config files.

    Returns a list of dicts with keys: client, command, args, env, cwd.
    Skips clients whose config file is missing (not installed).
    """
    configs: list[dict] = []
    for client_name, meta in _CLIENT_CONFIGS.items():
        config_path = meta["config_path"]
        if not config_path.is_file():
            continue
        try:
            data = json.loads(config_path.read_text())
            server = data.get("mcpServers", {}).get(meta["server_key"])
            if not server:
                continue
            configs.append({
                "client": client_name,
                "config_path": str(config_path),
                "command": server.get("command", ""),
                "args": server.get("args", []),
                "env": server.get("env", {}),
                "cwd": server.get("cwd", ""),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return configs


async def _check_client_config_async(cfg: dict, timeout: int = 15) -> dict:
    """Attempt MCP handshake using exact args from a client config file.

    This catches startup-blocking issues (lock conflicts, bad env, import
    errors) that only manifest under the real client's launch context.
    """
    _prefer_installed_mcp()
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=cfg["command"],
        args=cfg["args"],
        env=cfg.get("env") or None,
    )
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=timeout)
                tools = await asyncio.wait_for(session.list_tools(), timeout=timeout)
                return {"ok": True, "client": cfg["client"], "tools": len(tools.tools)}
    except Exception as e:
        return {"ok": False, "client": cfg["client"], "error": str(e)}


def _scan_client_configs(timeout: int = 15) -> list[dict]:
    """Validate MCP startup under each installed client's real config.

    Returns a list of issue dicts for clients whose startup failed.
    """
    configs = _load_client_configs()
    if not configs:
        return []

    issues: list[dict] = []
    for cfg in configs:
        try:
            result = asyncio.run(_check_client_config_async(cfg, timeout=timeout))
        except Exception as e:
            result = {"ok": False, "client": cfg["client"], "error": str(e)}

        if not result.get("ok"):
            issues.append({
                "error": f"MCP startup failed under {cfg['client']} config: {result.get('error', 'unknown')}",
                "level": "client-config",
                "category": "client-config-startup-fail",
                "client": cfg["client"],
                "config_path": cfg.get("config_path", ""),
            })
    return issues


def _scan_core_tool_coverage(health: dict, min_tools: int) -> list[dict]:
    issues: list[dict] = []
    tool_names = {str(name) for name in health.get("tool_names", []) if isinstance(name, str)}
    missing = sorted(tool for tool in _REQUIRED_CORE_TOOLS if tool not in tool_names)
    if missing:
        issues.append({
            "error": f"Missing core MCP tool(s): {', '.join(missing)}",
            "level": "tool-coverage",
            "missing_tools": missing,
            "category": "missing-core-tools",
        })
    tool_count = int(health.get("tools", 0) or 0)
    if tool_count < min_tools:
        issues.append({
            "error": f"Registered tool count {tool_count} below minimum {min_tools}",
            "level": "tool-coverage",
            "category": "tool-count-low",
            "tool_count": tool_count,
            "minimum": min_tools,
        })
    return issues


def scan(ctx: OpsContext) -> ScanResult:
    # MCP health is critical — always run at d1+ regardless of difficulty setting.
    effective_difficulty = max(ctx.difficulty, int(ctx.config.get("min_difficulty", 0)))

    if effective_difficulty < 1:
        prereqs = _surface_prereqs(ctx.project_root)
        if prereqs.get("ok"):
            return ScanResult(
                issues=[],
                summary=prereqs.get("summary", "MCP prerequisites present"),
                severity="info",
                health="verified",
            )
        return ScanResult(
            issues=[],
            summary=f"MCP prerequisites missing: {prereqs.get('error', 'unknown')[:100]}",
            severity="warning",
            health="broken",
        )

    timeout = ctx.config.get("handshake_timeout", 30)
    health = _check_mcp_health(ctx.project_root, timeout=timeout)

    if health.get("ok"):
        tool_count = health.get("tools", 0)
        if effective_difficulty >= 2:
            all_issues: list[dict] = []
            all_issues.extend(_scan_core_tool_coverage(
                health,
                int(ctx.config.get("min_tools", 40)),
            ))
            # Client-config validation: test startup under real client configs
            client_timeout = int(ctx.config.get("client_config_timeout", 15))
            all_issues.extend(_scan_client_configs(timeout=client_timeout))
            if all_issues:
                return ScanResult(
                    issues=all_issues,
                    summary=f"MCP handshake passed but validation failed ({len(all_issues)} issue(s))",
                    severity="error",
                )
        return ScanResult(
            issues=[],
            summary=f"MCP healthy, {tool_count} tools registered",
            severity="info",
        )

    return ScanResult(
        issues=[{"error": health.get("error", "unknown"), "level": "handshake"}],
        summary=f"MCP health check failed: {health.get('error', 'unknown')[:100]}",
        severity="error",
    )


def fix(ctx: OpsContext, issues: list[dict]):
    return report_only_fix(ctx, "test-mcp-latest.json", issues, noun="MCP issue")

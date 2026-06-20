#!/usr/bin/env python3
"""
verify-page-tools.py — MCP tool verification for dashboard pages.

Scans all TSX pages in apps/dashboard/features/pages/ for MCP tool references
(useMcpQuery, useMcpMutation, useMcpPoll), then probes each tool via
the MCP server to check existence and data availability.

Outputs:
  - docs/generated/tool-verification.json
  - Console summary of OK / missing / error tools per page
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import site
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cli_config.manifest import ServerEntry, load_manifest

# ---------------------------------------------------------------------------
# 1. TSX scanning — extract tool names from hook calls
# ---------------------------------------------------------------------------

# useMcpQuery<T>(cacheKey, 'tool-name', preset, opts?)
#   cacheKey is a string or array — skip it, tool name is the SECOND string arg
_RE_USE_MCP_QUERY = re.compile(
    r"""useMcpQuery\b[^(]*\(\s*"""               # useMcpQuery<T>(
    r"""(?:\[[^\]]*\]|'[^']*'|"[^"]*")\s*,\s*""" # first arg (cacheKey): array or string
    r"""['"]([^'"]+)['"]""",                      # capture: tool name (second string arg)
    re.DOTALL,
)

# useMcpMutation<T1, T2>('tool-name')
_RE_USE_MCP_MUTATION = re.compile(
    r"""useMcpMutation\b[^(]*\(\s*['"]([^'"]+)['"]""",
    re.DOTALL,
)

# useMcpPoll<T>(cacheKey, 'tool-name', interval, opts?)
_RE_USE_MCP_POLL = re.compile(
    r"""useMcpPoll\b[^(]*\(\s*"""
    r"""(?:\[[^\]]*\]|'[^']*'|"[^"]*")\s*,\s*"""
    r"""['"]([^'"]+)['"]""",
    re.DOTALL,
)

# Tools known to need a skill_id argument for a valid call
_SKILL_ID_TOOLS = {
    "list-skill-actions",
    "get-skill-doc",
    "list-skill-vault-notes",
    "get-skill",
    "get-skill-health",
    "search-skill-knowledge",
}


def scan_tsx_files(pages_dir: Path) -> dict[str, list[dict]]:
    """
    Walk pages_dir for .tsx files and extract MCP tool references.

    Returns:
        { "relative/path.tsx": [ { "tool": "tool-name", "hook": "useMcpQuery" }, ... ] }
    """
    results: dict[str, list[dict]] = {}
    for tsx_path in sorted(pages_dir.rglob("*.tsx")):
        content = tsx_path.read_text(errors="replace")
        tools: list[dict] = []

        for m in _RE_USE_MCP_QUERY.finditer(content):
            tools.append({"tool": m.group(1), "hook": "useMcpQuery"})
        for m in _RE_USE_MCP_MUTATION.finditer(content):
            tools.append({"tool": m.group(1), "hook": "useMcpMutation"})
        for m in _RE_USE_MCP_POLL.finditer(content):
            tools.append({"tool": m.group(1), "hook": "useMcpPoll"})

        if tools:
            rel = str(tsx_path.relative_to(pages_dir))
            results[rel] = tools
    return results


# ---------------------------------------------------------------------------
# 2. MCP tool probing — connect to server, call each tool
# ---------------------------------------------------------------------------

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


def _python_command_for_root(project_root: Path) -> str:
    """Resolve the Python interpreter used to launch local MCP servers."""
    root = str(project_root)
    venv_python = os.path.join(root, ".venv", "bin", "python")
    return venv_python if os.path.isfile(venv_python) else sys.executable


def _expand_manifest_value(value: str, project_root: Path) -> str:
    return value.replace("${AUGUR_ROOT}", str(project_root))


def _build_server_launch(project_root: Path, entry: ServerEntry) -> dict[str, Any]:
    """Build a serializable launch spec for one canonical Augur MCP server."""
    env = {
        "AUGUR_ROOT": str(project_root),
        "PYTHONPATH": f"{project_root}:{project_root / 'src' / 'mcp'}",
        "PYTHONUNBUFFERED": "1",
    }
    env.update({
        key: _expand_manifest_value(value, project_root)
        for key, value in entry.env.items()
    })
    command = _python_command_for_root(project_root) if entry.command == "python" else entry.command
    return {
        "command": command,
        "args": [_expand_manifest_value(arg, project_root) for arg in entry.args],
        "env": env,
    }


def _load_probe_server_entries(project_root: Path) -> list[ServerEntry]:
    """Load all canonical Augur MCP servers that can own dashboard tools."""
    manifest = load_manifest(project_root / "config" / "system" / "mcp_servers.yaml")
    return manifest.all_augur_servers()


def _get_server_params(project_root: Path, entry: ServerEntry):
    """Build MCP StdioServerParameters for a canonical Augur server."""
    _prefer_installed_mcp()
    from mcp import StdioServerParameters

    launch = _build_server_launch(project_root, entry)

    return StdioServerParameters(
        command=launch["command"],
        args=launch["args"],
        env=launch["env"],
    )


def _build_tool_args(tool_name: str) -> dict:
    """Return sample args for tools that require parameters."""
    if tool_name in _SKILL_ID_TOOLS:
        return {"skill_id": "growth"}
    return {}


async def _probe_tools_on_server(
    project_root: Path,
    entry: ServerEntry,
    tool_names: set[str],
    timeout: int,
) -> tuple[set[str], dict[str, dict]]:
    """List and call requested tools that are registered by one MCP server."""
    _prefer_installed_mcp()
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    params = _get_server_params(project_root, entry)
    results: dict[str, dict] = {}

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=30)

            tools_result = await asyncio.wait_for(session.list_tools(), timeout=timeout)
            registered_names = {t.name for t in tools_result.tools}

            for tool_name in sorted(tool_names & registered_names):
                entry_result: dict = {
                    "registered": True,
                    "callable": False,
                    "has_data": False,
                    "server": entry.id,
                    "error": None,
                }

                try:
                    args = _build_tool_args(tool_name)
                    call_result = await asyncio.wait_for(
                        session.call_tool(tool_name, args),
                        timeout=timeout,
                    )
                    entry_result["callable"] = True

                    text = ""
                    if call_result.content:
                        first_content = call_result.content[0]
                        text = first_content.text if hasattr(first_content, "text") else str(first_content)

                    if text:
                        try:
                            data = json.loads(text)
                            if isinstance(data, dict):
                                entry_result["has_data"] = bool(data)
                            elif isinstance(data, list):
                                entry_result["has_data"] = len(data) > 0
                            else:
                                entry_result["has_data"] = bool(data)
                        except json.JSONDecodeError:
                            entry_result["has_data"] = len(text.strip()) > 0

                except asyncio.TimeoutError:
                    entry_result["error"] = f"call timed out ({timeout}s)"
                except Exception as e:
                    err_msg = str(e)
                    if len(err_msg) > 200:
                        err_msg = err_msg[:200] + "..."
                    entry_result["error"] = err_msg

                results[tool_name] = entry_result

    return registered_names, results


async def probe_tools(
    project_root: Path,
    tool_names: set[str],
    timeout: int = 15,
) -> dict[str, dict]:
    """
    Connect to all canonical Augur MCP servers, then call each requested tool
    on the server that registers it.

    Returns:
        { "tool-name": { "registered": bool, "callable": bool, "has_data": bool, "error": str|None } }
    """
    results: dict[str, dict] = {}
    registered_names: set[str] = set()
    server_errors: dict[str, str] = {}

    for server_entry in _load_probe_server_entries(project_root):
        try:
            server_registered, server_results = await _probe_tools_on_server(
                project_root,
                server_entry,
                tool_names,
                timeout,
            )
        except Exception as e:
            err_msg = str(e)
            if len(err_msg) > 200:
                err_msg = err_msg[:200] + "..."
            server_errors[server_entry.id] = err_msg
            continue

        registered_names.update(server_registered)
        for tool_name, tool_result in server_results.items():
            current = results.get(tool_name)
            if current is None or (not current.get("callable") and tool_result.get("callable")):
                results[tool_name] = tool_result

    checked_servers = sorted(entry.id for entry in _load_probe_server_entries(project_root))
    for tool_name in sorted(tool_names):
        if tool_name in results:
            continue
        if tool_name not in registered_names:
            results[tool_name] = {
                "registered": False,
                "callable": False,
                "has_data": False,
                "servers": checked_servers,
                "error": "tool not registered in any Augur MCP server",
            }
            continue
        results[tool_name] = {
            "registered": True,
            "callable": False,
            "has_data": False,
            "servers": checked_servers,
            "error": f"registered but not callable; server errors: {server_errors}",
        }

    return results


# ---------------------------------------------------------------------------
# 3. Main — orchestrate scan + probe + output
# ---------------------------------------------------------------------------

def main() -> None:
    pages_dir = PROJECT_ROOT / "apps" / "dashboard" / "features" / "pages"
    output_path = PROJECT_ROOT / "docs" / "generated" / "tool-verification.json"

    if not pages_dir.is_dir():
        print(f"ERROR: pages directory not found: {pages_dir}")
        sys.exit(1)

    # --- Step 1: Scan TSX files ---
    print(f"Scanning {pages_dir} for MCP tool references...")
    page_tools = scan_tsx_files(pages_dir)

    # Collect unique tool names
    all_tools: set[str] = set()
    for tools_list in page_tools.values():
        for t in tools_list:
            all_tools.add(t["tool"])

    print(f"  Found {len(all_tools)} unique tools across {len(page_tools)} files\n")

    # --- Step 2: Probe tools via MCP server ---
    print("Probing tools via MCP server...")
    start = time.monotonic()
    try:
        tool_results = asyncio.run(probe_tools(PROJECT_ROOT, all_tools))
    except Exception as e:
        print(f"  ERROR: MCP probe failed: {e}")
        # Still produce output with scan results, marking all tools as unknown
        tool_results = {
            name: {"registered": None, "callable": False, "has_data": False, "error": f"MCP probe failed: {e}"}
            for name in all_tools
        }
    elapsed = time.monotonic() - start
    print(f"  Probed {len(tool_results)} tools in {elapsed:.1f}s\n")

    # --- Step 3: Build per-page status ---
    pages_status: list[dict] = []
    for page_path, tools_list in sorted(page_tools.items()):
        page_tool_names = [t["tool"] for t in tools_list]
        all_ok = all(
            tool_results.get(name, {}).get("callable", False)
            for name in page_tool_names
        )
        pages_status.append({
            "page": page_path,
            "tools": [
                {
                    "tool": t["tool"],
                    "hook": t["hook"],
                    **tool_results.get(t["tool"], {"registered": None, "callable": False, "has_data": False, "error": "not probed"}),
                }
                for t in tools_list
            ],
            "ready": all_ok,
        })

    # --- Step 4: Summary counts ---
    ok_tools = [n for n, r in tool_results.items() if r.get("callable")]
    missing_tools = [n for n, r in tool_results.items() if not r.get("registered")]
    error_tools = [n for n, r in tool_results.items() if r.get("registered") and not r.get("callable")]
    ready_pages = [p for p in pages_status if p["ready"]]

    summary = {
        "total_tools": len(all_tools),
        "ok": len(ok_tools),
        "missing": len(missing_tools),
        "error": len(error_tools),
        "total_pages": len(pages_status),
        "ready_pages": len(ready_pages),
    }

    # --- Step 5: Write output ---
    output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "summary": summary,
        "tools": {name: tool_results[name] for name in sorted(tool_results)},
        "pages": pages_status,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n")
    print(f"Output written to {output_path}\n")

    # --- Step 6: Console summary ---
    print("=" * 60)
    print("TOOL VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"  Tools:  {summary['ok']} OK / {summary['missing']} missing / {summary['error']} error  (of {summary['total_tools']})")
    print(f"  Pages:  {summary['ready_pages']} ready / {summary['total_pages']} total")
    print()

    if missing_tools:
        print("MISSING tools (not registered in MCP server):")
        for name in sorted(missing_tools):
            print(f"  - {name}")
        print()

    if error_tools:
        print("ERROR tools (registered but call failed):")
        for name in sorted(error_tools):
            err = tool_results[name].get("error", "unknown")
            print(f"  - {name}: {err}")
        print()

    if ok_tools:
        print("OK tools:")
        for name in sorted(ok_tools):
            data_flag = " [has data]" if tool_results[name].get("has_data") else " [empty]"
            print(f"  + {name}{data_flag}")
        print()

    not_ready = [p for p in pages_status if not p["ready"]]
    if not_ready:
        print(f"NOT READY pages ({len(not_ready)}):")
        for p in not_ready:
            broken = [t["tool"] for t in p["tools"] if not t.get("callable")]
            print(f"  {p['page']}: {', '.join(broken)}")
        print()

    # Exit with non-zero if any tools are missing
    if missing_tools or error_tools:
        sys.exit(1)


if __name__ == "__main__":
    main()

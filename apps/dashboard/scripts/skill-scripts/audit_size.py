"""Plugin size limit audit checks.

Functions: count_lines, count_mcp_tools, check_size_limits.
Split from audit_checks.py for module size management.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from audit import AuditResult, _collect_code_files, logger


def count_lines(file_path: Path) -> int:
    """Count non-empty, non-comment lines in a file."""
    try:
        content = file_path.read_text()
        lines = content.split("\n")
        return sum(1 for line in lines if line.strip() and not line.strip().startswith("#"))
    except Exception:
        return 0


def count_mcp_tools(plugin_path: Path) -> int:
    """Count MCP tools defined in a plugin."""
    mcp_init = plugin_path / "mcp" / "__init__.py"
    mcp_tools = plugin_path / "mcp" / "tools.py"

    tool_count = 0
    for file_path in [mcp_init, mcp_tools]:
        if file_path.exists():
            try:
                content = file_path.read_text()
                tool_count += content.count("@mcp.tool(")
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                logger.debug("Failed to count MCP decorators in %s: %s", file_path, exc)

    return tool_count


def check_size_limits(plugin_path: Path, plugin_name: str, spec: dict) -> List[AuditResult]:
    """Check plugin size limits and recommend splitting if too large."""
    results = []
    size_limits = spec.get("size_limits", {})

    if not size_limits:
        return results

    # --- MCP Tools Count ---
    mcp_limits = size_limits.get("mcp_tools", {})
    mcp_warn = mcp_limits.get("warn", 8)
    mcp_split = mcp_limits.get("recommend_split", 12)
    mcp_msg = mcp_limits.get("message", "Consider splitting plugin")

    tool_count = count_mcp_tools(plugin_path)

    if tool_count > 0:
        if tool_count >= mcp_split:
            results.append(
                AuditResult(
                    rule="size_mcp_tools",
                    passed=True,
                    message=f"Plugin has {tool_count} MCP tools (recommend max {mcp_split}). {mcp_msg}",
                    file_path=str(plugin_path / "mcp"),
                )
            )
        elif tool_count >= mcp_warn:
            results.append(
                AuditResult(
                    rule="size_mcp_tools",
                    passed=True,
                    message=f"Plugin has {tool_count} MCP tools (approaching limit of {mcp_split}). {mcp_msg}",
                    file_path=str(plugin_path / "mcp"),
                )
            )
        else:
            results.append(
                AuditResult(
                    rule="size_mcp_tools",
                    passed=True,
                    message=f"MCP tools count OK: {tool_count}",
                )
            )

    # --- File Line Counts ---
    file_limits = size_limits.get("file_lines", {})
    file_warn = file_limits.get("warn", 500)
    file_split = file_limits.get("recommend_split", 800)
    file_msg = file_limits.get("message", "Consider extracting to separate modules")

    large_files = []
    python_files = _collect_code_files(plugin_path, "*.py")
    ts_files = _collect_code_files(plugin_path, "*.ts")
    tsx_files = _collect_code_files(plugin_path, "*.tsx")

    for file_path in python_files + ts_files + tsx_files:
        line_count = count_lines(file_path)
        if line_count >= file_split:
            large_files.append((file_path, line_count, "critical"))
        elif line_count >= file_warn:
            large_files.append((file_path, line_count, "warning"))

    if large_files:
        for file_path, line_count, severity in large_files:
            relative_path = file_path.relative_to(plugin_path)
            results.append(
                AuditResult(
                    rule="size_file_lines",
                    passed=True,
                    message=f"File {relative_path} has {line_count} lines. {file_msg}",
                    file_path=str(file_path),
                )
            )
    else:
        results.append(
            AuditResult(
                rule="size_file_lines",
                passed=True,
                message="All files within size limits",
            )
        )

    # --- API Routes Count ---
    api_limits = size_limits.get("api_routes", {})
    api_warn = api_limits.get("warn", 6)
    api_split = api_limits.get("recommend_split", 10)
    api_msg = api_limits.get("message", "Consider creating a separate API plugin")

    api_dir = plugin_path / "api"
    if api_dir.exists():
        route_files = list(api_dir.rglob("route.ts"))
        route_count = len(route_files)

        if route_count >= api_split:
            results.append(
                AuditResult(
                    rule="size_api_routes",
                    passed=True,
                    message=f"Plugin has {route_count} API routes (recommend max {api_split}). {api_msg}",
                    file_path=str(api_dir),
                )
            )
        elif route_count >= api_warn:
            results.append(
                AuditResult(
                    rule="size_api_routes",
                    passed=True,
                    message=f"Plugin has {route_count} API routes (approaching limit of {api_split}). {api_msg}",
                    file_path=str(api_dir),
                )
            )
        else:
            results.append(
                AuditResult(
                    rule="size_api_routes",
                    passed=True,
                    message=f"API routes count OK: {route_count}",
                )
            )

    # --- Total Python Lines ---
    python_limits = size_limits.get("total_python_lines", {})
    py_warn = python_limits.get("warn", 2000)
    py_split = python_limits.get("recommend_split", 3500)
    py_msg = python_limits.get("message", "Plugin is getting large")

    total_python_lines = sum(count_lines(f) for f in python_files)

    if total_python_lines >= py_split:
        results.append(
            AuditResult(
                rule="size_total_python",
                passed=True,
                message=f"Total Python: {total_python_lines} lines (recommend max {py_split}). {py_msg}",
                file_path=str(plugin_path),
            )
        )
    elif total_python_lines >= py_warn:
        results.append(
            AuditResult(
                rule="size_total_python",
                passed=True,
                message=f"Total Python: {total_python_lines} lines (approaching limit of {py_split}). {py_msg}",
                file_path=str(plugin_path),
            )
        )
    else:
        results.append(
            AuditResult(
                rule="size_total_python",
                passed=True,
                message=f"Total Python lines OK: {total_python_lines}",
            )
        )

    # --- Total TypeScript Lines ---
    ts_limits = size_limits.get("total_typescript_lines", {})
    ts_warn = ts_limits.get("warn", 3000)
    ts_split = ts_limits.get("recommend_split", 5000)
    ts_msg = ts_limits.get("message", "Dashboard is getting complex")

    total_ts_lines = sum(count_lines(f) for f in ts_files + tsx_files)

    if total_ts_lines >= ts_split:
        results.append(
            AuditResult(
                rule="size_total_typescript",
                passed=True,
                message=f"Total TypeScript: {total_ts_lines} lines (recommend max {ts_split}). {ts_msg}",
                file_path=str(plugin_path),
            )
        )
    elif total_ts_lines >= ts_warn:
        results.append(
            AuditResult(
                rule="size_total_typescript",
                passed=True,
                message=f"Total TypeScript: {total_ts_lines} lines (approaching limit of {ts_split}). {ts_msg}",
                file_path=str(plugin_path),
            )
        )
    else:
        results.append(
            AuditResult(
                rule="size_total_typescript",
                passed=True,
                message=f"Total TypeScript lines OK: {total_ts_lines}",
            )
        )

    # --- Chains Count ---
    chain_limits = size_limits.get("chains", {})
    chain_warn = chain_limits.get("warn", 5)
    chain_split = chain_limits.get("recommend_split", 8)
    chain_msg = chain_limits.get("message", "Consider grouping related chains")

    chains_dir = plugin_path / "chains"
    if chains_dir.exists():
        chain_files = list(chains_dir.glob("*.yaml"))
        chain_count = len(chain_files)

        if chain_count >= chain_split:
            results.append(
                AuditResult(
                    rule="size_chains",
                    passed=True,
                    message=f"Plugin has {chain_count} chains (recommend max {chain_split}). {chain_msg}",
                    file_path=str(chains_dir),
                )
            )
        elif chain_count >= chain_warn:
            results.append(
                AuditResult(
                    rule="size_chains",
                    passed=True,
                    message=f"Plugin has {chain_count} chains (approaching limit of {chain_split}). {chain_msg}",
                    file_path=str(chains_dir),
                )
            )
        else:
            results.append(
                AuditResult(
                    rule="size_chains",
                    passed=True,
                    message=f"Chains count OK: {chain_count}",
                )
            )

    return results

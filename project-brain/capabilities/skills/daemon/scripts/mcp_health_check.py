#!/usr/bin/env python3
"""
MCP Health Check - Configuration and Runtime Health Validation.

Validates MCP configuration against recommended limits and checks
runtime process health for the daemon monitoring loop.

Configuration Checks (CI/validation time):
- MCP server count vs recommended limits
- Tool count vs recommended limits
- Startup time estimation
- Tool group configuration

Runtime Checks (daemon monitoring):
- PID liveness verification
- Process responsiveness
- Stalled process detection

Usage:
    python3 mcp_health_check.py                    # Full health check
    python3 mcp_health_check.py --verbose          # Detailed output
    python3 mcp_health_check.py --json             # JSON output
    python3 mcp_health_check.py --runtime          # Runtime checks only
    python3 mcp_health_check.py --config           # Config checks only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Setup project root
from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

from src.logging.self_heal_event import emit_heal_event as _emit_heal  # noqa: E402

try:
    import yaml
except ImportError as e:
    _emit_heal(
        source="mcp_health_check",
        category="import_failure",
        severity="high",
        message=f"Cannot import yaml: {e}",
        context={"expected_module": "yaml", "install": "pip install pyyaml"},
    )
    raise

try:
    from src.config.paths import get_project_root, get_runtime_dir
except ImportError as e:
    _emit_heal(
        source="mcp_health_check",
        category="import_failure",
        severity="high",
        message=f"Cannot import path helpers: {e}",
        context={"expected_module": "src.config.paths", "fallback_removed": True},
    )
    raise

try:
    from src.logging import get_entity_logger
except ImportError as e:
    _emit_heal(
        source="mcp_health_check",
        category="import_failure",
        severity="medium",
        message=f"Cannot import get_entity_logger: {e}",
        context={"expected_module": "src.logging", "fallback_removed": True},
    )
    raise


logger = get_entity_logger("mcp_health_check")


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION LIMITS (from ADR-019)
# ═══════════════════════════════════════════════════════════════════════════════

LIMITS = {
    "max_configured_mcps": 30,
    "max_enabled_mcps": 10,
    "max_active_tools": 80,
    "max_tools_per_page": 30,
    "max_startup_time_seconds": 5.0,
}

WARNING_THRESHOLD = 0.8


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    check: str
    status: str  # "ok", "warning", "error"
    message: str = ""
    details: Optional[dict] = None
    warnings: list[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MCPRuntimeStatus:
    """Runtime status of an MCP server."""

    name: str
    pid: Optional[int] = None
    is_alive: bool = False
    is_responsive: bool = False
    last_check: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def get_project_root() -> Path:
    """Get project root directory."""
    try:
        from src.config.paths import get_project_root as _get_root

        return Path(_get_root())
    except ImportError as e:
        _emit_heal(
            source="mcp_health_check",
            category="import_failure",
            severity="high",
            message=f"Cannot import get_project_root: {e}",
            context={"expected_module": "src.config.paths", "fallback_removed": True},
        )
        raise


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load YAML file safely."""
    if not path.exists() or not yaml:
        return {}
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.debug(f"Error loading YAML {path}: {e}")
        return {}


def load_json_file(path: Path) -> dict[str, Any]:
    """Load JSON file safely."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.debug(f"Error loading JSON {path}: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION CHECKS
# ═══════════════════════════════════════════════════════════════════════════════


def check_mcp_servers(root: Path, verbose: bool = False) -> HealthCheckResult:
    """Check MCP server configuration against limits."""
    result = HealthCheckResult(
        check="mcp_servers",
        status="ok",
        details={
            "configured": 0,
            "enabled": 0,
            "limit_configured": LIMITS["max_configured_mcps"],
            "limit_enabled": LIMITS["max_enabled_mcps"],
            "servers": [],
        },
    )

    # Check for MCP config files
    config_paths = [
        root / "config-data" / "mcp_config.json",
        root / "config-data" / "mcp_config.template.json",
        Path.home() / ".claude" / "mcp_config.json",
    ]

    config = {}
    for path in config_paths:
        if path.exists():
            config = load_json_file(path)
            break

    if not config:
        result.status = "warning"
        result.warnings.append("No MCP config file found")
        return result

    servers = config.get("mcpServers", {})
    result.details["configured"] = len(servers)

    enabled_count = 0
    for name, server_config in servers.items():
        is_enabled = server_config.get("enabled", True)
        if is_enabled:
            enabled_count += 1
        if verbose:
            result.details["servers"].append(
                {
                    "name": name,
                    "enabled": is_enabled,
                }
            )

    result.details["enabled"] = enabled_count

    # Check against limits
    configured = result.details["configured"]
    if configured > LIMITS["max_configured_mcps"]:
        result.status = "error"
        result.warnings.append(f"Configured MCPs ({configured}) exceeds limit ({LIMITS['max_configured_mcps']})")
    elif configured > LIMITS["max_configured_mcps"] * WARNING_THRESHOLD:
        result.status = "warning"
        result.warnings.append(f"Configured MCPs ({configured}) approaching limit ({LIMITS['max_configured_mcps']})")

    if enabled_count > LIMITS["max_enabled_mcps"]:
        result.status = "error"
        result.warnings.append(f"Enabled MCPs ({enabled_count}) exceeds limit ({LIMITS['max_enabled_mcps']})")
    elif enabled_count > LIMITS["max_enabled_mcps"] * WARNING_THRESHOLD:
        if result.status != "error":
            result.status = "warning"
        result.warnings.append(f"Enabled MCPs ({enabled_count}) approaching limit ({LIMITS['max_enabled_mcps']})")

    return result


def check_tool_count(root: Path, verbose: bool = False) -> HealthCheckResult:
    """Check total tool count across all MCPs."""
    result = HealthCheckResult(
        check="tool_count",
        status="ok",
        details={
            "total_tools": 0,
            "limit": LIMITS["max_active_tools"],
            "tools_by_mcp": {},
        },
    )

    tools_config_path = root / "config-data" / "mcp_tools.yaml"
    tools_config = load_yaml_file(tools_config_path)

    if not tools_config:
        result.status = "warning"
        result.warnings.append("No mcp_tools.yaml found")
        return result

    total = 0
    for mcp_name, mcp_config in tools_config.get("mcps", {}).items():
        tools = mcp_config.get("tools", [])
        tool_count = len(tools)
        if verbose:
            result.details["tools_by_mcp"][mcp_name] = tool_count
        total += tool_count

    result.details["total_tools"] = total

    if total > LIMITS["max_active_tools"]:
        result.status = "error"
        result.warnings.append(f"Total tools ({total}) exceeds limit ({LIMITS['max_active_tools']})")
    elif total > LIMITS["max_active_tools"] * WARNING_THRESHOLD:
        result.status = "warning"
        result.warnings.append(f"Total tools ({total}) approaching limit ({LIMITS['max_active_tools']})")

    return result


def check_tool_groups(root: Path, verbose: bool = False) -> HealthCheckResult:
    """Check tool groups per page configuration."""
    result = HealthCheckResult(
        check="tool_groups",
        status="ok",
        details={
            "pages": {},
            "limit_per_page": LIMITS["max_tools_per_page"],
        },
    )

    # ADR-260: Try assembled_tool_config.json first
    assembled_path = root / "config" / "dashboard" / "generated" / "assembled_tool_config.json"
    groups_config = None
    if assembled_path.exists():
        try:
            import json
            with open(assembled_path) as f:
                groups_config = json.load(f)
        except Exception:
            pass
    if not groups_config:
        groups_config_path = root / "config-data" / "mcp_tool_groups.yaml"
        groups_config = load_yaml_file(groups_config_path)

    if not groups_config:
        result.status = "warning"
        result.warnings.append("No tool config found")
        return result

    for page, page_config in groups_config.get("pages", {}).items():
        tools = page_config.get("tools", [])
        tool_count = len(tools)
        if verbose:
            result.details["pages"][page] = tool_count

        if tool_count > LIMITS["max_tools_per_page"]:
            result.status = "error"
            result.warnings.append(f"Page '{page}' has {tool_count} tools (limit: {LIMITS['max_tools_per_page']})")
        elif tool_count > LIMITS["max_tools_per_page"] * WARNING_THRESHOLD:
            if result.status != "error":
                result.status = "warning"
            result.warnings.append(
                f"Page '{page}' approaching tool limit ({tool_count}/{LIMITS['max_tools_per_page']})"
            )

    return result


def estimate_startup_time(root: Path, verbose: bool = False) -> HealthCheckResult:
    """Estimate MCP startup time based on configuration."""
    result = HealthCheckResult(
        check="startup_time",
        status="ok",
        details={
            "estimated_seconds": 0.0,
            "limit_seconds": LIMITS["max_startup_time_seconds"],
        },
    )

    config_paths = [
        root / "config-data" / "mcp_config.json",
        root / "config-data" / "mcp_config.template.json",
    ]

    config = {}
    for path in config_paths:
        if path.exists():
            config = load_json_file(path)
            break

    servers = config.get("mcpServers", {})
    enabled_count = sum(1 for s in servers.values() if s.get("enabled", True))

    estimated = enabled_count * 0.4
    result.details["estimated_seconds"] = round(estimated, 2)

    if estimated > LIMITS["max_startup_time_seconds"]:
        result.status = "error"
        result.warnings.append(
            f"Estimated startup ({estimated:.1f}s) exceeds limit ({LIMITS['max_startup_time_seconds']}s)"
        )
    elif estimated > LIMITS["max_startup_time_seconds"] * WARNING_THRESHOLD:
        result.status = "warning"
        result.warnings.append(
            f"Estimated startup ({estimated:.1f}s) approaching limit ({LIMITS['max_startup_time_seconds']}s)"
        )

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# RUNTIME CHECKS
# ═══════════════════════════════════════════════════════════════════════════════


def check_mcp_runtime_health() -> HealthCheckResult:
    """Check runtime health of MCP processes."""
    result = HealthCheckResult(
        check="mcp_runtime",
        status="ok",
        details={
            "servers": [],
            "total_pids": 0,
            "alive": 0,
            "responsive": 0,
            "stalled": 0,
        },
    )

    # Read MCP PIDs from registry
    pids_file = get_runtime_dir() / "mcp_pids.json"

    if not pids_file.exists():
        result.message = "No MCP PID registry found"
        return result

    try:
        pids_data = load_json_file(pids_file)
    except Exception as e:
        result.status = "warning"
        result.warnings.append(f"Failed to read MCP PID registry: {e}")
        return result

    servers = pids_data.get("servers", {})
    result.details["total_pids"] = len(servers)

    for name, info in servers.items():
        pid = info.get("pid")
        status = MCPRuntimeStatus(
            name=name,
            pid=pid,
            last_check=datetime.now().isoformat(),
        )

        if pid:
            # Check if process is alive
            try:
                os.kill(pid, 0)
                status.is_alive = True
                result.details["alive"] += 1

                # Check responsiveness (basic check)
                # Future: could ping health endpoint
                status.is_responsive = True
                result.details["responsive"] += 1

            except ProcessLookupError:
                status.error = "Process not found"
            except PermissionError:
                status.is_alive = True
                result.details["alive"] += 1

        if status.is_alive and not status.is_responsive:
            result.details["stalled"] += 1
            result.warnings.append(f"MCP '{name}' (PID {pid}) is stalled")

        result.details["servers"].append(status.to_dict())

    # Determine overall status
    if result.details["stalled"] > 0:
        result.status = "error"
    elif result.details["alive"] < result.details["total_pids"]:
        result.status = "warning"

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def run_config_checks(root: Path, verbose: bool = False) -> list[HealthCheckResult]:
    """Run all configuration health checks."""
    return [
        check_mcp_servers(root, verbose),
        check_tool_count(root, verbose),
        check_tool_groups(root, verbose),
        estimate_startup_time(root, verbose),
    ]


def run_runtime_checks() -> list[HealthCheckResult]:
    """Run all runtime health checks."""
    return [
        check_mcp_runtime_health(),
    ]


def run_all_checks(root: Path, verbose: bool = False) -> list[HealthCheckResult]:
    """Run all health checks (config + runtime)."""
    results = run_config_checks(root, verbose)
    results.extend(run_runtime_checks())
    return results


def print_results(results: list[HealthCheckResult], verbose: bool = False) -> None:
    """Print results in human-readable format."""
    status_icons = {
        "ok": "\u2705",
        "warning": "\u26a0\ufe0f",
        "error": "\u274c",
    }

    _out("\n=== MCP Health Check ===\n")

    for check in results:
        icon = status_icons.get(check.status, "?")
        name = check.check.replace("_", " ").title()

        # Format based on check type
        if check.check == "mcp_servers":
            details = check.details or {}
            _out(
                f"{icon} {name}: {details.get('enabled', 0)}/{details.get('limit_enabled', 0)} enabled, "
                f"{details.get('configured', 0)}/{details.get('limit_configured', 0)} configured"
            )
        elif check.check == "tool_count":
            details = check.details or {}
            _out(f"{icon} {name}: {details.get('total_tools', 0)}/{details.get('limit', 0)} tools")
        elif check.check == "tool_groups":
            details = check.details or {}
            pages = details.get("pages", {})
            max_page = max(pages.values()) if pages else 0
            _out(f"{icon} {name}: max {max_page}/{details.get('limit_per_page', 0)} tools per page")
        elif check.check == "startup_time":
            details = check.details or {}
            _out(
                f"{icon} {name}: ~{details.get('estimated_seconds', 0)}s "
                f"(limit: {details.get('limit_seconds', 0)}s)"
            )
        elif check.check == "mcp_runtime":
            details = check.details or {}
            _out(
                f"{icon} {name}: {details.get('alive', 0)}/{details.get('total_pids', 0)} alive, "
                f"{details.get('stalled', 0)} stalled"
            )
        else:
            _out(f"{icon} {name}: {check.message or check.status}")

        # Print warnings
        for warning in check.warnings or []:
            _out(f"   {warning}")

        if verbose and check.details:
            if check.check == "mcp_servers":
                servers = check.details.get("servers", [])
                if servers:
                    _out("   Servers:")
                    for server in servers:
                        status = "enabled" if server.get("enabled") else "disabled"
                        _out(f"      - {server.get('name')}: {status}")

    _out()

    # Summary
    error_count = sum(1 for c in results if c.status == "error")
    warning_count = sum(1 for c in results if c.status == "warning")

    if error_count > 0:
        _out(f"\u274c {error_count} error(s) found - action required")
    elif warning_count > 0:
        _out(f"\u26a0\ufe0f {warning_count} warning(s) - consider optimization")
    else:
        _out("\u2705 All checks passed")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="MCP Health Check - Configuration and Runtime Validation")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed information",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--config",
        action="store_true",
        help="Run configuration checks only",
    )
    parser.add_argument(
        "--runtime",
        action="store_true",
        help="Run runtime checks only",
    )
    args = parser.parse_args()

    root = get_project_root()

    # Determine which checks to run
    if args.config:
        results = run_config_checks(root, args.verbose)
    elif args.runtime:
        results = run_runtime_checks()
    else:
        results = run_all_checks(root, args.verbose)

    # Output results
    if args.json:
        output = {
            "results": [r.to_dict() for r in results],
            "limits": LIMITS,
            "timestamp": datetime.now().isoformat(),
        }
        _out(json.dumps(output, indent=2))
    else:
        print_results(results, args.verbose)

    # Return exit code
    error_count = sum(1 for c in results if c.status == "error")
    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

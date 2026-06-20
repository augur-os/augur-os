#!/usr/bin/env python3
"""
External Service Availability Checker (ADR-077).

Checks health/availability of external services declared in the v2
external_mcp_registry.yaml. Each service type has its own check strategy:

- MCP: Checks if the MCP server process is registered and alive in mcp_pids.json
- CLI: Runs the check_command (e.g., 'gh --version') with a timeout
- App: Checks if a macOS app bundle ID exists on disk via mdfind

Results are cached with a 5-minute TTL to avoid repeated subprocess calls.

Usage:
    python3 service_availability.py                   # Check all services
    python3 service_availability.py --skill career    # Check services used by career skill
    python3 service_availability.py --json            # JSON output
    python3 service_availability.py --service gh      # Check a single service
    python3 service_availability.py --remove gh       # Remove a service from registry
    python3 service_availability.py --remove gh --uninstall  # Remove and uninstall via brew

As a library:
    from service_availability import get_service_status
    status = get_service_status()
    status = get_service_status(skill_name="career")
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from subprocess import run  # nosec B404
from typing import Any, Optional


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    out_file = kwargs.get("file", sys.stdout)
    out_file.write(sep.join(str(arg) for arg in args) + str(end))


# Setup project root
from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

try:
    from src.logging import get_entity_logger
except ImportError:
    import logging as _logging

    def get_entity_logger(name: str):
        lgr = _logging.getLogger(name)
        if not lgr.handlers:
            handler = _logging.StreamHandler()
            handler.setFormatter(_logging.Formatter("%(levelname)s - %(message)s"))
            lgr.addHandler(handler)
            lgr.setLevel(_logging.INFO)
        return lgr


from src.config.paths import get_config_dir, get_runtime_dir

logger = get_entity_logger("service_availability")

# Cache configuration
CACHE_TTL_SECONDS = 300  # 5 minutes
CHECK_COMMAND_TIMEOUT = 5  # seconds

# Status constants
STATUS_CONNECTED = "connected"
STATUS_DISCONNECTED = "disconnected"
STATUS_DEGRADED = "degraded"
STATUS_UNKNOWN = "unknown"


# =============================================================================
# Data structures
# =============================================================================


@dataclass
class ServiceStatus:
    """Status of a single external service."""

    service_id: str
    name: str
    type: str  # mcp, cli, app
    status: str  # connected, disconnected, degraded, unknown
    version: Optional[str] = None
    error: Optional[str] = None
    checked_at: Optional[str] = None
    setup_url: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SkillServiceReport:
    """Service availability report for a specific skill."""

    skill_name: str
    services: list[ServiceStatus] = field(default_factory=list)
    features_blocked: list[str] = field(default_factory=list)
    all_connected: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "services": [s.to_dict() for s in self.services],
            "features_blocked": self.features_blocked,
            "all_connected": self.all_connected,
        }


# =============================================================================
# Cache
# =============================================================================


_status_cache: dict[str, tuple[ServiceStatus, float]] = {}


def _get_cached(service_id: str) -> Optional[ServiceStatus]:
    """Get cached status if within TTL."""
    if service_id in _status_cache:
        status, timestamp = _status_cache[service_id]
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            return status
        del _status_cache[service_id]
    return None


def _set_cached(service_id: str, status: ServiceStatus) -> None:
    """Cache a service status."""
    _status_cache[service_id] = (status, time.time())


def clear_cache() -> None:
    """Clear the status cache."""
    _status_cache.clear()


# =============================================================================
# Registry loading
# =============================================================================


def _load_registry() -> dict[str, Any]:
    """Load the external service registry (v1 and v2 compatible)."""
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not available, cannot load registry")
        return {}

    registry_path = get_config_dir() / "integrations" / "external_mcp_registry.yaml"
    if not registry_path.exists():
        logger.debug(f"Registry not found at {registry_path}")
        return {}

    with open(registry_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    version = data.get("version", 1)
    if version >= 2:
        return data.get("services", {})
    # v1 backward compat: all entries are implicitly type=mcp
    servers = data.get("servers", {})
    for entry in servers.values():
        entry.setdefault("type", "mcp")
    return servers


# =============================================================================
# Check strategies per service type
# =============================================================================


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve command executable to absolute path when available."""
    if not command:
        return command
    resolved = shutil.which(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return command


def _check_mcp_service(service_id: str, service_def: dict[str, Any]) -> ServiceStatus:
    """Check if an MCP server is registered and alive in the PID registry."""
    name = service_def.get("name", service_id)
    setup_url = service_def.get("setup_url")

    pids_file = get_runtime_dir() / "mcp_pids.json"
    if not pids_file.exists():
        return ServiceStatus(
            service_id=service_id,
            name=name,
            type="mcp",
            status=STATUS_UNKNOWN,
            error="PID registry not found",
            setup_url=setup_url,
        )

    try:
        pids_data = json.loads(pids_file.read_text())
    except Exception:
        return ServiceStatus(
            service_id=service_id,
            name=name,
            type="mcp",
            status=STATUS_UNKNOWN,
            error="Failed to read PID registry",
            setup_url=setup_url,
        )

    servers = pids_data.get("servers", {})

    # Check if the service is registered (match by service_id or by name patterns)
    if service_id in servers:
        pid = servers[service_id].get("pid")
        if pid and _is_pid_alive(pid):
            return ServiceStatus(
                service_id=service_id,
                name=name,
                type="mcp",
                status=STATUS_CONNECTED,
                setup_url=setup_url,
            )
        return ServiceStatus(
            service_id=service_id,
            name=name,
            type="mcp",
            status=STATUS_DISCONNECTED,
            error="Process not running",
            setup_url=setup_url,
        )

    # MCP server not in PID registry — check if it's enabled
    # If enabled in registry but not in PID file, it may just not be started
    is_enabled = service_def.get("enabled", False)
    if is_enabled:
        return ServiceStatus(
            service_id=service_id,
            name=name,
            type="mcp",
            status=STATUS_DISCONNECTED,
            error="MCP server not started",
            setup_url=setup_url,
        )

    return ServiceStatus(
        service_id=service_id,
        name=name,
        type="mcp",
        status=STATUS_DISCONNECTED,
        error="Not enabled",
        setup_url=setup_url,
    )


def _check_cli_service(service_id: str, service_def: dict[str, Any]) -> ServiceStatus:
    """Check if a CLI tool is installed by running its check_command."""
    name = service_def.get("name", service_id)
    check_command = service_def.get("check_command", "")
    setup_url = service_def.get("setup_url")

    if not check_command:
        return ServiceStatus(
            service_id=service_id,
            name=name,
            type="cli",
            status=STATUS_UNKNOWN,
            error="No check_command defined",
            setup_url=setup_url,
        )

    # Split the check command into parts
    parts = check_command.split()
    resolved = _resolve_command(parts)

    try:
        result = run(  # nosec B603
            resolved,
            capture_output=True,
            text=True,
            timeout=CHECK_COMMAND_TIMEOUT,
        )
        if result.returncode == 0:
            # Try to extract version from output
            version_str = result.stdout.strip().split("\n")[0] if result.stdout.strip() else None
            return ServiceStatus(
                service_id=service_id,
                name=name,
                type="cli",
                status=STATUS_CONNECTED,
                version=version_str,
                setup_url=setup_url,
            )
        return ServiceStatus(
            service_id=service_id,
            name=name,
            type="cli",
            status=STATUS_DISCONNECTED,
            error=f"Command returned exit code {result.returncode}",
            setup_url=setup_url,
        )
    except FileNotFoundError:
        return ServiceStatus(
            service_id=service_id,
            name=name,
            type="cli",
            status=STATUS_DISCONNECTED,
            error="Command not found",
            setup_url=setup_url,
        )
    except Exception as e:
        return ServiceStatus(
            service_id=service_id,
            name=name,
            type="cli",
            status=STATUS_DISCONNECTED,
            error=str(e),
            setup_url=setup_url,
        )


def _check_app_service(service_id: str, service_def: dict[str, Any]) -> ServiceStatus:
    """Check if a macOS app is installed via bundle ID lookup."""
    name = service_def.get("name", service_id)
    bundle_id = service_def.get("bundle_id", "")
    setup_url = service_def.get("setup_url")

    if not bundle_id:
        return ServiceStatus(
            service_id=service_id,
            name=name,
            type="app",
            status=STATUS_UNKNOWN,
            error="No bundle_id defined",
            setup_url=setup_url,
        )

    if sys.platform != "darwin":
        return ServiceStatus(
            service_id=service_id,
            name=name,
            type="app",
            status=STATUS_UNKNOWN,
            error="App checks only supported on macOS",
            setup_url=setup_url,
        )

    try:
        mdfind = shutil.which("mdfind")
        if not mdfind:
            return ServiceStatus(
                service_id=service_id,
                name=name,
                type="app",
                status=STATUS_UNKNOWN,
                error="mdfind not available",
                setup_url=setup_url,
            )

        result = run(  # nosec B603
            [mdfind, f"kMDItemCFBundleIdentifier == '{bundle_id}'"],
            capture_output=True,
            text=True,
            timeout=CHECK_COMMAND_TIMEOUT,
        )
        if result.returncode == 0 and result.stdout.strip():
            return ServiceStatus(
                service_id=service_id,
                name=name,
                type="app",
                status=STATUS_CONNECTED,
                setup_url=setup_url,
            )
        return ServiceStatus(
            service_id=service_id,
            name=name,
            type="app",
            status=STATUS_DISCONNECTED,
            error="App not installed",
            setup_url=setup_url,
        )
    except Exception as e:
        return ServiceStatus(
            service_id=service_id,
            name=name,
            type="app",
            status=STATUS_DISCONNECTED,
            error=str(e),
            setup_url=setup_url,
        )


def _is_pid_alive(pid: int) -> bool:
    """Check if a PID exists."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        return True


# =============================================================================
# Dispatch
# =============================================================================

_CHECKERS = {
    "mcp": _check_mcp_service,
    "cli": _check_cli_service,
    "app": _check_app_service,
}


def check_service(service_id: str, service_def: dict[str, Any]) -> ServiceStatus:
    """Check a single service, using cache if available."""
    cached = _get_cached(service_id)
    if cached is not None:
        return cached

    service_type = service_def.get("type", "mcp")
    checker = _CHECKERS.get(service_type)

    if checker is None:
        status = ServiceStatus(
            service_id=service_id,
            name=service_def.get("name", service_id),
            type=service_type,
            status=STATUS_UNKNOWN,
            error=f"Unknown service type: {service_type}",
        )
    else:
        status = checker(service_id, service_def)

    from datetime import datetime

    status.checked_at = datetime.now().isoformat()
    _set_cached(service_id, status)
    return status


# =============================================================================
# Public API
# =============================================================================


def get_service_status(
    skill_name: Optional[str] = None,
    service_id: Optional[str] = None,
) -> dict[str, Any]:
    """Check service availability.

    Args:
        skill_name: If provided, only check services used_by this skill.
        service_id: If provided, only check this specific service.

    Returns:
        Dict with service statuses and optional features_blocked info.
    """
    registry = _load_registry()

    if service_id:
        # Check a single service
        service_def = registry.get(service_id)
        if not service_def:
            return {"error": f"Service '{service_id}' not found in registry"}
        status = check_service(service_id, service_def)
        return {"service": status.to_dict()}

    if skill_name:
        # Filter services used_by this skill
        relevant = {}
        for sid, sdef in registry.items():
            used_by = sdef.get("used_by", [])
            if skill_name in used_by:
                relevant[sid] = sdef
    else:
        relevant = registry

    # Check all relevant services
    statuses: list[ServiceStatus] = []
    for sid, sdef in relevant.items():
        statuses.append(check_service(sid, sdef))

    result: dict[str, Any] = {
        "services": [s.to_dict() for s in statuses],
        "summary": {
            "total": len(statuses),
            "connected": sum(1 for s in statuses if s.status == STATUS_CONNECTED),
            "disconnected": sum(1 for s in statuses if s.status == STATUS_DISCONNECTED),
            "unknown": sum(1 for s in statuses if s.status == STATUS_UNKNOWN),
        },
    }

    if skill_name:
        result["skill_name"] = skill_name
        result["all_connected"] = all(s.status == STATUS_CONNECTED for s in statuses) if statuses else True

    return result


def remove_service(service_id: str, uninstall: bool = False) -> dict:
    """Remove a service from the registry.

    Args:
        service_id: The service ID to remove.
        uninstall: For CLI tools, also attempt to uninstall via brew.

    Returns:
        Dict with success status and message.
    """
    try:
        import yaml
    except ImportError:
        return {"success": False, "error": "PyYAML not available"}

    registry_path = get_config_dir() / "integrations" / "external_mcp_registry.yaml"
    if not registry_path.exists():
        return {"success": False, "error": f"Registry not found at {registry_path}"}

    # Load registry
    with open(registry_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    version = data.get("version", 1)
    if version >= 2:
        services = data.get("services", {})
    else:
        services = data.get("servers", {})

    # Validate service exists
    if service_id not in services:
        return {"success": False, "error": f"Service '{service_id}' not found in registry"}

    service_def = services[service_id]
    service_type = service_def.get("type", "mcp")
    service_name = service_def.get("name", service_id)

    # Handle type-specific removal
    messages = []

    if service_type == "cli" and uninstall:
        # Attempt to uninstall via brew
        brew_path = shutil.which("brew")
        if brew_path:
            try:
                result = run(  # nosec B603
                    [brew_path, "uninstall", service_id],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    messages.append(f"Uninstalled '{service_id}' via brew")
                else:
                    messages.append(f"Brew uninstall failed: {result.stderr.strip()}")
            except Exception as e:
                messages.append(f"Brew uninstall error: {str(e)}")
        else:
            messages.append("Homebrew not available; skipping uninstall")

    elif service_type == "app":
        messages.append(f"Cannot auto-uninstall macOS app '{service_name}'. Please uninstall manually.")

    # Remove from registry YAML
    del services[service_id]

    # Clear cache
    if service_id in _status_cache:
        del _status_cache[service_id]

    # Write back to disk
    with open(registry_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False)

    messages.append(f"Removed '{service_id}' from registry")

    return {
        "success": True,
        "service_id": service_id,
        "action": "removed",
        "message": "; ".join(messages),
    }


# =============================================================================
# CLI
# =============================================================================


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="External Service Availability Checker")
    parser.add_argument(
        "--skill",
        help="Check services for a specific skill",
        default=None,
    )
    parser.add_argument(
        "--service",
        help="Check a single service by ID",
        default=None,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip cache (force fresh checks)",
    )
    parser.add_argument(
        "--remove",
        metavar="SERVICE_ID",
        help="Remove a service from the registry",
        default=None,
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="When used with --remove for CLI tools, also uninstall via brew",
    )
    args = parser.parse_args()

    if args.no_cache:
        clear_cache()

    # Handle remove operation
    if args.remove:
        result = remove_service(args.remove, uninstall=args.uninstall)
        if args.json:
            _out(json.dumps(result, indent=2))
        else:
            if result.get("success"):
                _out(f"Success: {result.get('message')}")
            else:
                _out(f"Error: {result.get('error')}")
        return 0 if result.get("success") else 1

    result = get_service_status(skill_name=args.skill, service_id=args.service)

    if args.json:
        _out(json.dumps(result, indent=2))
        return 0

    # Human-readable output
    if "error" in result:
        _out(f"Error: {result['error']}")
        return 1

    if "service" in result:
        # Single service
        svc = result["service"]
        icon = "OK" if svc["status"] == STATUS_CONNECTED else "FAIL"
        _out(f"  {svc['service_id']:20} [{icon}] {svc['name']} ({svc['type']})")
        if svc.get("version"):
            _out(f"    Version: {svc['version']}")
        if svc.get("error"):
            _out(f"    Error: {svc['error']}")
        return 0

    # Multiple services
    services = result.get("services", [])
    summary = result.get("summary", {})
    skill = result.get("skill_name")

    if skill:
        _out(f"Service availability for skill: {skill}")
    else:
        _out("External Service Availability")
    _out("=" * 50)

    for svc in services:
        icon = "OK" if svc["status"] == STATUS_CONNECTED else "FAIL"
        _out(f"  {svc['service_id']:20} [{icon}] {svc['name']} ({svc['type']})")
        if svc.get("version"):
            _out(f"    Version: {svc['version']}")
        if svc.get("error"):
            _out(f"    Error: {svc['error']}")

    _out(f"\nSummary: {summary.get('connected', 0)}/{summary.get('total', 0)} connected")

    if skill and not result.get("all_connected", True):
        _out(f"\nSome services required by '{skill}' are not available.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

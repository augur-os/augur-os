"""External service registry helpers for Browse and capability inventory."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_project_brain_skills_dir, get_project_root

REGISTRY_RELATIVE_PATH = Path("config") / "integrations" / "external_mcp_registry.yaml"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def external_service_registry_path(project_root: Path | None = None) -> Path:
    """Return the canonical external service registry path."""
    return (project_root or get_project_root()) / REGISTRY_RELATIVE_PATH


def load_external_service_registry(
    project_root: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Load v1/v2 external service registry entries keyed by service id."""
    registry_path = external_service_registry_path(project_root)
    if not registry_path.exists():
        return {}

    raw = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return {}

    if int(raw.get("version") or 1) >= 2:
        services = raw.get("services") or {}
    else:
        services = raw.get("servers") or {}
        if isinstance(services, dict):
            for service in services.values():
                if isinstance(service, dict):
                    service.setdefault("type", "mcp")

    if not isinstance(services, dict):
        return {}

    return {str(service_id): dict(service) for service_id, service in services.items() if isinstance(service, dict)}


def external_service_capability_id(service_id: str, service_type: str) -> str:
    """Return the policy inventory id for a registry service when supported."""
    service_slug = _slug(service_id)
    normalized_type = str(service_type or "mcp").strip().lower()
    if normalized_type == "cli":
        return f"cli:{service_slug}"
    if normalized_type == "mcp":
        return f"mcp-server:{service_slug}"
    return f"external-service:{service_slug}"


def _service_availability_script_path(project_root: Path | None = None) -> Path:
    return (
        get_project_brain_skills_dir(project_root or get_project_root())
        / "daemon"
        / "scripts"
        / "service_availability.py"
    )


def _load_service_availability_module(script_path: Path) -> Any:
    """Load the daemon service availability module without requiring packaging."""
    spec = importlib.util.spec_from_file_location(
        "_augur_service_availability",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load module spec for {script_path}")

    script_dir = str(script_path.parent)
    inserted = False
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
        inserted = True

    existing = sys.modules.get(spec.name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if existing is not None:
            sys.modules[spec.name] = existing
        else:
            sys.modules.pop(spec.name, None)
        raise
    finally:
        if inserted:
            try:
                sys.path.remove(script_dir)
            except ValueError:
                pass
    return module


def external_service_status_report(project_root: Path | None = None) -> dict[str, Any]:
    """Return live status from the daemon service availability helper."""
    script_path = _service_availability_script_path(project_root)
    if not script_path.exists():
        return {}

    try:
        module = _load_service_availability_module(script_path)
        result = module.get_service_status()
    except Exception:
        return {}

    return result if isinstance(result, dict) else {}


def external_service_statuses_by_id(
    project_root: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Return live service status records keyed by service id."""
    report = external_service_status_report(project_root)
    services = report.get("services") or []
    if not isinstance(services, list):
        return {}

    statuses: dict[str, dict[str, Any]] = {}
    for service in services:
        if not isinstance(service, dict):
            continue
        service_id = str(service.get("service_id") or "").strip()
        if service_id:
            statuses[service_id] = service
    return statuses


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"


def _service_metadata(
    service_id: str,
    service_type: str,
    service: dict[str, Any],
    status: dict[str, Any],
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "external_service_id": service_id,
        "service_type": service_type,
        "registry": "external_mcp_registry",
        "enabled": _bool_text(service.get("enabled", False)),
    }
    for key in ("tier", "cost", "description", "setup_url", "check_command", "command"):
        value = service.get(key)
        if value not in (None, "", []):
            metadata[key] = value
    used_by = _string_list(service.get("used_by"))
    if used_by:
        metadata["used_by"] = ",".join(used_by)
    args = _string_list(service.get("args"))
    if args:
        metadata["args"] = " ".join(args)
    for key in ("status", "version", "error", "checked_at"):
        value = status.get(key)
        if value not in (None, "", []):
            metadata[key] = value
    return metadata


def external_service_browse_entries(
    project_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Return registry services in the same raw shape as Browse index entries."""
    registry = load_external_service_registry(project_root)
    if not registry:
        return []

    registry_path = external_service_registry_path(project_root)
    statuses = external_service_statuses_by_id(project_root)
    entries: list[dict[str, Any]] = []

    for service_id, service in sorted(registry.items()):
        service_type = str(service.get("type") or "mcp").strip().lower()
        status = statuses.get(service_id, {})
        capability = external_service_capability_id(service_id, service_type)
        title = str(status.get("name") or service.get("name") or service_id)
        description = str(service.get("description") or "")
        metadata = _service_metadata(service_id, service_type, service, status)

        entry: dict[str, Any] = {
            "id": capability,
            "name": service_id,
            "title": title,
            "description": description,
            "hub": "system",
            "type": "integration",
            "source_path": str(registry_path),
            "tags": _string_list(service.get("tags")),
            **metadata,
        }
        if service_type == "cli":
            entry["cli_tools"] = [
                {
                    "name": service_id,
                    "installed": metadata.get("status") == "connected",
                    "version": metadata.get("version") or None,
                    "configured": None,
                    "install_hint": str(service.get("install") or ""),
                    "homepage": service.get("setup_url") or None,
                }
            ]
        entries.append(entry)

    return entries

"""
External MCP server resolution for configure_mcp.

Handles loading the external MCP registry, scanning plugin SKILL.md files for
MCP server requirements, resolving environment variables, and building
external server config entries.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from src.logging import get_entity_logger

logger = get_entity_logger("configure_mcp")


def _load_external_mcp_registry(repo_root: Path) -> dict[str, Any]:
    """Load the external MCP server registry (v2 format).

    Uses 'services:' key. Returns all entries (both MCP and CLI types).
    """
    registry_path = repo_root / "config" / "integrations" / "external_mcp_registry.yaml"
    if not registry_path.exists():
        return {}
    with open(registry_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("services", {})


def _load_env_file(repo_root: Path) -> dict[str, str]:
    """Load .env.mcp file if present. Returns dict of VAR=VALUE pairs."""
    env_path = repo_root / "config" / "integrations" / ".env.mcp"
    if not env_path.exists():
        return {}

    extra: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            extra[key] = value
    return extra


def _extract_mcp_ids_from_services_block(services_block: dict[str, Any]) -> set[str]:
    """Extract MCP service IDs from a services: block in SKILL.md frontmatter.

    Supports:
        services:
          required:
            - id: brightdata
              type: mcp
          optional:
            - id: exa
              type: mcp
    """
    ids: set[str] = set()
    for key in ("required", "optional"):
        entries = services_block.get(key, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_type = entry.get("type", "mcp")
            entry_id = entry.get("id", "")
            if entry_type == "mcp" and entry_id:
                ids.add(entry_id.strip())
    return ids


def _scan_plugin_mcp_requirements(repo_root: Path) -> set[str]:
    """Scan all SKILL.md files for MCP server declarations in frontmatter.

    Supports both legacy format (mcp_servers: [...]) and new format
    (services: {required: [...], optional: [...]}).
    """
    required: set[str] = set()
    plugins_dir = repo_root / "plugins"
    if not plugins_dir.exists():
        return required

    for skill_md in plugins_dir.glob("*/skills/*/SKILL.md"):
        try:
            content = skill_md.read_text(encoding="utf-8")
        except Exception:
            continue

        # Extract YAML frontmatter between --- markers
        if not content.startswith("---"):
            continue
        end = content.find("---", 3)
        if end < 0:
            continue
        frontmatter = content[3:end]
        try:
            meta = yaml.safe_load(frontmatter) or {}
        except Exception:
            continue

        # services: block with required/optional lists
        services_block = meta.get("services")
        if isinstance(services_block, dict):
            required |= _extract_mcp_ids_from_services_block(services_block)

    return required


def _resolve_env_value(value: str, extra_env: dict[str, str]) -> str | None:
    """Resolve ${VAR} placeholders in a string. Returns None if any var is missing."""
    pattern = re.compile(r"\$\{([^}]+)\}")
    missing = False

    def replacer(match: re.Match[str]) -> str:
        nonlocal missing
        var_name = match.group(1)
        resolved = extra_env.get(var_name) or os.environ.get(var_name)
        if not resolved:
            missing = True
            return match.group(0)
        return resolved

    result = pattern.sub(replacer, value)
    return None if missing else result


def _resolve_external_servers(
    registry: dict[str, Any],
    required: set[str],
    extra_env: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """Resolve external MCP servers into config entries.

    A server is included if:
    - It's an MCP type
    - It's enabled in registry, OR required by a plugin
    - All required env vars are available
    """
    resolved: dict[str, dict[str, Any]] = {}

    for server_id, server_def in registry.items():
        # Skip non-MCP service types (cli, app, etc.) — they don't go in IDE config
        service_type = server_def.get("type")
        if service_type != "mcp":
            continue

        # Include if enabled globally or required by a plugin
        is_enabled = server_def.get("enabled", False)
        is_required = server_id in required
        if not is_enabled and not is_required:
            continue

        command = server_def.get("command", "")
        args = server_def.get("args", [])
        env_template = server_def.get("env", {})

        # Resolve env vars
        resolved_env: dict[str, str] = {}
        env_ok = True
        for env_key, env_val in env_template.items():
            if isinstance(env_val, str) and "${" in env_val:
                val = _resolve_env_value(env_val, extra_env)
                if val is None:
                    env_ok = False
                    break
                resolved_env[env_key] = val
            else:
                resolved_env[env_key] = str(env_val)

        if not env_ok:
            # Missing required env vars - silently skip
            logger.debug(f"Skipping external MCP '{server_id}': missing required env vars")
            continue

        entry: dict[str, Any] = {"command": command, "args": list(args)}
        if resolved_env:
            entry["env"] = resolved_env

        resolved[server_id] = entry

    return resolved

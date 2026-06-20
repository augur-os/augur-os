"""
resolve-template and read-active-templates MCP tools.

ADR-450 Step 4.1: Template resolution pipeline that merges base YAML templates
with user overrides from the vault and checks skill dependencies.
Includes enabled-state awareness via local skill state and
auto-enable for internal skills that are disabled but required.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from src.config.paths import get_project_brain_skills_dir, get_project_root, get_vault_config_dir
from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.logging import get_entity_logger
from src.plugins.skill_ui_state import is_skill_enabled, set_skill_enabled

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_entity_logger("mcp")


# ── Skill discovery ──────────────────────────────────────────────────────


@dataclass
class DiscoveredSkill:
    """Metadata for a locally discovered skill."""

    name: str
    dir_path: Path
    hub: str | None = None
    location: str = "skills"  # "skills" or "claude-skills"


_skill_cache: tuple[float, dict[str, DiscoveredSkill]] | None = None
_SKILL_CACHE_TTL = 60.0


def _discover_available_skills() -> dict[str, DiscoveredSkill]:
    """Return cached skill discovery results, refreshing after TTL expiry."""
    global _skill_cache
    now = time.monotonic()
    if _skill_cache and (now - _skill_cache[0]) < _SKILL_CACHE_TTL:
        return _skill_cache[1]
    result = _discover_available_skills_impl()
    _skill_cache = (now, result)
    return result


def _invalidate_skill_cache() -> None:
    """Invalidate the skill discovery cache (for testing)."""
    global _skill_cache
    _skill_cache = None


def _discover_available_skills_impl() -> dict[str, DiscoveredSkill]:
    """Scan project-brain/capabilities/skills/*/SKILL.md.

    Returns a dict mapping skill name -> DiscoveredSkill with enough info
    to check enabled state and auto-enable if needed.
    """
    root = get_project_root()
    available: dict[str, DiscoveredSkill] = {}

    # project-brain/capabilities/skills/{skill}/SKILL.md
    skills_dir = get_project_brain_skills_dir(root)
    if skills_dir.is_dir():
        for skill_md in skills_dir.glob("*/SKILL.md"):
            skill_dir = skill_md.parent
            skill_name = skill_dir.name
            available[skill_name] = DiscoveredSkill(
                name=skill_name,
                dir_path=skill_dir,
                hub=None,
                location="skills",
            )

    return available


# ── Enabled-state helpers ──────────────────────────────────────────────


def _is_skill_enabled(skill: DiscoveredSkill) -> bool:
    """Check whether a discovered skill is enabled via local skill state."""
    return is_skill_enabled(skill.name)


def _auto_enable_skill(skill: DiscoveredSkill) -> bool:
    """Auto-enable a disabled internal skill via the compatibility writer.

    Returns True if the skill was successfully auto-enabled, False on error.
    For canonical skills this writes runtime-backed local state. Legacy bundle
    layouts still route through the compatibility `.config` path.
    """
    if skill.location == "plugins" and skill.hub:
        # If the hub itself is disabled, don't auto-enable individual skills
        logger.info(
            "Skipping auto-enable bundle-level guard for %s: legacy plugin layout only",
            skill.name,
        )
        return False

    try:
        set_skill_enabled(skill.name, True)
        logger.info("Auto-enabled skill %s at %s", skill.name, skill.dir_path)
        return True
    except Exception as exc:
        logger.warning("Failed to auto-enable skill %s: %s", skill.name, exc)
        return False


# ── Template loading ──────────────────────────────────────────────────────


def _load_yaml(path: Path) -> dict[str, Any] | None:
    """Load a YAML file, returning None if missing or invalid."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except FileNotFoundError:
        return None
    except Exception as exc:
        logger.warning("Failed to load YAML %s: %s", path, exc)
        return None


def _base_template_path(hub: str, template_id: str) -> Path:
    return get_project_root() / "plugins" / "ui" / "templates" / hub / f"{template_id}.yaml"


def _override_path(hub: str, template_id: str) -> Path:
    return get_vault_config_dir() / "dashboard" / "templates" / hub / f"{template_id}.overrides.yaml"


def _active_templates_path() -> Path:
    return get_vault_config_dir() / "dashboard" / "active.yaml"


# ── Dependency checking ───────────────────────────────────────────────────


def _check_dependency(
    skill_name: str,
    available_skills: dict[str, DiscoveredSkill],
    *,
    auto_enable: bool = True,
) -> dict[str, Any]:
    """Build a DependencyStatus dict for a skill.

    Checks availability (SKILL.md exists), enabled state (.config), and
    optionally auto-enables disabled internal skills.

    Returns dict with keys:
        skill: str — the skill name
        available: bool — SKILL.md found locally
        enabled: bool — .config says enabled (or was just auto-enabled)
        community: bool — True if not found locally (would need install)
        autoEnabled: bool — True if skill was auto-enabled during this resolution
    """
    discovered = available_skills.get(skill_name)

    if discovered is None:
        # Not found locally — community skill needed
        return {
            "skill": skill_name,
            "available": False,
            "enabled": False,
            "community": True,
            "autoEnabled": False,
        }

    # Found locally — check enabled state
    enabled = _is_skill_enabled(discovered)
    auto_enabled = False

    if not enabled and auto_enable:
        # Attempt to auto-enable the skill
        auto_enabled = _auto_enable_skill(discovered)
        if auto_enabled:
            enabled = True

    return {
        "skill": skill_name,
        "available": True,
        "enabled": enabled,
        "community": False,
        "autoEnabled": auto_enabled,
    }


# ── Merge pipeline ────────────────────────────────────────────────────────


def _resolve_template(hub: str, template_id: str) -> dict[str, Any]:
    """Core merge logic: base + overrides -> ResolvedTemplate JSON."""
    base_path = _base_template_path(hub, template_id)
    base = _load_yaml(base_path)
    if base is None:
        return {"error": f"Base template not found: {hub}/{template_id}"}

    override_path = _override_path(hub, template_id)
    overrides = _load_yaml(override_path)
    has_override = overrides is not None

    available_skills = _discover_available_skills()

    # Cache dependency checks per skill to avoid duplicate auto-enable side effects
    # and ensure consistent results between block-level and summary-level checks.
    _dep_cache: dict[str, dict[str, Any]] = {}

    def _cached_check_dependency(skill_name: str) -> dict[str, Any]:
        if skill_name not in _dep_cache:
            _dep_cache[skill_name] = _check_dependency(skill_name, available_skills)
        return _dep_cache[skill_name]

    # Index base blocks by id
    base_blocks: list[dict[str, Any]] = base.get("blocks") or []
    base_block_map: dict[str, dict[str, Any]] = {b["id"]: b for b in base_blocks}

    # Index base actions by id
    base_actions: list[dict[str, Any]] = base.get("actions") or []
    base_action_map: dict[str, dict[str, Any]] = {a["id"]: a for a in base_actions}

    # Override maps
    block_overrides: dict[str, dict[str, Any]] = (overrides or {}).get("blocks") or {}
    action_overrides: dict[str, dict[str, Any]] = (overrides or {}).get("actions") or {}

    # Track orphaned overrides: user customized blocks that base has removed
    orphaned: list[str] = []

    # ── Resolve blocks ────────────────────────────────────────────────
    resolved_blocks: list[dict[str, Any]] = []
    processed_block_ids: set[str] = set()

    # Process base blocks (possibly merged with overrides)
    for block_id, base_block in base_block_map.items():
        processed_block_ids.add(block_id)
        override = block_overrides.get(block_id)

        if override and override.get("removed"):
            # Block with removed: true -> hidden
            continue

        source = base_block["source"]
        block_key = base_block["block"]
        span = base_block.get("span", 6)
        order = base_block.get("order", 0)
        config = dict(base_block.get("config") or {})

        if override:
            # Merge: override wins for present keys
            if "span" in override:
                span = override["span"]
            if "order" in override:
                order = override["order"]
            if "config" in override and override["config"]:
                config.update(override["config"])

        registry_key = f"{source}:{block_key}"
        resolved_blocks.append(
            {
                "id": block_id,
                "registryKey": registry_key,
                "span": span,
                "order": order,
                "config": config,
                "userAdded": False,
                "dependency": _cached_check_dependency(source),
            }
        )

    # Process override-only blocks (user-added)
    for block_id, override in block_overrides.items():
        if block_id in processed_block_ids:
            continue

        if override.get("removed"):
            continue

        # User-added block must have source and block
        source = override.get("source")
        block_key = override.get("block")
        if not source or not block_key:
            # Orphaned: override references a block_id that no longer exists in base
            # and doesn't have enough info to render as user-added
            orphaned.append(block_id)
            continue

        registry_key = f"{source}:{block_key}"
        resolved_blocks.append(
            {
                "id": block_id,
                "registryKey": registry_key,
                "span": override.get("span", 6),
                "order": override.get("order", 99),
                "config": dict(override.get("config") or {}),
                "userAdded": True,
                "dependency": _cached_check_dependency(source),
            }
        )

    # Detect orphaned overrides: overrides that reference base blocks
    # that were removed from the base (block_id was in overrides with
    # customizations but not in base and not user-added)
    for block_id in block_overrides:
        if block_id in processed_block_ids:
            continue
        if block_id not in {b["id"] for b in resolved_blocks}:
            if block_id not in orphaned:
                orphaned.append(block_id)

    # Sort by order
    resolved_blocks.sort(key=lambda b: b["order"])

    # ── Resolve actions ───────────────────────────────────────────────
    resolved_actions: list[dict[str, Any]] = []
    for action_id, base_action in base_action_map.items():
        override = action_overrides.get(action_id)
        if override and override.get("removed"):
            continue
        resolved_actions.append(
            {
                "id": action_id,
                "source": base_action["source"],
                "action": base_action["action"],
            }
        )

    # ── Dependency summary ────────────────────────────────────────────
    required_skills: list[str] = base.get("requires") or []
    dep_details: list[dict[str, Any]] = []
    available_list: list[str] = []
    missing_list: list[str] = []
    auto_enabled_list: list[str] = []

    for req_skill in required_skills:
        dep = _cached_check_dependency(req_skill)
        dep_details.append(dep)
        if dep["available"]:
            available_list.append(req_skill)
            if dep["autoEnabled"]:
                auto_enabled_list.append(req_skill)
        else:
            missing_list.append(req_skill)

    return {
        "name": base.get("name", template_id),
        "description": base.get("description", ""),
        "hub": base.get("hub", hub),
        "icon": base.get("icon", "LayoutGrid"),
        "layout": base.get("layout", "2-column"),
        "blocks": resolved_blocks,
        "actions": resolved_actions,
        "hasOverride": has_override,
        "orphanedOverrides": orphaned,
        "dependencies": {
            "required": required_skills,
            "available": available_list,
            "missing": missing_list,
            "autoEnabled": auto_enabled_list,
            "details": dep_details,
        },
    }


# ── Active templates ──────────────────────────────────────────────────────


def _read_active_templates(hub: str | None = None) -> dict[str, Any]:
    """Read active.yaml and return active template IDs per hub."""
    active_path = _active_templates_path()
    data = _load_yaml(active_path)
    if data is None:
        return {}

    if hub:
        entry = data.get(hub)
        if entry is None:
            return {}
        return {hub: entry}

    return data


_active_yaml_lock = threading.Lock()


def _activate_template(hub: str, template_id: str, *, active: bool = True) -> dict[str, Any]:
    """Activate or deactivate a template in active.yaml for a given hub.

    Returns dict with ok, hub, template_id, active, and the updated templates list.
    """
    # Validate that the template file actually exists before activation
    if active:
        template_path = _base_template_path(hub, template_id)
        if not template_path.is_file():
            return {"ok": False, "error": f"Template {hub}/{template_id} not found"}

    with _active_yaml_lock:
        active_path = _active_templates_path()
        data = _load_yaml(active_path) or {}

        hub_entry = data.get(hub)
        if not isinstance(hub_entry, dict):
            hub_entry = {"templates": []}
        templates: list[str] = hub_entry.get("templates") or []

        if active:
            if template_id not in templates:
                templates.append(template_id)
        else:
            templates = [t for t in templates if t != template_id]

        hub_entry["templates"] = templates
        data[hub] = hub_entry

        # Ensure parent directory exists
        active_path.parent.mkdir(parents=True, exist_ok=True)
        active_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")

    return {
        "ok": True,
        "hub": hub,
        "template_id": template_id,
        "active": active,
        "templates": templates,
    }


# ── Template catalog ─────────────────────────────────────────────────────

_SEED_DIR = Path(__file__).resolve().parent / "seeds"


def _load_seed_templates_catalog(hub: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """Load seed template catalog data when no real templates exist."""
    seed_path = _SEED_DIR / "templates-catalog.json"
    if not seed_path.exists():
        return {}
    try:
        import json as _json

        data = _json.loads(seed_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        if hub:
            filtered = data.get(hub, [])
            return {hub: filtered} if filtered else {}
        return data
    except Exception:
        return {}


def _list_templates_catalog(hub: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """Scan all template YAML files and return catalog entries grouped by hub.

    Each entry includes id, name, description, hub, icon, requires, and
    whether the template is currently active in the user's active.yaml.
    """
    templates_dir = get_project_root() / "plugins" / "ui" / "templates"
    if not templates_dir.is_dir():
        # Seed fallback: return starter templates when directory doesn't exist
        return _load_seed_templates_catalog(hub)

    # Read active state
    active_data = _load_yaml(_active_templates_path()) or {}

    # Determine which hub directories to scan
    if hub:
        hub_dirs = [templates_dir / hub] if (templates_dir / hub).is_dir() else []
    else:
        hub_dirs = [d for d in sorted(templates_dir.iterdir()) if d.is_dir()]

    result: dict[str, list[dict[str, Any]]] = {}

    for hub_dir in hub_dirs:
        hub_name = hub_dir.name
        active_ids: list[str] = []
        hub_active = active_data.get(hub_name)
        if isinstance(hub_active, dict):
            active_ids = hub_active.get("templates", [])

        entries: list[dict[str, Any]] = []
        for yaml_path in sorted(hub_dir.glob("*.yaml")):
            template_id = yaml_path.stem
            data = _load_yaml(yaml_path)
            if data is None:
                continue

            entries.append(
                {
                    "id": template_id,
                    "name": data.get("name", template_id),
                    "description": data.get("description", ""),
                    "hub": data.get("hub", hub_name),
                    "icon": data.get("icon", "LayoutGrid"),
                    "requires": data.get("requires", []),
                    "active": template_id in active_ids,
                }
            )

        if entries:
            result[hub_name] = entries

    # Seed fallback: return starter templates when no real templates found
    if not result:
        return _load_seed_templates_catalog(hub)

    return result


# ── Save template override ────────────────────────────────────────────────

_override_yaml_lock = threading.Lock()


def _save_template_override(hub: str, template_id: str, overrides: dict[str, Any]) -> dict[str, Any]:
    """Write a template override YAML to the vault.

    The override file is written to:
        get_vault_config_dir()/dashboard/templates/{hub}/{id}.overrides.yaml

    The overrides dict is written as-is, with a ``base`` key prepended
    to record which template this overrides.
    """
    # Validate the base template exists
    base_path = _base_template_path(hub, template_id)
    if not base_path.is_file():
        return {"ok": False, "error": f"Base template not found: {hub}/{template_id}"}

    override_data: dict[str, Any] = {
        "base": f"{hub}/{template_id}",
    }
    override_data.update(overrides)

    target = _override_path(hub, template_id)

    with _override_yaml_lock:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.dump(override_data, default_flow_style=False),
            encoding="utf-8",
        )

    logger.info("Saved template override: %s -> %s", f"{hub}/{template_id}", target)
    return {"ok": True, "path": str(target)}


# ── MCP registration ─────────────────────────────────────────────────────


def register_template_tools(
    mcp: FastMCP,
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """Register template resolution MCP tools."""

    @mcp.tool(
        name="resolve-template",
        annotations=tool_annotations(
            {
                "title": "Resolve Dashboard Template",
                "readOnlyHint": False,  # may auto-enable disabled skills via .config writes
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def resolve_template(hub: str, id: str) -> str:
        """Resolve a dashboard template by merging base YAML with user overrides.

        Reads the base template from plugins/ui/templates/{hub}/{id}.yaml,
        applies user overrides from get_vault_config_dir()/dashboard/templates/{hub}/{id}.overrides.yaml,
        and checks skill dependencies.

        Args:
            hub: Hub identifier (e.g. "brain", "career")
            id: Template identifier (e.g. "library", "memory")

        Returns:
            str: JSON matching the ResolvedTemplate type
        """
        metrics.track_tool("resolve_template", hub=hub, template_id=id)
        result = _resolve_template(hub, id)
        return json.dumps(result)

    @mcp.tool(
        name="read-active-templates",
        annotations=tool_annotations(
            {
                "title": "Read Active Templates",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def read_active_templates(hub: str | None = None) -> str:
        """Read the active template configuration per hub.

        Reads get_vault_config_dir()/dashboard/active.yaml and returns which templates
        are active for each hub.

        Args:
            hub: Optional hub filter. If None, returns all hubs.

        Returns:
            str: JSON mapping hub -> {templates: [...], order?: {...}}
        """
        metrics.track_tool("read_active_templates", hub=hub)
        result = _read_active_templates(hub)
        return json.dumps(result)

    @mcp.tool(
        name="list-templates-catalog",
        annotations=tool_annotations(
            {
                "title": "List Templates Catalog",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def list_templates_catalog(hub: str | None = None) -> str:
        """List all available templates for the template catalog UI.

        Scans plugins/ui/templates/{hub}/*.yaml for all template definitions
        and cross-references with active.yaml to mark activation state.

        Args:
            hub: Optional hub filter. If None, returns templates for all hubs.

        Returns:
            str: JSON mapping hub -> list of template catalog entries
        """
        metrics.track_tool("list_templates_catalog", hub=hub)
        result = _list_templates_catalog(hub)
        return json.dumps(result)

    @mcp.tool(
        name="activate-template",
        annotations=tool_annotations(
            {
                "title": "Activate/Deactivate Dashboard Template",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def activate_template(
        hub: str,
        template_id: str = "",
        templateId: str = "",
        active: bool = True,
    ) -> str:
        """Activate or deactivate a dashboard template for a hub.

        Writes to get_vault_config_dir()/dashboard/active.yaml to add or remove
        a template from the hub's active templates list.

        Args:
            hub: Hub identifier (e.g. "brain", "career")
            template_id: Template to activate/deactivate (e.g. "library")
            active: True to activate, False to deactivate (default True)

        Returns:
            str: JSON with ok, hub, template_id, active, templates
        """
        # camelCase alias (ADR-465)
        template_id = template_id or templateId

        metrics.track_tool(
            "activate_template",
            hub=hub,
            template_id=template_id,
            active=active,
        )
        result = _activate_template(hub, template_id, active=active)
        return json.dumps(result)

    @mcp.tool(
        name="save-template-override",
        annotations=tool_annotations(
            {
                "title": "Save Template Override",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def save_template_override(
        hub: str,
        id: str,
        overrides: dict[str, Any],
    ) -> str:
        """Save a template override YAML to the user's vault.

        Writes override configuration to
        get_vault_config_dir()/dashboard/templates/{hub}/{id}.overrides.yaml.
        The overrides dict should contain a ``blocks`` key mapping block IDs
        to their override properties (order, config, span, removed, etc.).

        Args:
            hub: Hub identifier (e.g. "brain", "career")
            id: Template identifier (e.g. "library", "memory")
            overrides: Override content dict with blocks and optional actions

        Returns:
            str: JSON with ok and path of written file
        """
        metrics.track_tool(
            "save_template_override",
            hub=hub,
            template_id=id,
        )
        result = _save_template_override(hub, id, overrides)
        return json.dumps(result)


__all__ = ["register_template_tools", "_invalidate_skill_cache", "_save_template_override"]

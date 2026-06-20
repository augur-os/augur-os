"""MCP Tool Configuration - Enable/disable MCP tools via configuration.

This module manages which MCP tools are exposed to IDE clients.
By default, all tools are enabled but users can disable tools they don't
need to reduce cognitive load and focus the IDE on useful capabilities.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_config_dir


def get_mcp_config_path() -> Path:
    """Get the path to mcp_tools.yaml configuration."""
    return get_config_dir() / "mcp_tools.yaml"


# Default tool categories - loaded from mcp_tools.yaml
# Fallback hardcoded defaults only used if YAML file doesn't exist
_DEFAULT_TOOL_CATEGORIES_CACHE: dict[str, dict[str, Any]] | None = None


def _get_default_yaml_path() -> Path:
    """Get the path to the default mcp_tools.yaml bundled with the code."""
    return Path(__file__).parent / "mcp_tools.yaml"


def _load_default_tool_categories() -> dict[str, dict[str, Any]]:
    """Load default tool categories from YAML. Fails fast if missing (ADR-084)."""
    global _DEFAULT_TOOL_CATEGORIES_CACHE
    if _DEFAULT_TOOL_CATEGORIES_CACHE is not None:
        return _DEFAULT_TOOL_CATEGORIES_CACHE

    default_yaml = _get_default_yaml_path()
    if not default_yaml.exists():
        from src.logging.self_heal_event import emit_heal_event

        emit_heal_event(
            source="mcp_tools",
            category="config_missing",
            severity="high",
            message=f"mcp_tools.yaml not found at {default_yaml}",
            context={"expected_path": str(default_yaml), "fallback_removed": True},
        )
        raise FileNotFoundError(f"mcp_tools.yaml not found: {default_yaml}")

    try:
        with open(default_yaml, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        categories = data.get("categories", {})
        result = {}
        for cat_name, cat_info in categories.items():
            result[cat_name] = {
                "description": cat_info.get("description", ""),
                "tools": cat_info.get("tools", []),
                "recommended": cat_info.get("recommended", False),
            }
        _DEFAULT_TOOL_CATEGORIES_CACHE = result
        return result
    except Exception as e:
        from src.logging.self_heal_event import emit_heal_event

        emit_heal_event(
            source="mcp_tools",
            category="config_missing",
            severity="high",
            message=f"Failed to parse mcp_tools.yaml: {e}",
            context={"path": str(default_yaml), "fallback_removed": True},
        )
        raise


# Backwards compatible accessor - use this instead of the old constant
def get_default_tool_categories() -> dict[str, dict[str, Any]]:
    """Get default tool categories (loaded from YAML)."""
    return _load_default_tool_categories()


# Alias for backwards compatibility (deprecated - use get_default_tool_categories())
DEFAULT_TOOL_CATEGORIES = _load_default_tool_categories()


def load_mcp_tools_config() -> dict[str, Any]:
    """
    Load MCP tools configuration.

    Returns:
        dict with structure:
        {
            "version": "1.0",
            "last_updated": "ISO timestamp",
            "mode": "allowlist" | "denylist",  # allowlist = only listed tools enabled
            "categories": {
                "core": {"enabled": True},
                "training": {"enabled": False},
                ...
            },
            "tools": {
                "list-skills": {"enabled": True, "category": "core"},
                "training-start": {"enabled": False, "category": "training"},
                ...
            },
            "presets": {
                "minimal": ["core", "context"],
                "standard": ["core", "context", "execution"],
                "full": ["core", "context", "execution", "training", "background-jobs", "diagnostics"],
            },
            "active_preset": "standard" | None
        }
    """
    config_path = get_mcp_config_path()

    if not config_path.exists():
        return _get_default_config()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        # Merge with defaults for any missing tools/categories
        default_config = _get_default_config()

        # Ensure all default categories exist
        if "categories" not in config:
            config["categories"] = {}
        for cat_name, cat_info in default_config["categories"].items():
            if cat_name not in config["categories"]:
                config["categories"][cat_name] = cat_info

        # Ensure all default tools exist
        if "tools" not in config:
            config["tools"] = {}
        for tool_name, tool_info in default_config["tools"].items():
            if tool_name not in config["tools"]:
                config["tools"][tool_name] = tool_info

        return config
    except Exception:
        return _get_default_config()


def _get_default_config() -> dict[str, Any]:
    """Generate default configuration with standard preset active."""
    config: dict[str, Any] = {
        "version": "1.0",
        "last_updated": None,
        "mode": "category",  # Enable/disable by category
        "categories": {},
        "tools": {},
        "presets": {
            "minimal": {
                "description": "Just skill discovery - read only",
                "categories": ["core"],
            },
            "standard": {
                "description": "Discovery + context + execution",
                "categories": ["core", "context", "execution"],
            },
            "full": {
                "description": "All capabilities including self-update",
                "categories": list(DEFAULT_TOOL_CATEGORIES.keys()),
            },
        },
        "active_preset": "standard",
    }

    # Build categories and tools from defaults
    for cat_name, cat_info in DEFAULT_TOOL_CATEGORIES.items():
        # Standard preset enables core, context, execution
        enabled = cat_name in ["core", "context", "execution"]
        config["categories"][cat_name] = {
            "enabled": enabled,
            "description": cat_info["description"],
            "recommended": cat_info.get("recommended", False),
        }

        for tool_name in cat_info["tools"]:
            config["tools"][tool_name] = {
                "enabled": enabled,
                "category": cat_name,
            }

    return config


def save_mcp_tools_config(config: dict[str, Any]) -> None:
    """Save MCP tools configuration."""
    config_path = get_mcp_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config["last_updated"] = datetime.now().isoformat()

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)


def get_enabled_tools() -> set[str]:
    """Get set of enabled tool names."""
    config = load_mcp_tools_config()
    return {tool_name for tool_name, tool_info in config.get("tools", {}).items() if tool_info.get("enabled", True)}


def is_tool_enabled(tool_name: str) -> bool:
    """Check if a specific tool is enabled."""
    config = load_mcp_tools_config()
    tool_info = config.get("tools", {}).get(tool_name)

    if tool_info is None:
        # Unknown tool - allow by default (for dynamic tools)
        return True

    return tool_info.get("enabled", True)


def set_tool_enabled(tool_name: str, enabled: bool) -> None:
    """Enable or disable a specific tool."""
    config = load_mcp_tools_config()

    if tool_name in config.get("tools", {}):
        config["tools"][tool_name]["enabled"] = enabled
        # Clear active preset since we're doing custom config
        config["active_preset"] = None
        save_mcp_tools_config(config)


def set_category_enabled(category_name: str, enabled: bool) -> None:
    """Enable or disable all tools in a category."""
    config = load_mcp_tools_config()

    if category_name not in config.get("categories", {}):
        return

    config["categories"][category_name]["enabled"] = enabled

    # Update all tools in this category
    for tool_name, tool_info in config.get("tools", {}).items():
        if tool_info.get("category") == category_name:
            tool_info["enabled"] = enabled

    # Clear active preset
    config["active_preset"] = None
    save_mcp_tools_config(config)


def apply_preset(preset_name: str) -> bool:
    """Apply a preset configuration."""
    config = load_mcp_tools_config()
    presets = config.get("presets", {})

    if preset_name not in presets:
        return False

    preset = presets[preset_name]
    enabled_categories = set(preset.get("categories", []))

    # Update all categories
    for cat_name, cat_info in config.get("categories", {}).items():
        cat_info["enabled"] = cat_name in enabled_categories

    # Update all tools based on their category
    for tool_name, tool_info in config.get("tools", {}).items():
        tool_category = tool_info.get("category")
        tool_info["enabled"] = tool_category in enabled_categories

    config["active_preset"] = preset_name
    save_mcp_tools_config(config)
    return True


def get_tools_summary() -> dict[str, Any]:
    """Get a summary of tool configuration for the dashboard."""
    config = load_mcp_tools_config()

    # Count enabled/total per category
    category_stats = {}
    for cat_name, cat_info in config.get("categories", {}).items():
        cat_tools = [
            tool_name
            for tool_name, tool_info in config.get("tools", {}).items()
            if tool_info.get("category") == cat_name
        ]
        enabled_count = sum(1 for t in cat_tools if config["tools"][t].get("enabled", True))
        category_stats[cat_name] = {
            "enabled": cat_info.get("enabled", True),
            "description": cat_info.get("description", ""),
            "recommended": cat_info.get("recommended", False),
            "tools_total": len(cat_tools),
            "tools_enabled": enabled_count,
            "tools": cat_tools,
        }

    enabled_tools = get_enabled_tools()
    all_tools = set(config.get("tools", {}).keys())

    return {
        "version": config.get("version", "1.0"),
        "last_updated": config.get("last_updated"),
        "active_preset": config.get("active_preset"),
        "presets": config.get("presets", {}),
        "total_tools": len(all_tools),
        "enabled_tools": len(enabled_tools),
        "categories": category_stats,
        "tools": config.get("tools", {}),
    }


def register_dynamic_tool(tool_name: str, category: str = "dynamic") -> None:
    """Register a dynamically discovered tool in the config.

    Called when dynamic_registry discovers skill scripts.
    """
    config = load_mcp_tools_config()

    # Add dynamic category if not exists
    if "dynamic" not in config.get("categories", {}):
        config["categories"]["dynamic"] = {
            "enabled": True,  # Dynamic tools enabled by default
            "description": "Dynamically discovered skill scripts",
            "recommended": False,
        }

    # Add tool if not exists (don't override existing config)
    if tool_name not in config.get("tools", {}):
        # Inherit enabled state from category
        cat_enabled = config["categories"].get(category, {}).get("enabled", True)
        config["tools"][tool_name] = {
            "enabled": cat_enabled,
            "category": category,
        }
        save_mcp_tools_config(config)


# =============================================================================
# Auto-Configuration based on Usage & Project Context
# =============================================================================


def _load_usage_metrics() -> dict[str, Any]:
    """Load MCP usage metrics from the metrics file."""
    from src.config.paths import get_dynamic_runtime_dir

    metrics_path = get_dynamic_runtime_dir() / "metrics" / "mcp" / "mcp-metrics.json"

    if not metrics_path.exists():
        return {
            "tool_calls": {},
            "skill_usage": {},
            "module_usage": {},
            "sessions": 0,
        }

    try:
        return json.loads(metrics_path.read_text())
    except Exception:
        return {"tool_calls": {}, "skill_usage": {}, "sessions": 0}


def _detect_project_context() -> dict[str, Any]:
    """Detect project context to inform tool recommendations."""
    from src.config.paths import get_project_brain_skills_dir, get_project_root

    project_root = get_project_root()
    context: dict[str, Any] = {
        "has_careers": False,
        "has_recipes": False,
        "has_agents": False,
        "has_dashboard": False,
        "has_testing": False,
        "active_verticals": [],
        "active_factories": [],
    }

    # ADR-770: shared/team skills live under project-brain/capabilities/skills.
    skills_dir = get_project_brain_skills_dir(project_root)

    # Check for active vertical skills.
    # ADR-Track-3a: replace hardcoded enumeration with dynamic discovery
    # via the augur_shared.skill_registry. Vertical skills are defined as
    # vault-tier skills (consumer-facing user surfaces that ship as vault
    # plugins, e.g., career, lifestyle, finance, etc.). Project-tier
    # skills (ai, knowledge, etc.) are not "vertical" by this definition.
    context["has_careers"] = (skills_dir / "career" / "SKILL.md").exists()
    context["has_recipes"] = (skills_dir / "recipes" / "SKILL.md").exists()
    try:
        from src.mcp.augur_shared.skill_registry import all_vault_skills

        vertical_skills = all_vault_skills()
    except Exception:
        # Fallback to empty during early bootstrap when the registry
        # cannot be loaded (rare; logs warn at the call site).
        vertical_skills = frozenset()
    if skills_dir.exists():
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir() and skill_dir.name in vertical_skills and (skill_dir / "SKILL.md").exists():
                context["active_verticals"].append(skill_dir.name)

    # Check for active dev/orchestration skills
    factory_skills = {"platform-admin", "frontend", "validator", "advisor", "mcp-app-factory", "advisor"}
    if skills_dir.exists():
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir() and skill_dir.name in factory_skills and (skill_dir / "SKILL.md").exists():
                context["active_factories"].append(skill_dir.name)
                if skill_dir.name == "validator":
                    context["has_testing"] = True
                if skill_dir.name in {"platform-admin", "advisor"}:
                    context["has_agents"] = True

    # Check for dashboard
    dashboard_dir = project_root / "apps" / "dashboard"
    context["has_dashboard"] = dashboard_dir.exists()

    return context


def auto_configure_tools() -> dict[str, Any]:
    """
    Automatically configure MCP tools based on usage metrics and project context.

    Algorithm:
    1. Start with 'standard' preset as baseline
    2. Analyze usage metrics to find frequently used tools
    3. Enable categories that contain frequently used tools
    4. Consider project context (e.g., enable training if career is active)
    5. Disable categories with zero usage after enough sessions

    Returns:
        dict with:
        - enabled_categories: list of enabled categories
        - disabled_categories: list of disabled categories
        - reason: explanation of why each decision was made
        - tools_enabled: count
        - confidence: how confident the recommendation is (based on data volume)
    """
    metrics = _load_usage_metrics()
    context = _detect_project_context()
    config = load_mcp_tools_config()

    tool_calls = metrics.get("tool_calls", {})
    skill_usage = metrics.get("skill_usage", {})
    sessions = metrics.get("sessions", 0)

    # Calculate total calls for percentages
    total_calls = sum(tool_calls.values()) if tool_calls else 0

    # Track recommendations
    recommendations = {
        "core": {"enable": True, "reason": "Essential for skill discovery"},
        "context": {"enable": True, "reason": "Essential for personalized context"},
        "execution": {"enable": True, "reason": "Essential for running skills"},
        "self-update": {"enable": False, "reason": "Not commonly needed"},
        "rollback": {"enable": False, "reason": "Not commonly needed"},
        "training": {"enable": False, "reason": "Not commonly needed"},
        "background-jobs": {"enable": False, "reason": "Not commonly needed"},
        "diagnostics": {"enable": False, "reason": "Only needed for debugging"},
    }

    # Get category tool mappings
    category_tools: dict[str, set[str]] = {}
    for cat_name, cat_info in DEFAULT_TOOL_CATEGORIES.items():
        tools = cat_info.get("tools", [])
        if isinstance(tools, list):
            category_tools[cat_name] = set(tool for tool in tools if isinstance(tool, str))
        else:
            category_tools[cat_name] = set()

    # Analyze usage per category
    category_usage = {}
    for cat_name, tools in category_tools.items():
        usage = sum(tool_calls.get(tool, 0) for tool in tools)
        category_usage[cat_name] = usage

    # Rule 1: Enable categories with significant usage (>5% of calls or >10 calls)
    if total_calls >= 20:  # Need enough data
        for cat_name, usage in category_usage.items():
            if usage > 10 or (total_calls > 0 and usage / total_calls > 0.05):
                recommendations[cat_name]["enable"] = True
                recommendations[cat_name][
                    "reason"
                ] = f"High usage ({usage} calls, {usage/total_calls*100:.1f}% of total)"

    # Rule 2: Project context overrides
    if context["has_careers"]:
        recommendations["training"]["enable"] = True
        recommendations["training"]["reason"] = "Careers vertical active - training mode useful"

    if context["has_agents"] and sessions >= 10:
        recommendations["self-update"]["enable"] = True
        recommendations["self-update"]["reason"] = "Active development - self-update helps iterate"

    if context["has_testing"]:
        recommendations["diagnostics"]["enable"] = True
        recommendations["diagnostics"]["reason"] = "Testing agents active - diagnostics useful"

    # Rule 3: Skill-based recommendations
    career_skills = ["career", "interview", "job-analyzer", "interview-prep"]
    if any(skill in skill_usage for skill in career_skills):
        recommendations["training"]["enable"] = True
        recommendations["training"]["reason"] = "Career skills in use - training improves job matching"

    # Rule 5: Background jobs if any async operations detected
    bg_tools = ["get-job-status", "list-jobs", "cancel-job"]
    if any(tool_calls.get(tool, 0) > 0 for tool in bg_tools):
        recommendations["background-jobs"]["enable"] = True
        recommendations["background-jobs"]["reason"] = "Background job tools in use"

    # Apply recommendations
    enabled_categories = []
    disabled_categories = []
    reasons = {}

    for cat_name in config.get("categories", {}):
        if cat_name not in recommendations:
            # Unknown category, keep current state
            continue

        rec = recommendations[cat_name]
        enabled = rec["enable"]
        reasons[cat_name] = rec["reason"]

        if enabled:
            enabled_categories.append(cat_name)
        else:
            disabled_categories.append(cat_name)

        # Update config
        config["categories"][cat_name]["enabled"] = enabled

        # Update tools in category
        for tool_name, tool_info in config.get("tools", {}).items():
            if tool_info.get("category") == cat_name:
                tool_info["enabled"] = enabled

    # Clear preset since this is custom
    config["active_preset"] = "auto"
    config["auto_config"] = {
        "applied_at": datetime.now().isoformat(),
        "sessions_analyzed": sessions,
        "total_calls_analyzed": total_calls,
        "context": {
            "has_careers": context["has_careers"],
            "has_agents": context["has_agents"],
            "has_testing": context["has_testing"],
        },
    }

    save_mcp_tools_config(config)

    # Calculate confidence
    if sessions < 5:
        confidence = "low"
        confidence_reason = "Need more usage data (< 5 sessions)"
    elif sessions < 20:
        confidence = "medium"
        confidence_reason = f"Based on {sessions} sessions"
    else:
        confidence = "high"
        confidence_reason = f"Based on {sessions} sessions and {total_calls} tool calls"

    return {
        "success": True,
        "enabled_categories": enabled_categories,
        "disabled_categories": disabled_categories,
        "reasons": reasons,
        "tools_enabled": sum(1 for t in config.get("tools", {}).values() if t.get("enabled", False)),
        "tools_total": len(config.get("tools", {})),
        "confidence": confidence,
        "confidence_reason": confidence_reason,
        "metrics_summary": {
            "sessions": sessions,
            "total_calls": total_calls,
            "top_tools": sorted(tool_calls.items(), key=lambda x: x[1], reverse=True)[:5] if tool_calls else [],
        },
        "context": context,
    }

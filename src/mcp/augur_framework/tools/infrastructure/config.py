"""
Configuration and Features tool implementations.

These tools handle feature flags, batch presets, chat sessions, and system caching.
"""

# TODO_CLEANUP: This file is 848 lines — consider splitting into smaller modules

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.logging import get_entity_logger

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_entity_logger("mcp")

# Project root for path resolution
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def _resolve_data_dir() -> Path:
    """Resolve the project root directory."""
    from src.mcp.augur_shared.config import get_project_root

    return get_project_root()


def _resolve_repo_config_dir() -> Path:
    """Resolve the canonical repo config directory."""
    try:
        from src.config.paths import get_config_dir

        return get_config_dir()
    except ImportError:
        return _resolve_data_dir() / "config"


def _missing_config_payload(kind: str, searched_paths: list[Path]) -> dict[str, Any]:
    """Build a consistent explicit error for missing MCP config sources."""
    return {
        "success": False,
        "error": f"{kind} config not found",
        "searched_paths": [str(path) for path in searched_paths],
    }


def _get_features_payload() -> dict[str, Any]:
    """Load feature flag data from the canonical config directory."""
    config_dir = _resolve_repo_config_dir()
    feature_files = ["factory.yaml", "vertical.yaml", "services.yaml", "incubator.yaml"]
    feature_dirs = [
        config_dir / "operations" / "features",
        config_dir / "features",
    ]
    features_dir = next((path for path in feature_dirs if path.exists()), None)
    if features_dir is None:
        return _missing_config_payload("Feature flags", feature_dirs)

    data: dict[str, list[Any]] = {file.replace(".yaml", ""): [] for file in feature_files}
    missing_files: list[Path] = []

    for file in feature_files:
        file_path = features_dir / file
        if not file_path.exists():
            missing_files.append(file_path)
            continue

        with open(file_path, encoding="utf-8") as handle:
            parsed = yaml.safe_load(handle) or {}
        data[file.replace(".yaml", "")] = parsed.get("epics", []) if isinstance(parsed, dict) else []

    if missing_files:
        return {
            "success": False,
            "error": "Feature flag config is incomplete",
            "source": str(features_dir),
            "missing_files": [str(path) for path in missing_files],
            "data": data,
        }

    return {
        "success": True,
        "source": str(features_dir),
        "data": data,
    }


def _get_batch_presets_payload() -> dict[str, Any]:
    """Load batch preset data from the canonical config directory."""
    config_dir = _resolve_repo_config_dir()
    preset_files = [
        config_dir / "batch_presets.yaml",
        config_dir / "presets" / "batch_presets.yaml",
    ]
    presets_file = next((path for path in preset_files if path.exists()), None)
    if presets_file is None:
        return _missing_config_payload("Batch presets", preset_files)

    with open(presets_file, encoding="utf-8") as handle:
        presets = yaml.safe_load(handle) or {}

    if not isinstance(presets, dict):
        return {
            "success": False,
            "error": "Batch presets config must be a mapping",
            "source": str(presets_file),
        }

    payload = dict(presets)
    payload.setdefault("presets", [])
    payload["success"] = True
    payload["source"] = str(presets_file)
    return payload


def _resolve_chat_session_file() -> Path:
    from src.mcp.augur_shared.config import get_runtime_dir

    return get_runtime_dir() / "temp" / "chat_session.json"


# =============================================================================
# Tool Registration
# =============================================================================


def register_config_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """
    Register Configuration and Features tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
    """

    @mcp.tool(
        name="get-features",
        annotations=tool_annotations(
            {
                "title": "Get Feature Flags",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_features_tool() -> str:
        """Get feature flags configuration.

        Returns:
            str: JSON with feature flag data or an explicit config-missing error
        """
        metrics.track_tool("get_features")

        try:
            payload = _get_features_payload()
            if not payload.get("success"):
                logger.warning(f"get-features: {payload['error']}")
            return json.dumps(payload, indent=2)

        except Exception as e:
            logger.error(f"Failed to get features: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="get-chat-session",
        annotations=tool_annotations(
            {
                "title": "Get Chat Session",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_chat_session_tool() -> str:
        """Get current chat session state.

        Returns:
            str: JSON with chat session data
        """
        metrics.track_tool("get_chat_session")

        try:
            session_file = _resolve_chat_session_file()

            if not session_file.exists():
                # Return default session
                return json.dumps({"isActive": False, "mode": "ide", "status": "idle"}, indent=2)

            with open(session_file) as f:
                session = json.load(f)

            return json.dumps(session, indent=2)

        except Exception as e:
            logger.error(f"Failed to get chat session: {e}")
            return json.dumps({"isActive": False, "mode": "ide", "status": "idle"})

    @mcp.tool(
        name="update-chat-session",
        annotations=tool_annotations(
            {
                "title": "Update Chat Session",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def update_chat_session_tool(
        is_active: bool | None = None,
        mode: str | None = None,
        status: str | None = None,
        action_id: str | None = None,
        context: dict[str, Any] | str | None = None,
        # Dashboard camelCase aliases
        isActive: bool | None = None,
        actionId: str | None = None,
    ) -> str:
        """Update chat session state.

        Args:
            is_active: Whether chat is active (alias: isActive)
            mode: Chat mode (ide, remote, local, auto)
            status: Chat status (idle, waiting_for_ide, processing)
            action_id: Action ID (alias: actionId)
            context: Context data as JSON string or dict

        Returns:
            str: JSON with updated session
        """
        metrics.track_tool("update_chat_session")

        # Resolve camelCase dashboard aliases
        if is_active is None and isActive is not None:
            is_active = isActive
        if action_id is None and actionId is not None:
            action_id = actionId

        try:
            session_file = _resolve_chat_session_file()

            # Get current session
            if session_file.exists():
                with open(session_file) as f:
                    current = json.load(f)
            else:
                current = {"isActive": False, "mode": "ide", "status": "idle"}

            # Apply updates
            if is_active is not None:
                current["isActive"] = is_active
            if mode is not None:
                current["mode"] = mode
            if status is not None:
                current["status"] = status
            if action_id is not None:
                current["actionId"] = action_id
            if context is not None:
                if isinstance(context, dict):
                    current["context"] = context
                else:
                    try:
                        current["context"] = json.loads(context)
                    except (json.JSONDecodeError, TypeError):
                        current["context"] = context

            # Ensure directory exists
            session_file.parent.mkdir(parents=True, exist_ok=True)

            # Write updated session
            with open(session_file, "w") as f:
                json.dump(current, f, indent=2)

            return json.dumps(current, indent=2)

        except Exception as e:
            logger.error(f"Failed to update chat session: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="clear-system-cache",
        annotations=tool_annotations(
            {
                "title": "Clear System Cache",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def clear_system_cache_tool() -> str:
        """Clear Next.js system cache.

        Returns:
            str: JSON with success status
        """
        metrics.track_tool("clear_system_cache")

        try:
            # Note: This is a marker tool. Actual cache clearing happens in Next.js
            # via revalidatePath which can't be called from Python

            logger.info("System cache clear requested via MCP")

            return json.dumps(
                {
                    "success": True,
                    "message": "System cache clear requested",
                    "timestamp": datetime.now().isoformat(),
                    "note": "Cache revalidation will be triggered by Next.js route",
                },
                indent=2,
            )

        except Exception as e:
            logger.error(f"Failed to clear system cache: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="get-intelligence-stats",
        annotations=tool_annotations(
            {
                "title": "Get Intelligence Stats",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_intelligence_stats_tool() -> str:
        """Get brain intelligence usage statistics.

        Returns:
            str: JSON with LLM usage stats
        """
        metrics.track_tool("get_intelligence_stats")

        try:
            from src.mcp.augur_shared.config import get_project_root

            project_root = get_project_root()
            stats_file = project_root / "factory" / "devops" / "llm_usage.json"

            if not stats_file.exists():
                return json.dumps({"total_requests": 0, "total_cost": 0, "provider_stats": {}}, indent=2)

            with open(stats_file) as f:
                stats = json.load(f)

            # Patch: Calculate total_requests if missing or 0 but requests exist
            if (not stats.get("total_requests") or stats.get("total_requests") == 0) and isinstance(
                stats.get("requests"), list
            ):
                stats["total_requests"] = len(stats["requests"])

            return json.dumps(stats, indent=2)

        except Exception as e:
            logger.error(f"Failed to get intelligence stats: {e}")
            return json.dumps({"error": str(e), "total_requests": 0, "total_cost": 0})

    @mcp.tool(
        name="get-usage-stats",
        annotations=tool_annotations(
            {
                "title": "Get Usage Statistics",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_usage_stats_tool(days: int = 7) -> str:
        """Get usage statistics and system health.

        Returns today's token usage, this week's total, per-model breakdown,
        and budget status (OK/WARNING/CRITICAL).

        Args:
            days: Number of days to include in the report (default: 7)

        Returns:
            str: JSON with usage stats, cost breakdown, and budget status
        """
        metrics.track_tool("get_usage_stats")

        try:
            from src.mcp.augur_shared.config import get_project_root

            project_root = get_project_root()
            stats_file = project_root / "factory" / "devops" / "llm_usage.json"

            today = datetime.now().strftime("%Y-%m-%d")
            week_start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            if not stats_file.exists():
                return json.dumps(
                    {
                        "today": {"requests": 0, "tokens": 0, "cost": 0.0},
                        "period": {"days": days, "requests": 0, "tokens": 0, "cost": 0.0},
                        "model_breakdown": {},
                        "provider_breakdown": {},
                        "budget_status": "OK",
                        "budget_message": "No usage data found",
                    },
                    indent=2,
                )

            with open(stats_file) as f:
                usage_data = json.load(f)

            daily_stats = usage_data.get("daily_stats", {})
            provider_stats = usage_data.get("provider_stats", {})

            # Today's stats
            today_data = daily_stats.get(today, {})
            today_summary = {
                "requests": today_data.get("requests", 0),
                "tokens": today_data.get("tokens", 0),
                "cost": round(today_data.get("cost", 0.0), 4),
                "errors": today_data.get("errors", 0),
            }

            # Period stats (last N days)
            period_requests = 0
            period_tokens = 0
            period_cost = 0.0
            period_errors = 0
            daily_breakdown = []

            for date_key in sorted(daily_stats.keys(), reverse=True):
                if date_key >= week_start:
                    day = daily_stats[date_key]
                    period_requests += day.get("requests", 0)
                    period_tokens += day.get("tokens", 0)
                    period_cost += day.get("cost", 0.0)
                    period_errors += day.get("errors", 0)
                    daily_breakdown.append(
                        {
                            "date": date_key,
                            "requests": day.get("requests", 0),
                            "tokens": day.get("tokens", 0),
                            "cost": round(day.get("cost", 0.0), 4),
                        }
                    )

            period_summary = {
                "days": days,
                "requests": period_requests,
                "tokens": period_tokens,
                "cost": round(period_cost, 4),
                "errors": period_errors,
            }

            # Per-model breakdown from provider stats
            model_breakdown = {}
            provider_breakdown = {}
            for prov_name, prov_data in provider_stats.items():
                provider_breakdown[prov_name] = {
                    "requests": prov_data.get("requests", 0),
                    "tokens": prov_data.get("tokens", 0),
                    "cost": round(prov_data.get("cost", 0.0), 4),
                }
                for model_name, model_data in prov_data.get("models", {}).items():
                    key = f"{prov_name}/{model_name}"
                    model_breakdown[key] = {
                        "requests": model_data.get("requests", 0),
                        "tokens": model_data.get("tokens", 0),
                        "cost": round(model_data.get("cost", 0.0), 4),
                    }

            # Budget status based on daily cost thresholds
            # Thresholds: OK < $5/day, WARNING < $15/day, CRITICAL >= $15/day
            daily_avg_cost = period_cost / max(len(daily_breakdown), 1)
            total_cost = usage_data.get("total_cost", 0.0)

            if daily_avg_cost >= 15.0:
                budget_status = "CRITICAL"
                budget_message = f"High spend: ${daily_avg_cost:.2f}/day avg over {days}d"
            elif daily_avg_cost >= 5.0:
                budget_status = "WARNING"
                budget_message = f"Moderate spend: ${daily_avg_cost:.2f}/day avg over {days}d"
            else:
                budget_status = "OK"
                budget_message = f"Normal spend: ${daily_avg_cost:.2f}/day avg over {days}d"

            result = {
                "today": today_summary,
                "period": period_summary,
                "daily_breakdown": daily_breakdown,
                "model_breakdown": model_breakdown,
                "provider_breakdown": provider_breakdown,
                "all_time": {
                    "total_cost": round(total_cost, 4),
                    "total_tokens": usage_data.get("total_tokens", 0),
                },
                "budget_status": budget_status,
                "budget_message": budget_message,
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}")
            return json.dumps({"error": str(e), "budget_status": "UNKNOWN"})

    @mcp.tool(
        name="export-skill-plugin",
        annotations=tool_annotations(
            {
                "title": "Export Skill Plugin",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def export_skill_plugin_tool(
        skill_name: str,
        bundle: str | None = None,
        target: str = "claude-code",
        output_dir: str | None = None,
    ) -> str:
        """Export an Augur skill as an external plugin package.

        Supports all bundles (crew, services, apps, orchestrator) and
        multiple export targets (claude-code, mcp-server, python-package, tarball).

        Args:
            skill_name: Name of the skill to export (e.g., "developer", "career", "knowledge")
            bundle: Optional bundle name (crew, services, apps, orchestrator). Auto-detects if omitted.
            target: Export format: claude-code, mcp-server, python-package, or tarball (default: claude-code)
            output_dir: Required output directory for claude-code/mcp-server/python-package targets (tarball uses project root)

        Returns:
            str: JSON with export result including plugin path and file list
        """
        metrics.track_tool("export_skill_plugin")

        try:
            import asyncio
            import sys
            from pathlib import Path

            valid_targets = {"claude-code", "mcp-server", "python-package", "tarball"}
            if target not in valid_targets:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Invalid target '{target}'. Must be one of: {sorted(valid_targets)}",
                    },
                    indent=2,
                )

            # ADR-Track-3a: replace hardcoded `valid_bundles` enumeration with
            # dynamic skill discovery via augur_shared.skill_registry. Project
            # skills live under project-brain/capabilities/skills, so the legacy
            # plugins/<bundle>/skills/ path is irrelevant; the bundle parameter
            # is now a no-op (kept for backward compat with external callers).
            from src.config.paths import get_skill_root

            # Resolve paths
            from src.mcp.augur_shared.config import get_project_root as get_mcp_project_root
            from src.mcp.augur_shared.skill_registry import (
                all_known_skills,
                is_known_skill,
            )

            actual_root = get_mcp_project_root()
            if actual_root is None:
                from src.config.paths import get_project_root

                actual_root = get_project_root()

            # Resolve skill path via managed shared/private skill roots.
            try:
                skill_path = get_skill_root(skill_name)
            except ValueError:
                if bundle and not is_known_skill(skill_name):
                    return json.dumps(
                        {
                            "success": False,
                            "error": f"Skill '{skill_name}' not found in bundle '{bundle}' (or any registered bundle).",
                            "available_skills": sorted(all_known_skills()),
                        },
                        indent=2,
                    )
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Skill '{skill_name}' not found in managed skill roots",
                        "available_skills": sorted(all_known_skills()),
                    },
                    indent=2,
                )

            if output_dir:
                out = Path(output_dir)
            elif target == "tarball":
                out = actual_root
            else:
                return json.dumps(
                    {
                        "success": False,
                        "error": "output_dir is required for claude-code, mcp-server, and python-package targets",
                    },
                    indent=2,
                )

            # Import and run exporter
            exporter_path = actual_root / "apps" / "dashboard" / "scripts" / "skill-scripts" / "skill_exporter.py"
            if not exporter_path.exists():
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Exporter script not found at {exporter_path}",
                    },
                    indent=2,
                )

            scripts_dir = str(exporter_path.parent)
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)

            from skill_exporter import export_skill

            plugin_path = await asyncio.to_thread(export_skill, skill_path, out, target)

            # List generated files (for tarball, the result is a single .tar.gz file)
            if plugin_path.is_file():
                files = [plugin_path.name]
            else:
                files = sorted(str(f.relative_to(plugin_path)) for f in plugin_path.rglob("*") if f.is_file())

            return json.dumps(
                {
                    "success": True,
                    "skill_name": skill_name,
                    "target": target,
                    "plugin_path": str(plugin_path),
                    "files": files,
                },
                indent=2,
            )

        except Exception as e:
            logger.error(f"Failed to export skill plugin: {e}")
            return json.dumps({"success": False, "error": str(e)})


__all__ = ["register_config_tools"]

"""
Workflow tool implementations.

These tools handle focused tools, audit logging, and skill generation.
"""

import asyncio
import json
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field
from src.mcp.augur_shared.annotations import tool_annotations
from src.mcp.augur_shared.compat import get_mcp_controller, get_project_root
from src.mcp.augur_shared.config import get_runtime_dir
from src.mcp.augur_shared.logging import get_entity_logger
from src.mcp.augur_shared.safe_subprocess import safe_run as subprocess_run  # nosec B404

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_entity_logger("mcp")

# Project root for path resolution - use compat layer
_project_root = get_project_root()
# workflow.py -> infrastructure -> augur_mcp -> mcp -> src -> PROJECT_ROOT
PROJECT_ROOT = _project_root if _project_root else Path(__file__).parent.parent.parent.parent.parent


def _run_command(command: list[str], **kwargs: Any):
    """Run subprocess command using argv invocation."""
    return subprocess_run(command, **kwargs)  # nosec B603


# =============================================================================
# Pydantic Input Models
# =============================================================================


class EmitExecutionEventInput(BaseModel):
    """Input for emit-execution-event MCP tool."""

    model_config = ConfigDict(extra="forbid")
    command: str = Field(..., description="Slash command name (without leading /)")
    outcome: str = Field("success", description="Execution outcome: success, failure, partial_success")
    duration_ms: int = Field(0, description="Execution duration in milliseconds")
    learnings: list[str] = Field(default_factory=list, description="Learnings from this execution")
    phases: list[dict] = Field(default_factory=list, description="Execution phases with name and status")
    tools_called: list[dict] = Field(
        default_factory=list,
        description="Tools invoked during execution, each with 'name' and 'count'",
    )
    errors: list[dict] = Field(
        default_factory=list,
        description="Errors encountered, each with 'phase', 'message', and 'recoverable' (bool)",
    )
    files_changed: list[dict] = Field(
        default_factory=list,
        description="Files touched, each with 'path' and 'action' (created/edited/deleted)",
    )
    assessment: dict = Field(
        default_factory=dict,
        description="Structured self-assessment with keys: what_worked, what_was_slow, what_to_improve, confidence (high/medium/low)",
    )


class GetFocusedToolsInput(BaseModel):
    """Input for get-focused-tools MCP tool."""

    model_config = ConfigDict(extra="forbid")
    task: str | None = Field(None, description="Task description to optimize tool selection for")
    preset: str | None = Field(
        None, description="Preset configuration: minimal, standard, full, development, production"
    )


class QueryAuditLogInput(BaseModel):
    """Input for query-audit-log MCP tool."""

    model_config = ConfigDict(extra="forbid")
    action: str = Field("query", description="Action: query or log")
    # Query parameters
    start_date: str | None = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: str | None = Field(None, description="End date (YYYY-MM-DD)")
    filter_action: str | None = Field(None, description="Filter by action type")
    user: str | None = Field(None, description="Filter by user")
    limit: int = Field(100, description="Maximum results")
    # Log parameters
    log_action: str | None = Field(None, description="Action to log")
    resource: str | None = Field(None, description="Resource affected")
    details: str | None = Field(None, description="Additional details")


class GenerateSkillInput(BaseModel):
    """Input for generate-skill MCP tool."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="Skill name (will be slugified)")
    description: str | None = Field(None, description="Skill description")
    layer: str = Field("vertical", description="Layer: factory, horizontal, or vertical")
    patterns: list[str] = Field(default_factory=list, description="Skill patterns: inbox, database, dashboard, etc.")
    source: str = Field("create", description="Source type: create, import, documents, unified")


# =============================================================================
# Tool Registration
# =============================================================================


def register_workflow_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
) -> None:
    """
    Register Workflow tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
    """

    @mcp.tool(
        name="emit-execution-event",
        annotations=tool_annotations(
            {
                "title": "Emit Execution Event",
                "readOnlyHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def emit_execution_event(params: EmitExecutionEventInput) -> str:
        """Record a command execution event for adaptive loop tracking.

        Writes to both the post-exec queue (for immediate loop triggers)
        and the execution log directory (for scanner reads).
        """
        try:
            runtime_dir = get_runtime_dir()
            ts = datetime.now().isoformat()

            event = {
                "command": params.command,
                "outcome": params.outcome,
                "duration_ms": params.duration_ms,
                "timestamp": ts,
                "learnings": params.learnings,
                "phases": params.phases,
                "tools_called": params.tools_called,
                "errors": params.errors,
                "files_changed": params.files_changed,
                "assessment": params.assessment,
            }

            # Write to post_exec_queue.jsonl
            queue_file = runtime_dir / "adaptive" / "post_exec_queue.jsonl"
            queue_file.parent.mkdir(parents=True, exist_ok=True)
            with open(queue_file, "a") as f:
                f.write(json.dumps(event) + "\n")

            # Write execution log for command-evolution scanner
            log_dir = runtime_dir / "command-evolution" / params.command / "executions"
            log_dir.mkdir(parents=True, exist_ok=True)
            ts_safe = ts.replace(":", "-")[:19]
            log_path = log_dir / f"{ts_safe}.json"
            log_path.write_text(
                json.dumps(
                    {
                        "command": params.command,
                        "outcome": params.outcome,
                        "started_at": ts,
                        "completed_at": ts,
                        "duration_ms": params.duration_ms,
                        "phases": params.phases,
                        "learnings": params.learnings,
                        "tools_called": params.tools_called,
                        "errors": params.errors,
                        "files_changed": params.files_changed,
                        "assessment": params.assessment,
                        "metrics": {"duration_seconds": params.duration_ms / 1000},
                    },
                    indent=2,
                )
            )

            return json.dumps({"success": True, "command": params.command, "log_path": str(log_path)})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool(
        name="get-focused-tools",
        annotations=tool_annotations(
            {
                "title": "Get Focused MCP Tools",
                "readOnlyHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def get_focused_tools(
        # MCP tool no-arg input model default is introspected by the SDK.
        params: GetFocusedToolsInput = GetFocusedToolsInput(),  # noqa: B008
    ) -> str:
        """Get context-aware MCP tool selection based on task or preset.

        Returns which tools should be enabled/disabled for optimal performance.
        Useful for agents to optimize their tool usage per task.
        """
        try:
            controller = get_mcp_controller()

            if controller is None:
                # Fallback if controller not available
                return json.dumps(
                    {
                        "enabled_tools": ["search-documents", "list-skills", "execute-chain"],
                        "disabled_tools": [],
                        "reasoning": "Default configuration (ai kernel not available)",
                        "enabled_count": 3,
                        "disabled_count": 0,
                    },
                    indent=2,
                )

            if params.preset:
                config = controller.get_preset_config(params.preset)
            else:
                config = controller.get_focused_config(task_description=params.task)

            return json.dumps(config.to_dict(), indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    @mcp.tool(
        name="query-audit-log",
        annotations=tool_annotations(
            {
                "title": "Query Audit Log",
                "readOnlyHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def query_audit_log(
        action: str = "query",
        start_date: str | None = None,
        end_date: str | None = None,
        filter_action: str | None = None,
        user: str | None = None,
        limit: int = 100,
        log_action: str | None = None,
        resource: str | None = None,
        details: str | None = None,
    ) -> str:
        """Query or log security audit events.

        Allows agents to audit their own actions and query historical logs
        for compliance and debugging purposes.
        """
        params = QueryAuditLogInput(
            action=action,
            start_date=start_date,
            end_date=end_date,
            filter_action=filter_action,
            user=user,
            limit=limit,
            log_action=log_action,
            resource=resource,
            details=details,
        )
        try:
            # Get data directory from centralized config
            from src.mcp.augur_shared.config import get_project_root

            project_root = get_project_root()
            audit_dir = project_root / "security" / "audit"
            audit_dir.mkdir(parents=True, exist_ok=True)

            if params.action == "log":
                if not params.log_action:
                    return json.dumps({"error": "log_action is required for logging"}, indent=2)

                # Create audit entry
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "action": params.log_action,
                    "user": params.user or "system",
                    "resource": params.resource,
                    "details": params.details,
                }

                # Append to daily log file
                date_str = datetime.now().strftime("%Y-%m-%d")
                log_file = audit_dir / f"audit-{date_str}.yaml"

                existing: list[dict[str, Any]] = []
                if log_file.exists():
                    try:
                        existing = yaml.safe_load(log_file.read_text()) or []
                    except Exception:
                        existing = []

                existing.append(entry)
                log_file.write_text(yaml.dump(existing, default_flow_style=False))

                return json.dumps({"success": True, "logged": entry}, indent=2)

            else:  # query
                all_entries: list[dict[str, Any]] = []

                # Read all audit files
                for log_file in sorted(audit_dir.glob("audit-*.yaml"), reverse=True):
                    entries: list[dict[str, Any]] = []
                    try:
                        loaded = yaml.safe_load(log_file.read_text()) or []
                        if isinstance(loaded, list):
                            entries = loaded
                        all_entries.extend(entries)
                    except Exception as exc:
                        logger.debug("Failed loading audit log %s: %s", log_file, exc)

                    if len(all_entries) >= params.limit * 2:  # Get extra for filtering
                        break

                # Apply filters
                filtered = all_entries

                if params.start_date:
                    filtered = [e for e in filtered if e.get("timestamp", "") >= params.start_date]
                if params.end_date:
                    filtered = [e for e in filtered if e.get("timestamp", "")[:10] <= params.end_date]
                if params.filter_action:
                    filtered = [e for e in filtered if e.get("action") == params.filter_action]
                if params.user:
                    filtered = [e for e in filtered if e.get("user") == params.user]

                # Limit results
                filtered = filtered[: params.limit]

                return json.dumps(
                    {
                        "count": len(filtered),
                        "logs": filtered,
                    },
                    indent=2,
                )

        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    @mcp.tool(
        name="generate-skill",
        annotations=tool_annotations(
            {
                "title": "Generate New Skill",
                "readOnlyHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def generate_skill(params: GenerateSkillInput) -> str:
        """Generate a new Augur skill with all required components.

        Creates skill structure, SKILL.md, scripts, tests, and dashboard UI.
        Enables agents to create new skills autonomously.
        """
        try:
            # Slugify name
            slug = params.name.lower().strip().replace(" ", "-").replace("_", "-")
            slug = "".join(c for c in slug if c.isalnum() or c == "-")

            # Create config for generator
            config = {
                "source": params.source,
                "name": slug,
                "slug": slug,
                "title": params.name.replace("-", " ").title(),
                "description": params.description or f"A skill for {params.name}",
                "layer": params.layer,
                "patterns": params.patterns or ["inbox", "database"],
            }

            # Write temp config
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(config, f, indent=2)
                config_path = f.name

            try:
                # Run generator script
                script_path = (
                    PROJECT_ROOT
                    / "plugins"
                    / "ai"
                    / "skills"
                    / "mcp-app-factory"
                    / "scripts"
                    / "skill_generation"
                    / "unified_generator.py"
                )

                if script_path.exists():
                    result = await asyncio.to_thread(
                        _run_command,
                        ["python3", str(script_path), config_path],
                        capture_output=True,
                        text=True,
                        timeout=60,
                        cwd=str(PROJECT_ROOT),
                    )

                    if result.returncode == 0:
                        try:
                            output = json.loads(result.stdout)
                            return json.dumps(output, indent=2)
                        except Exception as exc:
                            logger.debug("Failed to parse generator JSON output: %s", exc)

                # Fallback: create basic structure
                skill_dir = PROJECT_ROOT / "plugins" / params.layer / "skills" / slug
                skill_dir.mkdir(parents=True, exist_ok=True)

                # Create SKILL.md
                skill_md = skill_dir / "SKILL.md"
                skill_md.write_text(f"""# {params.name.replace("-", " ").title()}

{params.description or f"A skill for {params.name}"}

## Trigger Phrases
- "{slug}"
- "help with {slug}"

## Patterns
{chr(10).join(f"- {p}" for p in (params.patterns or ["inbox"]))}

## Layer
{params.layer}
""")

                # Create scripts directory
                scripts_dir = skill_dir / "scripts"
                scripts_dir.mkdir(exist_ok=True)
                (scripts_dir / "__init__.py").write_text("")

                return json.dumps(
                    {
                        "success": True,
                        "skill": {
                            "slug": slug,
                            "title": params.name.replace("-", " ").title(),
                            "layer": params.layer,
                            "path": skill_dir.relative_to(PROJECT_ROOT).as_posix(),
                        },
                        "generated": {
                            "structure": True,
                            "skill_md": True,
                            "scripts": True,
                        },
                        "next_steps": [
                            f"View skill at plugins/{params.layer}/{slug}",
                            "Customize SKILL.md",
                            "Add domain-specific scripts",
                        ],
                    },
                    indent=2,
                )

            finally:
                # Clean up temp file
                Path(config_path).unlink(missing_ok=True)

        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)


__all__ = ["register_workflow_tools"]

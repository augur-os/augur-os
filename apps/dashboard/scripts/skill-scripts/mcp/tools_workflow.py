"""Workflow/generation tools for mcp-app-factory.

Tools: workflow-start, workflow-status, workflow-resume,
       workflow-answer, workflow-advance, workflow-abort, workflow-list
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from ._helpers import (
    logger,
    tool_annotations,
    get_workflow_engine,
)


# ============================================================================
# Implementation Functions
# ============================================================================


def workflow_start_impl(
    mode: str = "new",
    skill_name: str = "",
    # Track 3b: bundle is the plugin BUNDLE id (lifestyle/ai/dev/...),
    # not a hub id from config/system/hubs.yaml.
    bundle: str = "lifestyle",
    profile: str = "standard",
    source_path: Optional[str] = None,
    auto_mode: bool = False,
) -> dict:
    """Start a new workflow for plugin generation or refactoring.

    Args:
        mode: "new" for new plugin, "refactor" for existing plugin
        skill_name: Name of the skill (required for new mode)
        bundle: Target bundle (core, career, growth, finance, health, productivity, lifestyle, ai, admin, observe, dev, etc.)
        profile: Target profile (minimal, standard, full)
        source_path: Path to existing skill (required for refactor mode)
        auto_mode: If True, use default answers for all questions (for CI/batch)

    Returns:
        Workflow state including workflow_id and current stage
    """
    logger.info("Starting workflow", extra={"mode": mode, "skill_name": skill_name})

    try:
        engine = get_workflow_engine()
        # Engine returns a dict directly
        result = engine.start_workflow(
            mode=mode,
            skill_name=skill_name,
            bundle=bundle,
            target_profile=profile,
            source_path=source_path,
            auto_mode=auto_mode,
        )
        return result

    except Exception as e:
        logger.error("Failed to start workflow", exc_info=True)
        return {"success": False, "error": str(e)}


def workflow_status_impl(workflow_id: str) -> dict:
    """Get the current status of a workflow.

    Args:
        workflow_id: The workflow identifier

    Returns:
        Complete workflow state including progress and pending questions
    """
    logger.info("Getting workflow status", extra={"workflow_id": workflow_id})

    try:
        engine = get_workflow_engine()
        return engine.get_status(workflow_id)

    except Exception as e:
        logger.error("Failed to get workflow status", exc_info=True)
        return {"success": False, "error": str(e)}


def workflow_resume_impl(workflow_id: str) -> dict:
    """Resume an interrupted workflow from its last checkpoint.

    Args:
        workflow_id: The workflow identifier

    Returns:
        Updated workflow state after resuming
    """
    logger.info("Resuming workflow", extra={"workflow_id": workflow_id})

    try:
        engine = get_workflow_engine()
        return engine.resume_workflow(workflow_id)

    except Exception as e:
        logger.error("Failed to resume workflow", exc_info=True)
        return {"success": False, "error": str(e)}


def workflow_answer_impl(workflow_id: str, answers: dict) -> dict:
    """Submit answers to the current stage's questions.

    Args:
        workflow_id: The workflow identifier
        answers: Dictionary mapping question_id to answer

    Returns:
        Updated workflow state after processing answers
    """
    logger.info("Submitting workflow answers", extra={"workflow_id": workflow_id})

    try:
        engine = get_workflow_engine()
        return engine.submit_answers(workflow_id, answers)

    except Exception as e:
        logger.error("Failed to submit workflow answers", exc_info=True)
        return {"success": False, "error": str(e)}


def workflow_advance_impl(workflow_id: str) -> dict:
    """Advance the workflow to the next phase/stage.

    This runs the workflow engine to process the current state
    and advance to the next phase or stage.

    Args:
        workflow_id: The workflow identifier

    Returns:
        Updated workflow state after advancing
    """
    logger.info("Advancing workflow", extra={"workflow_id": workflow_id})

    try:
        engine = get_workflow_engine()
        return engine.advance_workflow(workflow_id)

    except Exception as e:
        logger.error("Failed to advance workflow", exc_info=True)
        return {"success": False, "error": str(e)}


def workflow_abort_impl(workflow_id: str, cleanup: bool = False) -> dict:
    """Abort a running workflow.

    Args:
        workflow_id: The workflow identifier
        cleanup: If True, also delete generated files

    Returns:
        Confirmation of abort
    """
    logger.info("Aborting workflow", extra={"workflow_id": workflow_id})

    try:
        engine = get_workflow_engine()
        return engine.abort_workflow(workflow_id, cleanup)

    except Exception as e:
        logger.error("Failed to abort workflow", exc_info=True)
        return {"success": False, "error": str(e)}


def workflow_list_impl(status_filter: Optional[str] = None) -> dict:
    """List all workflows with optional status filter.

    Args:
        status_filter: Filter by status (active, completed, failed)

    Returns:
        List of workflow summaries
    """
    logger.info("Listing workflows", extra={"filter": status_filter})

    try:
        engine = get_workflow_engine()
        return engine.list_workflows(status_filter)

    except Exception as e:
        logger.error("Failed to list workflows", exc_info=True)
        return {"success": False, "error": str(e)}


# ============================================================================
# Tool Registration
# ============================================================================


def register_workflow_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register workflow/generation tools with the MCP server."""

    @mcp.tool(
        name="workflow-start",
        annotations=tool_annotations(
            {
                "title": "Start Workflow",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def workflow_start_tool(
        mode: str = "new",
        skill_name: str = "",
        bundle: str = "lifestyle",
        profile: str = "standard",
        source_path: Optional[str] = None,
        auto_mode: bool = False,
    ) -> str:
        """Start a new 5-stage workflow for plugin generation or refactoring.

        The workflow progresses through 5 stages:
        1. Baseline - Generate/import Layer 1 compliant SKILL.md
        2. Hardening - Add triggers, tiers, safety constraints
        3. Data Structures - Define schemas and storage patterns
        4. MCP/Actions - Define tools and dashboard actions
        5. UI Generation - Generate dashboard components

        Each stage follows: Plan -> Execute -> Test -> Validate -> Questions -> Complete

        Args:
            mode: "new" for new plugin, "refactor" for existing plugin
            skill_name: Name of the skill (required for new mode)
            bundle: Target bundle (core, career, growth, finance, health, productivity, lifestyle, ai, admin, observe, dev, etc.)
            profile: Target profile (minimal, standard, full)
            source_path: Path to existing skill (required for refactor mode)
            auto_mode: If True, use defaults for all questions (for CI/batch)

        Returns:
            str: JSON with workflow_id and initial state
        """
        metrics.track_tool("workflow_start", skill="mcp-app-factory")
        result = workflow_start_impl(mode, skill_name, bundle, profile, source_path, auto_mode)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="workflow-status",
        annotations=tool_annotations(
            {
                "title": "Workflow Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def workflow_status_tool(workflow_id: str) -> str:
        """Get the current status of a workflow.

        Returns complete state including:
        - Current stage and phase
        - Progress percentage
        - Pending questions (if waiting for input)
        - Stage outputs completed so far

        Args:
            workflow_id: The workflow identifier from workflow-start

        Returns:
            str: JSON with complete workflow state
        """
        metrics.track_tool("workflow_status", skill="mcp-app-factory")
        result = workflow_status_impl(workflow_id)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="workflow-resume",
        annotations=tool_annotations(
            {
                "title": "Resume Workflow",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def workflow_resume_tool(workflow_id: str) -> str:
        """Resume an interrupted workflow from its last checkpoint.

        Workflows are checkpointed after each stage completion.
        Use this to continue after a session break or error recovery.

        Args:
            workflow_id: The workflow identifier

        Returns:
            str: JSON with updated workflow state
        """
        metrics.track_tool("workflow_resume", skill="mcp-app-factory")
        result = workflow_resume_impl(workflow_id)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="workflow-answer",
        annotations=tool_annotations(
            {
                "title": "Submit Workflow Answers",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def workflow_answer_tool(workflow_id: str, answers: str) -> str:
        """Submit answers to the current stage's questions.

        When a workflow is in the 'questions' phase, use this to provide
        answers and advance to the next stage.

        Args:
            workflow_id: The workflow identifier
            answers: JSON string mapping question_id to answer value
                    Example: '{"category": "personal", "triggers": "search recipes, find meal"}'

        Returns:
            str: JSON with updated workflow state after processing answers
        """
        metrics.track_tool("workflow_answer", skill="mcp-app-factory")
        try:
            answers_dict = json.loads(answers) if isinstance(answers, str) else answers
        except json.JSONDecodeError as e:
            return json.dumps({"success": False, "error": f"Invalid JSON in answers: {e}"})
        result = workflow_answer_impl(workflow_id, answers_dict)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="workflow-advance",
        annotations=tool_annotations(
            {
                "title": "Advance Workflow",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def workflow_advance_tool(workflow_id: str) -> str:
        """Advance the workflow to the next phase/stage.

        Runs the workflow engine to process the current state
        and move to the next phase or stage. Use after submitting
        answers or to continue processing.

        Args:
            workflow_id: The workflow identifier

        Returns:
            str: JSON with updated workflow state
        """
        metrics.track_tool("workflow_advance", skill="mcp-app-factory")
        result = workflow_advance_impl(workflow_id)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="workflow-abort",
        annotations=tool_annotations(
            {
                "title": "Abort Workflow",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def workflow_abort_tool(workflow_id: str, cleanup: bool = False) -> str:
        """Abort a running workflow.

        Stops the workflow and optionally cleans up generated files.

        Args:
            workflow_id: The workflow identifier
            cleanup: If True, also delete files generated by this workflow

        Returns:
            str: JSON confirming abort
        """
        metrics.track_tool("workflow_abort", skill="mcp-app-factory")
        result = workflow_abort_impl(workflow_id, cleanup)
        return json.dumps(result, indent=2)

    @mcp.tool(
        name="workflow-list",
        annotations=tool_annotations(
            {
                "title": "List Workflows",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def workflow_list_tool(status_filter: Optional[str] = None) -> str:
        """List all workflows with optional status filter.

        Args:
            status_filter: Filter by status - "active", "completed", or "failed"
                          Leave empty to list all workflows

        Returns:
            str: JSON with list of workflow summaries
        """
        metrics.track_tool("workflow_list", skill="mcp-app-factory")
        result = workflow_list_impl(status_filter)
        return json.dumps(result, indent=2)

"""
Action tool implementations.

These tools handle skill actions.
"""

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field
from src.mcp.augur_core.tools.core.helpers import list_modules
from src.mcp.augur_shared.annotations import tool_annotations

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


# =============================================================================
# Pydantic Input Models
# =============================================================================


class SkillActionInput(BaseModel):
    """Input for executing a skill action."""

    model_config = ConfigDict(str_strip_whitespace=True, extra='allow')

    skill_name: str = Field(..., description="Skill to use", min_length=1)
    action: str = Field(..., description="Action/command to execute", min_length=1)
    params: dict = Field(default_factory=dict, description="Action parameters")


# =============================================================================
# Helper Functions
# =============================================================================


def _coerce_action_params(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "model_dump"):
        try:
            return raw.model_dump()
        except Exception:
            return {}
    if hasattr(raw, "dict"):
        try:
            return raw.dict()
        except Exception:
            return {}
    try:
        return dict(raw)
    except Exception:
        return {}


# =============================================================================
# Shared Action Logic
# =============================================================================


def build_skill_action_result(params: SkillActionInput, resolve_skill_entry: Callable) -> dict[str, Any]:
    """Build the skill action result payload.

    This src/lib helper is used by both the MCP tool handler and local callers.
    """
    skill_entry = resolve_skill_entry(params.skill_name)
    if not skill_entry:
        return {"status": "error", "message": f"Skill '{params.skill_name}' not found"}

    skill_path = skill_entry.path

    # Check for executable script
    scripts_dir = skill_path / "scripts"
    action_script = scripts_dir / f"{params.action.replace(' ', '_')}.py"

    result: dict[str, Any] = {
        "skill": skill_entry.name,
        "action": params.action,
        "params": params.params,
        "script_available": action_script.exists(),
        "suggested_modules": [],
        "guidance": "",
    }

    # Suggest relevant modules based on action keywords
    modules = list_modules(skill_path)
    action_lower = params.action.lower()

    module_keywords = {
        "scoring": ["score", "analyze", "rate", "evaluate"],
        "company-research": ["company", "research", "investigate"],
        "skills-matching": ["match", "skills", "cv", "resume"],
        "linkedin-tracking": ["linkedin", "track", "application"],
        "recruiter-contacts": ["contact", "recruiter", "network"],
        "follow-up-reminders": ["reminder", "follow", "followup"],
        "job-backlog-manager": ["backlog", "queue", "pending"],
        "database-operations": ["save", "export", "database", "excel"],
    }

    for module, keywords in module_keywords.items():
        if module in modules and any(kw in action_lower for kw in keywords):
            result["suggested_modules"].append(module)

    # Provide guidance based on action
    if "analyze" in action_lower or "score" in action_lower:
        result["guidance"] = (
            "Load scoring-formulas and skills-matching modules. Provide URL in params['url']. "
            "Workflow: 1) Parse job posting, 2) Research company, 3) Match skills, 4) Calculate scores."
        )
    elif "track" in action_lower or "linkedin" in action_lower:
        result["guidance"] = "Load linkedin-tracking module. Use params['url'] for LinkedIn job URL."
    elif "contact" in action_lower or "recruiter" in action_lower:
        result["guidance"] = "Load recruiter-contacts module for contact management."
    elif "reminder" in action_lower or "follow" in action_lower:
        result["guidance"] = "Load follow-up-reminders module for reminder operations."
    elif "backlog" in action_lower:
        result["guidance"] = "Load job-backlog-manager module for queue operations."
    elif "claim_task" in action_lower or "claim" in action_lower:
        # Enhanced guidance for claim_task with deep analysis
        action_params = _coerce_action_params(getattr(params, "params", {}))
        task_analysis = action_params.get("task_analysis", {})
        is_ui_task = action_params.get("is_ui_task", False)

        guidance_parts = [
            "Perform DEEP analysis of the task. Your goal is to extract SPECIFIC, ACTIONABLE requirements.",
            "",
            "## Analysis Requirements:",
            "1. **Task Type**: Determine if this is UI improvement, bug fix, feature, or refactor",
            "2. **Scope**: Is this global (affects many pages) or page-specific?",
            "3. **Affected Pages**: Extract all page URLs and routes mentioned",
            "4. **Specific Requirements**: Extract ALL detailed requirements (not just high-level)",
            "5. **Context**: Note any page-specific issues, constraints, or dependencies",
            "",
        ]

        if is_ui_task:
            guidance_parts.extend(
                [
                    "## UI Task Specifics:",
                    "- This is a UI improvement task - analyze page-specific context",
                    "- Extract page URLs and identify affected routes",
                    "- Distinguish between global design system changes vs page-specific fixes",
                    "- Note layout, component usage, and content density per page",
                    "",
                ]
            )

        if task_analysis:
            guidance_parts.extend(
                [
                    "## Task Analysis Context:",
                    f"- Task Type: {task_analysis.get('task_type', 'unknown')}",
                    f"- Is Global: {task_analysis.get('global_issue', False)}",
                    f"- Affected Pages: {', '.join(task_analysis.get('affected_pages', []))}",
                    f"- Recommended Approach: {task_analysis.get('recommended_approach', '')}",
                    "",
                ]
            )

        guidance_parts.extend(
            [
                "## Output Format:",
                "Provide a detailed task_spec JSON with:",
                "- task_type: 'ui_improvement' | 'bugfix' | 'feature' | 'refactor'",
                "- is_global: boolean",
                "- affected_pages: [list of page paths]",
                "- specific_requirements: [detailed list of ALL requirements]",
                "- recommended_files: [likely files/components to modify]",
                "- implementation_notes: [specific guidance for implementation]",
                "- page_specific_issues: {page_url: {details}} if page-specific",
            ]
        )

        result["guidance"] = "\n".join(guidance_parts)
    elif "implement_feature" in action_lower or "implement" in action_lower:
        # Enhanced guidance for implement_feature
        action_params = _coerce_action_params(getattr(params, "params", {}))
        task_analysis = action_params.get("task_analysis", {})
        previous_outputs = action_params.get("previous_outputs", {})
        refactor_plan = previous_outputs.get("refactor_plan", {}) if isinstance(previous_outputs, dict) else {}

        guidance_parts = [
            "Implement the feature based on the design plan. Use ALL available context.",
            "",
            "## Implementation Requirements:",
            "",
        ]

        if task_analysis and task_analysis.get("task_type") == "ui_improvement":
            guidance_parts.extend(
                [
                    "### UI Task Implementation:",
                    "- This is a UI improvement - make PAGE-SPECIFIC changes",
                    "- For EACH affected page, analyze its current code structure",
                    "- Make targeted changes per page (don't copy-paste generic solutions)",
                    "- Consider each page's unique layout, components, and content density",
                    "- Test changes on the specific page(s)",
                    "",
                ]
            )

            if task_analysis.get("global_issue"):
                guidance_parts.extend(
                    [
                        "⚠️ GLOBAL ISSUE: Apply changes to src/lib design system components, NOT individual pages",
                        "- Modify: src/lib components, layout components, global styles",
                        "- Do NOT modify: individual page components",
                        "",
                    ]
                )
            else:
                guidance_parts.extend(
                    [
                        "⚠️ PAGE-SPECIFIC: Make targeted changes to each affected page",
                        f"- Affected pages: {', '.join(task_analysis.get('affected_pages', []))}",
                        "- Analyze each page's current state before making changes",
                        "",
                    ]
                )
        else:
            guidance_parts.extend(
                [
                    "### General Implementation:",
                    "- Follow the design plan exactly",
                    "- Make specific, targeted changes",
                    "- Preserve existing functionality",
                    "",
                ]
            )

        if refactor_plan:
            guidance_parts.extend(
                [
                    "## Design Plan Available:",
                    "Use the refactor_plan from previous step to guide implementation.",
                    "",
                ]
            )

        guidance_parts.extend(
            [
                "## Quality Requirements:",
                "- Make SPECIFIC, TARGETED changes (not generic)",
                "- Preserve existing functionality",
                "- Follow code style and patterns",
                "- Test changes appropriately",
                "",
                "## Context Available:",
                "- task_analysis: Available in params",
                "- refactor_plan: Available in previous_outputs",
                "- All previous step outputs: Available in previous_outputs",
            ]
        )

        result["guidance"] = "\n".join(guidance_parts)
    elif not result["guidance"]:
        result["guidance"] = f"Load skill overview first to see available commands for '{params.action}'."

    if not result["suggested_modules"]:
        result["suggested_modules"] = modules[:3]  # First 3 as fallback

    return result


# =============================================================================
# Tool Registration
# =============================================================================


def register_action_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any,
    resolve_skill_entry: Callable,
) -> None:
    """
    Register Action tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mcp_tool_interceptor: Decorator for tool interception
        metrics: MetricsTracker instance for telemetry
        resolve_skill_entry: Function to resolve skill entries
    """

    @mcp.tool(
        name="skill-action",
        annotations=tool_annotations(
            {
                "title": "Execute Skill Action",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            }
        ),
    )
    @mcp_tool_interceptor
    async def skill_action(params: SkillActionInput) -> str:
        """Execute a skill action/command.

        Interprets action and returns guidance or executes if script available.
        Use after loading the skill overview to understand commands.

        Args:
            params: SkillActionInput with skill_name, action, and params dict

        Returns:
            str: Action result with suggested next modules
        """
        result = build_skill_action_result(params, resolve_skill_entry)
        return json.dumps(result, indent=2)


__all__ = ["register_action_tools"]

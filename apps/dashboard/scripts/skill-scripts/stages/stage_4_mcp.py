"""
Stage 4: MCP/Actions.

Define MCP tools and dashboard actions for the skill.

Outputs:
- mcp/__init__.py with register_tools (full profile)
- dashboard.yaml actions array
- api/health/route.ts (full profile)
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import yaml

from .base_stage import BaseStage
from ._imports import ValidationResult, ValidationIssue

if TYPE_CHECKING:
    from ._imports import StageOutput, WorkflowState


class Stage4MCP(BaseStage):
    """Stage 4: MCP/Actions - Define tools and dashboard actions."""

    @property
    def stage_num(self) -> int:
        return 4

    @property
    def stage_name(self) -> str:
        return "MCP/Actions"

    @property
    def description(self) -> str:
        return "Define MCP tools and dashboard actions"

    def get_acceptance_criteria(self) -> List[str]:
        return [
            "mcp/__init__.py with register_tools (full profile)",
            "dashboard.yaml has valid actions array",
            "Actions have: id, label, icon, dispatch",
            "api/health/route.ts exists (full profile)",
        ]

    def plan(
        self,
        state: "WorkflowState",
        previous_output: Optional["StageOutput"] = None,
        user_answers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create execution plan for MCP/Actions."""
        skill_path = state.skill_path
        mcp_dir = skill_path / "mcp"
        dashboard_yaml = skill_path / "dashboard.yaml"

        plan = {
            "skill_path": str(skill_path),
            "mcp_dir": str(mcp_dir),
            "dashboard_yaml": str(dashboard_yaml),
            "target_profile": state.target_profile,
            "steps": [
                {"action": "analyze_action_needs"},
                {"action": "create_dashboard_yaml"},
                {"action": "add_actions_to_dashboard"},
            ],
            "files_to_create": [str(dashboard_yaml)],
            "files_to_modify": [],
        }

        # Full profile gets MCP tools
        if state.target_profile == "full":
            plan["steps"].extend(
                [
                    {"action": "create_mcp_directory"},
                    {"action": "generate_mcp_init"},
                    {"action": "create_api_health_route"},
                ]
            )
            plan["files_to_create"].extend(
                [
                    str(mcp_dir / "__init__.py"),
                    str(skill_path / "dashboard" / "api" / "health" / "route.ts"),
                ]
            )

        if user_answers:
            plan["user_inputs"] = user_answers

        return plan

    def execute(
        self,
        state: "WorkflowState",
        plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the MCP/Actions plan."""
        skill_path = state.skill_path
        user_inputs = plan.get("user_inputs", {})

        files_created = []
        files_modified = []

        # Get action definitions from user or defaults
        actions = user_inputs.get("actions", [])
        if isinstance(actions, str):
            # Parse comma-separated action names
            action_names = [a.strip() for a in actions.split(",") if a.strip()]
            actions = [
                {
                    "id": name.lower().replace(" ", "-"),
                    "label": name.title(),
                    "icon": "Zap",
                    "dispatch": "oneshot",
                }
                for name in action_names
            ]

        # Add default overview action if none provided
        if not actions:
            actions = [
                {
                    "id": "refresh",
                    "label": "Refresh",
                    "description": f"Refresh {state.skill_name} data",
                    "icon": "RefreshCw",
                    "dispatch": "fire",
                },
            ]

        # Create/update dashboard.yaml
        dashboard_yaml_path = skill_path / "dashboard.yaml"
        dashboard_config = self._load_or_create_dashboard_yaml(dashboard_yaml_path, state.skill_name)

        # Merge actions - keep existing, add new ones that don't conflict by id
        existing_actions = dashboard_config.get("actions", [])
        existing_ids = {a.get("id") for a in existing_actions if isinstance(a, dict)}

        # Only add new actions that don't already exist
        for action in actions:
            if action.get("id") not in existing_ids:
                existing_actions.append(action)

        dashboard_config["actions"] = existing_actions

        with open(dashboard_yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(dashboard_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        if dashboard_yaml_path.exists():
            files_modified.append(str(dashboard_yaml_path))

        # Full profile: Create MCP tools
        if state.target_profile == "full":
            mcp_dir = skill_path / "mcp"
            mcp_dir.mkdir(parents=True, exist_ok=True)

            # Generate MCP __init__.py
            mcp_init_content = self._generate_mcp_init(
                skill_name=state.skill_name,
                actions=actions,
            )
            mcp_init_path = mcp_dir / "__init__.py"
            mcp_init_path.write_text(mcp_init_content, encoding="utf-8")
            files_created.append(str(mcp_init_path))

            # Generate API health route
            api_dir = skill_path / "dashboard" / "api" / "health"
            api_dir.mkdir(parents=True, exist_ok=True)

            health_route_content = self._generate_health_route(state.skill_name)
            health_route_path = api_dir / "route.ts"
            health_route_path.write_text(health_route_content, encoding="utf-8")
            files_created.append(str(health_route_path))

        return {
            "files_created": files_created,
            "files_modified": files_modified,
            "data": {
                "actions": actions,
                "dashboard_yaml": str(dashboard_yaml_path),
            },
        }

    def test(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run automated tests on MCP/Actions."""
        skill_path = state.skill_path
        results = {}

        # Test 1: dashboard.yaml exists
        dashboard_yaml = skill_path / "dashboard.yaml"
        results["dashboard_yaml_exists"] = {
            "passed": dashboard_yaml.exists(),
            "message": "dashboard.yaml exists" if dashboard_yaml.exists() else "dashboard.yaml missing",
        }

        # Test 2: dashboard.yaml has valid actions
        if dashboard_yaml.exists():
            try:
                with open(dashboard_yaml) as f:
                    config = yaml.safe_load(f) or {}

                actions = config.get("actions", [])
                has_actions = len(actions) > 0

                results["has_actions"] = {
                    "passed": has_actions,
                    "message": f"Has {len(actions)} actions" if has_actions else "No actions defined",
                }

                # Test 3: Actions have required fields
                if has_actions:
                    required_fields = {"id", "label", "dispatch"}
                    all_valid = all(all(field in action for field in required_fields) for action in actions)
                    results["actions_valid"] = {
                        "passed": all_valid,
                        "message": (
                            "All actions have required fields" if all_valid else "Some actions missing required fields"
                        ),
                    }
            except Exception as e:
                results["dashboard_yaml_parse"] = {
                    "passed": False,
                    "message": f"Failed to parse dashboard.yaml: {e}",
                }

        # Full profile tests
        if state.target_profile == "full":
            # Test 4: MCP __init__.py exists
            mcp_init = skill_path / "mcp" / "__init__.py"
            results["mcp_init_exists"] = {
                "passed": mcp_init.exists(),
                "message": "mcp/__init__.py exists" if mcp_init.exists() else "mcp/__init__.py missing",
            }

            # Test 5: MCP has register_tools function
            if mcp_init.exists():
                content = mcp_init.read_text(encoding="utf-8")
                has_register = "def register_tools" in content
                results["has_register_tools"] = {
                    "passed": has_register,
                    "message": "register_tools function found" if has_register else "register_tools function missing",
                }

            # Test 6: API health route exists
            health_route = skill_path / "dashboard" / "api" / "health" / "route.ts"
            results["health_route_exists"] = {
                "passed": health_route.exists(),
                "message": "api/health/route.ts exists" if health_route.exists() else "api/health/route.ts missing",
            }

        return results

    def validate(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
        test_results: Dict[str, Any],
    ) -> "ValidationResult":
        """Validate against acceptance criteria."""
        result = ValidationResult()

        for test_name, test_result in test_results.items():
            if not test_result.get("passed", False):
                severity = "error" if "exists" in test_name else "warning"
                result.add_issue(
                    ValidationIssue(
                        rule=f"test_{test_name}",
                        message=test_result.get("message", f"Test {test_name} failed"),
                        severity=severity,
                    )
                )

        return result

    def generate_questions(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
        validation: Optional["ValidationResult"] = None,
    ) -> List[Dict[str, Any]]:
        """Generate context-aware questions for MCP/Actions."""
        questions = [
            {
                "id": "actions",
                "text": "What dashboard actions should be available? (comma-separated)",
                "type": "text",
                "default": "refresh, analyze, export",
                "required": True,
                "context": "Actions appear as buttons in the dashboard. Common: refresh, analyze, export, import, sync",
            },
            {
                "id": "primary_flow",
                "text": "What should be the primary action dispatch type?",
                "type": "choice",
                "options": ["fire", "oneshot", "modal"],
                "default": "oneshot",
                "required": True,
                "context": "fire: Immediate action. oneshot: single AI task. modal: collect user input first.",
            },
        ]

        # Full profile gets MCP-specific questions
        if state.target_profile == "full":
            questions.append(
                {
                    "id": "mcp_tools",
                    "text": "What MCP tools should be exposed? (comma-separated)",
                    "type": "text",
                    "default": f"get-{state.skill_name}-status, list-{state.skill_name}-items",
                    "required": True,
                    "context": "MCP tools are callable by AI agents. Use kebab-case names.",
                }
            )

        return questions

    def get_output(self, state: "WorkflowState") -> Dict[str, Any]:
        """Get the stage output data."""
        skill_path = state.skill_path
        output = {}

        # Get actions from dashboard.yaml
        dashboard_yaml = skill_path / "dashboard.yaml"
        if dashboard_yaml.exists():
            try:
                with open(dashboard_yaml) as f:
                    config = yaml.safe_load(f) or {}
                output["actions"] = config.get("actions", [])
            except Exception as e:
                warnings.warn(
                    f"Failed to read dashboard actions from {dashboard_yaml}: {e}",
                    RuntimeWarning,
                    stacklevel=2,
                )

        # Check MCP tools
        mcp_init = skill_path / "mcp" / "__init__.py"
        output["has_mcp"] = mcp_init.exists()

        return output

    def get_default_answers(self, state: "WorkflowState") -> Dict[str, Any]:
        """Get default answers for auto mode."""
        return {
            "actions": "refresh, analyze, export",
            "primary_flow": "oneshot",
            "mcp_tools": f"get-{state.skill_name}-status, list-{state.skill_name}-items",
        }

    def _load_or_create_dashboard_yaml(
        self,
        path: Path,
        skill_name: str,
    ) -> Dict[str, Any]:
        """Load existing dashboard.yaml or create default."""
        if path.exists():
            try:
                with open(path) as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                warnings.warn(
                    f"Failed to parse existing dashboard config at {path}: {e}",
                    RuntimeWarning,
                    stacklevel=2,
                )

        # Default structure
        return {
            "hub": {
                "id": skill_name,
                "label": skill_name.replace("-", " ").title(),
                "icon": "Sparkles",
            },
            "tabs": [
                {
                    "id": "overview",
                    "label": "Overview",
                    "default": True,
                },
            ],
            "actions": [],
        }

    def _generate_mcp_init(
        self,
        skill_name: str,
        actions: List[Dict[str, Any]],
    ) -> str:
        """Generate MCP __init__.py content."""

        # Generate tool implementations
        tool_impls = []
        tool_registrations = []

        for action in actions:
            action_id = action["id"]
            func_name = action_id.replace("-", "_")
            tool_impls.append(f'''
def {func_name}_impl(params: dict) -> dict:
    """Implementation for {action.get('label', action_id)}."""
    # TODO: Implement {action_id} logic
    return {{"status": "success", "action": "{action_id}"}}
''')
            tool_registrations.append(f'''    server.register_tool(
        name="{action_id}",
        description="{action.get('description', action.get('label', action_id))}",
        handler={func_name}_impl,
    )''')

        return f'''"""
MCP Tools for {skill_name}.

Auto-generated by mcp-app-factory Stage 4.
"""

from typing import Any, Dict


# Tool implementations
{"".join(tool_impls)}

def register_tools(server: Any) -> None:
    """Register all MCP tools for {skill_name}."""
{"".join(tool_registrations) if tool_registrations else "    pass  # No tools to register"}
'''

    def _generate_health_route(self, skill_name: str) -> str:
        """Generate API health route TypeScript content."""
        return f'''/**
 * Health check API route for {skill_name}.
 * Auto-generated by mcp-app-factory Stage 4.
 */

import {{ NextResponse }} from "next/server";

export async function GET() {{
  return NextResponse.json({{
    status: "healthy",
    skill: "{skill_name}",
    timestamp: new Date().toISOString(),
  }});
}}
'''

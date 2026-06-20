"""Stage 2: Blueprint -- generate a hub blueprint from flow analysis."""
from __future__ import annotations

from typing import Any

from workflow_runner import RunState, Stage

try:
    from ..blueprint_generator import BlueprintGenerator, UserOverrides
except ImportError:
    from blueprint_generator import BlueprintGenerator, UserOverrides  # noqa: E402


class BlueprintStage(Stage):
    """Generate a hub blueprint from flow analysis + user answers."""

    @property
    def name(self) -> str:
        return "blueprint"

    @property
    def description(self) -> str:
        return "Generate hub blueprint from analysis and user preferences"

    def plan(
        self,
        state: RunState,
        previous_output: dict[str, Any] | None = None,
        user_answers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        flow = state.context.get("flow_analysis")
        if not flow:
            return {}
        return {"steps": ["apply_overrides", "generate_blueprint"]}

    def execute(
        self,
        state: RunState,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            from ..flow_analyzer import (
                FlowAnalysis,
                StatCard,
                SuggestedAction,
                SuggestedTab,
                FileStrategy,
            )
        except ImportError:
            from flow_analyzer import (
                FlowAnalysis,
                StatCard,
                SuggestedAction,
                SuggestedTab,
                FileStrategy,
            )

        flow_dict = state.context.get("flow_analysis", {})

        # Reconstruct FlowAnalysis from dict
        flow = FlowAnalysis(
            hub=flow_dict.get("hub", ""),
            source_path=flow_dict.get("source_path", ""),
            suggested_tabs=[SuggestedTab(**t) for t in flow_dict.get("suggested_tabs", [])],
            stat_cards=[StatCard(**c) for c in flow_dict.get("stat_cards", [])],
            actions=[SuggestedAction(**a) for a in flow_dict.get("actions", [])],
            file_strategies=[FileStrategy(**f) for f in flow_dict.get("file_strategies", [])],
        )

        # Apply user overrides
        overrides = UserOverrides.from_answers(state.user_answers.get("blueprint", {}))

        generator = BlueprintGenerator(flow, overrides=overrides)
        blueprint = generator.generate()

        # Store blueprint in context for code gen
        state.context["blueprint"] = blueprint

        return {
            "hub_id": blueprint["hub"]["id"],
            "hub_title": blueprint["hub"]["title"],
            "tab_count": len(blueprint.get("tabs", [])),
            "action_count": len(blueprint.get("actions", [])),
            "rendered_files": len(blueprint.get("rendered_files", [])),
            "external_only": len(blueprint.get("external_only", [])),
        }

    def validate(
        self,
        state: RunState,
        artifacts: dict[str, Any],
    ) -> tuple[bool, str | None]:
        if artifacts.get("tab_count", 0) == 0:
            return False, "Blueprint has no tabs"
        return True, None

    def generate_questions(
        self,
        state: RunState,
        artifacts: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Ask for hub title/icon customization."""
        return [
            {
                "id": "hub_title",
                "text": f"Hub title (default: '{artifacts.get('hub_title', '')}')?",
                "type": "text",
                "default": artifacts.get("hub_title", ""),
                "required": False,
            },
            {
                "id": "hub_bundle",
                "text": "Which bundle?",
                "type": "choice",
                "options": [
                    {"value": "lifestyle", "label": "Lifestyle (user-facing personal skills)"},
                    {"value": "productivity", "label": "Productivity (task/workflow skills)"},
                    {"value": "ai", "label": "AI (AI/integration capabilities)"},
                    {"value": "dev", "label": "Dev (dev/build tools)"},
                ],
                "default": "lifestyle",
                "required": False,
            },
        ]

"""Stage 1: DeepScan -- scan a folder and run flow analysis."""
from __future__ import annotations

from typing import Any

from workflow_runner import RunState, Stage

try:
    from ..file_analyzers import get_analyzer_map
    from ..flow_analyzer import FlowAnalyzer
    from ..source_adapters.folder import FolderAdapter
except ImportError:
    from file_analyzers import get_analyzer_map  # noqa: E402
    from flow_analyzer import FlowAnalyzer  # noqa: E402
    from source_adapters.folder import FolderAdapter  # noqa: E402


class DeepScanStage(Stage):
    """Scan a folder and run flow analysis."""

    @property
    def name(self) -> str:
        return "deep_scan"

    @property
    def description(self) -> str:
        return "Scan external data folder and analyze file structures"

    def plan(
        self,
        state: RunState,
        previous_output: dict[str, Any] | None = None,
        user_answers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        folder = state.context.get("folder", "")
        hub = state.context.get("hub", "")

        if not folder:
            return {}

        return {
            "folder": folder,
            "hub": hub,
            "steps": ["scan_folder", "run_analyzers", "flow_analysis"],
        }

    def execute(
        self,
        state: RunState,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        folder = plan["folder"]
        hub = plan["hub"]

        # Scan with all analyzers
        analyzers = get_analyzer_map()
        adapter = FolderAdapter(folder, analyzers=analyzers)
        manifest = adapter.scan()

        # Run flow analysis
        analyzer = FlowAnalyzer(hub)
        flow = analyzer.analyze(manifest)

        # Store flow analysis in context for later stages
        state.context["flow_analysis"] = flow.to_dict()

        return {
            "file_count": manifest.file_count,
            "directory_count": manifest.directory_count,
            "total_size": manifest.total_size,
            "suggested_tabs": len(flow.suggested_tabs),
            "stat_cards": len(flow.stat_cards),
            "actions": len(flow.actions),
            "flow": flow.to_dict(),
        }

    def validate(
        self,
        state: RunState,
        artifacts: dict[str, Any],
    ) -> tuple[bool, str | None]:
        if artifacts.get("file_count", 0) == 0 and artifacts.get("directory_count", 0) == 0:
            return False, "No files found in the source folder"
        return True, None

    def generate_questions(
        self,
        state: RunState,
        artifacts: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Ask user to confirm scan results and tab suggestions."""
        flow = artifacts.get("flow", {})
        tabs = flow.get("suggested_tabs", [])
        tab_names = [f"{t['label']} ({t['tab_type']})" for t in tabs]

        questions = [
            {
                "id": "confirm_tabs",
                "text": f"Suggested tabs: {', '.join(tab_names)}. Accept?",
                "type": "yes_no",
                "default": "yes",
                "required": False,
            },
        ]
        return questions

    def get_output(self, state: RunState) -> dict[str, Any]:
        return {"flow_analysis": state.context.get("flow_analysis", {})}

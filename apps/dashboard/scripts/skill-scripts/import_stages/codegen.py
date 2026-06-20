"""Stage 4: CodeGen -- generate plugin files from the blueprint."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_runner import RunState, Stage

try:
    from ..import_codegen import ImportCodeGenerator
except ImportError:
    from import_codegen import ImportCodeGenerator  # noqa: E402


class CodeGenStage(Stage):
    """Generate plugin files from the blueprint."""

    @property
    def name(self) -> str:
        return "codegen"

    @property
    def description(self) -> str:
        return "Generate plugin source files from blueprint"

    def plan(
        self,
        state: RunState,
        previous_output: dict[str, Any] | None = None,
        user_answers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        blueprint = state.context.get("blueprint")
        if not blueprint:
            return {}
        return {"steps": ["generate_files", "write_to_disk"]}

    def execute(
        self,
        state: RunState,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        blueprint = state.context.get("blueprint", {})

        # Resolve project root
        import sys
        _project_root = Path(__file__).resolve()
        while _project_root.name != "plugins" and _project_root != _project_root.parent:
            _project_root = _project_root.parent
        _project_root = _project_root.parent

        codegen = ImportCodeGenerator(blueprint, project_root=_project_root)
        generated_files = codegen.generate()

        return {
            "skill_dir": str(codegen.skill_dir),
            "files_generated": list(generated_files.keys()),
            "file_count": len(generated_files),
        }

    def validate(
        self,
        state: RunState,
        artifacts: dict[str, Any],
    ) -> tuple[bool, str | None]:
        skill_dir = artifacts.get("skill_dir")
        if not skill_dir or not Path(skill_dir).exists():
            return False, f"Skill directory not created: {skill_dir}"

        required = ["SKILL.md", "dashboard.yaml"]
        for f in required:
            if not (Path(skill_dir) / f).exists():
                return False, f"Missing required file: {f}"

        return True, None

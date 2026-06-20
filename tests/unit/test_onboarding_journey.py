from __future__ import annotations

import json
from pathlib import Path

from src.lib.brain_init import ProjectBrainInitResult, init_project_brain
from src.lib.brain_manifest import BRAIN_MANIFEST_NAME, STANDARD_BRAIN_FILES
from src.lib.onboarding_journey import (
    PROJECT_INVENTORY_QUESTION_PROMPT,
    activate_project_launch_context,
    build_project_init_launch_journey,
    format_project_init_launch_journey,
)


def _result(tmp_path: Path, *, sync_returncode: int | None = None) -> ProjectBrainInitResult:
    project = tmp_path / "demo"
    brain_root = project / "project-brain"
    inventory = brain_root / "config" / "inventory" / "ai-artifacts.json"
    return ProjectBrainInitResult(
        brain_id="project-demo",
        brain_root=brain_root,
        project_root=project,
        created=True,
        sync_returncode=sync_returncode,
        inventory_path=inventory,
        inventory_count=3,
        inventory_warning_count=1,
    )


def test_launch_journey_names_first_value_write_boundary_and_next_action(
    tmp_path: Path,
) -> None:
    payload = build_project_init_launch_journey(_result(tmp_path))
    inventory_path = tmp_path / "demo" / "project-brain" / "config" / "inventory" / "ai-artifacts.json"

    assert payload["success_moment"] == "inventory_proof"
    assert payload["first_question"] == "Which folder should I initialize?"
    assert payload["promise"] == (
        "Get to know your AI setup, build your local second brain, " "and talk with your projects."
    )
    assert payload["inventory"] == {
        "count": 3,
        "warnings": 1,
        "path": str(inventory_path),
    }
    assert payload["write_boundary"]["inventory_only"] is True
    assert payload["write_boundary"]["chosen_folder_default_writes"] == [
        str(tmp_path / "demo" / "project-brain"),
        str(tmp_path / "demo" / "project-brain" / BRAIN_MANIFEST_NAME),
        *[str(tmp_path / "demo" / "project-brain" / filename) for filename in STANDARD_BRAIN_FILES],
        str(inventory_path),
    ]
    assert payload["write_boundary"]["chosen_folder_vendor_files"] == "read_only"
    assert payload["primary_next_action"]["label"] == "Ask Augur about this project"
    assert payload["primary_next_action"]["prompt"] == PROJECT_INVENTORY_QUESTION_PROMPT
    assert payload["primary_next_action"]["retention"] == "answer_only"


def test_launch_journey_marks_projection_sync_as_opt_in(tmp_path: Path) -> None:
    payload = build_project_init_launch_journey(_result(tmp_path, sync_returncode=0))

    assert payload["write_boundary"]["inventory_only"] is False
    assert "generated AI-client projections" in " ".join(payload["write_boundary"]["chosen_folder_opt_in_writes"])


def test_launch_journey_text_is_chat_ready(tmp_path: Path) -> None:
    text = format_project_init_launch_journey(build_project_init_launch_journey(_result(tmp_path)))

    assert "First value: AI artifact inventory" in text
    assert "3 records, 1 warnings" in text
    assert "Chosen-folder writes: project-brain metadata and inventory only" in text
    assert (
        "Existing vendor files: read-only inventory; not adopted, rewritten, merged, " "deleted, or projected over"
    ) in text
    assert "http://localhost:3000/browse" in text
    assert "Ask Augur about this project" in text
    assert PROJECT_INVENTORY_QUESTION_PROMPT in text


def test_launch_journey_text_discloses_requested_projection_writes(
    tmp_path: Path,
) -> None:
    text = format_project_init_launch_journey(build_project_init_launch_journey(_result(tmp_path, sync_returncode=0)))

    assert (
        "Chosen-folder writes: project-brain metadata, inventory, and requested " "generated AI-client projections"
    ) in text


def test_activate_project_launch_context_selects_initialized_project(tmp_path: Path) -> None:
    registry = tmp_path / "brains.yaml"
    state = tmp_path / "active-context.json"
    project = tmp_path / "repo"
    result = init_project_brain(project, registry_path=registry, refresh_inventory=False)

    context_result = activate_project_launch_context(
        result,
        registry_path=registry,
        state_path=state,
    )

    assert context_result.success is True
    assert context_result.context.scope == "brain"
    assert context_result.context.brain_id == result.brain_id
    assert json.loads(state.read_text(encoding="utf-8"))["brain_id"] == result.brain_id

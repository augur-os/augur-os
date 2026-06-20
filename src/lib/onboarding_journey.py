from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.lib.brain_active_context import (
    ActiveBrainFolderContextResult,
    set_active_brain_folder_context,
)
from src.lib.brain_init import ProjectBrainInitResult
from src.lib.brain_manifest import BRAIN_MANIFEST_NAME, STANDARD_BRAIN_FILES

ONBOARDING_PROMISE = "Get to know your AI setup, build your local second brain, " "and talk with your projects."
FIRST_FOLDER_QUESTION = "Which folder should I initialize?"
PROJECT_INVENTORY_QUESTION_PROMPT = (
    "What should I know about this project based on the AI setup and inventory "
    "Augur just found? Answer only; do not save or retain anything unless I ask."
)


def build_project_init_launch_journey(result: ProjectBrainInitResult) -> dict[str, Any]:
    inventory_only = result.sync_returncode is None
    default_writes = [
        str(result.brain_root),
        str(result.brain_root / BRAIN_MANIFEST_NAME),
        *[str(result.brain_root / filename) for filename in STANDARD_BRAIN_FILES],
    ]
    if result.inventory_path is not None:
        default_writes.append(str(result.inventory_path))

    return {
        "version": 1,
        "promise": ONBOARDING_PROMISE,
        "first_question": FIRST_FOLDER_QUESTION,
        "success_moment": "inventory_proof",
        "brain_id": result.brain_id,
        "brain_root": str(result.brain_root),
        "project_root": str(result.project_root),
        "inventory": {
            "count": result.inventory_count,
            "warnings": result.inventory_warning_count,
            "path": str(result.inventory_path) if result.inventory_path else None,
        },
        "write_boundary": {
            "inventory_only": inventory_only,
            "chosen_folder_vendor_files": "read_only",
            "chosen_folder_default_writes": default_writes,
            "chosen_folder_opt_in_writes": (
                [] if inventory_only else ["generated AI-client projections requested by --sync/run_sync=true"]
            ),
            "installer_owned_updates": [
                "Augur install directory",
                "MCP/client integration config",
                "generated client surfaces for the active install target",
                "client plugin cache when an existing Augur cache is detected",
            ],
        },
        "browse": {
            "path": "/browse",
            "preferred_url": "http://localhost:3000/browse",
            "open_when_possible": True,
            "fallback": "Print the Browse URL if browser control is unavailable.",
            "active_context": {
                "scope": "brain",
                "brain_id": result.brain_id,
                "project_root": str(result.project_root),
            },
        },
        "primary_next_action": {
            "id": "ask-project-inventory-summary",
            "label": "Ask Augur about this project",
            "prompt": PROJECT_INVENTORY_QUESTION_PROMPT,
            "dispatch": "chat",
            "retention": "answer_only",
        },
        "pause_policy": {
            "auto_fix_non_sensitive_prerequisites": True,
            "pause_only_for": ["credentials", "OS permissions", "destructive ambiguity"],
        },
    }


def format_project_init_launch_journey(payload: dict[str, Any]) -> str:
    inventory = payload["inventory"]
    browse = payload["browse"]
    action = payload["primary_next_action"]
    write_boundary = payload["write_boundary"]
    chosen_folder_writes = (
        "Chosen-folder writes: project-brain metadata and inventory only"
        if write_boundary["inventory_only"]
        else (
            "Chosen-folder writes: project-brain metadata, inventory, and requested " "generated AI-client projections"
        )
    )
    return "\n".join(
        [
            "First value: AI artifact inventory",
            f"Project brain: {payload['brain_id']}",
            f"Metadata folder: {payload['brain_root']}",
            f"Attached folder: {payload['project_root']}",
            ("AI artifact inventory: " f"{inventory['count']} records, {inventory['warnings']} warnings"),
            f"Inventory path: {inventory['path']}",
            chosen_folder_writes,
            (
                "Existing vendor files: read-only inventory; not adopted, rewritten, "
                "merged, deleted, or projected over"
            ),
            f"Browse: {browse['preferred_url']}",
            f"Next action: {action['label']}",
            f"Prompt: {action['prompt']}",
        ]
    )


def activate_project_launch_context(
    result: ProjectBrainInitResult,
    *,
    registry_path: Path | None = None,
    state_path: Path | None = None,
) -> ActiveBrainFolderContextResult:
    return set_active_brain_folder_context(
        {"scope": "brain", "brain_id": result.brain_id},
        cwd=result.project_root,
        project_root=result.project_root,
        registry_path=registry_path,
        state_path=state_path,
    )


def serialize_project_launch_context(
    context_result: ActiveBrainFolderContextResult,
) -> dict[str, Any]:
    return {
        "success": context_result.success,
        "context": asdict(context_result.context),
        "repaired": context_result.repaired,
        "error": context_result.error,
    }


def failed_project_launch_context_payload(error: str) -> dict[str, Any]:
    return {
        "success": False,
        "context": None,
        "repaired": False,
        "error": error,
    }

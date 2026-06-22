"""Brain discovery + init MCP tools (ADR-772).

``brain-discovery`` exposes the registered/detected brains, per-brain index and
git state, current-project status, and per-client projection status to the
``/brain/settings`` dashboard surface. ``brain-init`` runs the ``augur init``
project-brain bootstrap as an explicit, user-triggered action.

The heavy lifting lives in ``src/lib/brain_discovery.py`` (pure core engine) and
``src/lib/brain_init.py``. These thin async wrappers add the per-client
projection status (sourced from the existing sync-status surface) and serialize
to JSON, keeping the core engine free of project-brain skill imports.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any


def _projection_status() -> dict[str, Any]:
    """Per-client projection status for the active project (best-effort).

    Reuses the sync-status surface that reports which AI clients have Augur
    projections synced. Degrades to an empty payload if the project-brain
    capability module is not importable in this runtime — the dashboard renders
    "unknown" rather than failing the whole snapshot.
    """
    get_sync_status = _import_sync_status()
    if get_sync_status is None:
        return {}
    try:
        from src.config.paths import get_project_root

        return {
            "project_root": str(get_project_root()),
            "clients": get_sync_status(),
        }
    except Exception:
        return {}


def _import_sync_status():
    try:
        from skills.ai.scripts.ops.sync_status import get_sync_status

        return get_sync_status
    except ImportError:
        pass
    try:
        import sys

        from src.config.paths import get_project_root

        capabilities = get_project_root() / "project-brain" / "capabilities"
        if capabilities.is_dir() and str(capabilities) not in sys.path:
            sys.path.insert(0, str(capabilities))
        from skills.ai.scripts.ops.sync_status import get_sync_status

        return get_sync_status
    except Exception:
        return None


async def brain_discovery_impl(include_git_status: bool = True) -> str:
    """Return the full brain discovery snapshot as JSON.

    ``include_git_status=False`` skips the per-brain git subprocess calls and
    projection lookup for cheap, frequently-polled callers (the Browse brain
    filter only needs brain id/type/active state).
    """
    from src.lib.brain_discovery import build_discovery_snapshot

    snapshot = build_discovery_snapshot(
        cwd=Path.cwd(),
        projections=_projection_status() if include_git_status else {},
        include_git_status=include_git_status,
    )
    return json.dumps(snapshot, indent=2, default=str)


async def brain_init_impl(project_root: str | None = None, run_sync: bool = False) -> str:
    """Initialize (or re-attach) a project brain for ``project_root``.

    Defaults to the active project. Mirrors the ``augur init`` CLI: creates the
    repo-local ``project-brain/`` skeleton, registers it, and writes a read-only
    AI artifact inventory. Projection sync is explicit opt-in via ``run_sync``.
    """
    from src.config.paths import get_project_root
    from src.lib.brain_init import init_project_brain
    from src.lib.onboarding_journey import (
        activate_project_launch_context,
        build_project_init_launch_journey,
        failed_project_launch_context_payload,
        serialize_project_launch_context,
    )

    target = Path(project_root).expanduser() if project_root else get_project_root()
    try:
        result = init_project_brain(target, run_sync=run_sync)
    except Exception as exc:  # noqa: BLE001 — surface init failures to the UI
        return json.dumps({"success": False, "error": str(exc)})

    try:
        launch_context_payload = serialize_project_launch_context(activate_project_launch_context(result))
    except Exception as exc:  # noqa: BLE001 — init succeeded; report context failure in JSON
        launch_context_payload = failed_project_launch_context_payload(str(exc))
    return json.dumps(
        {
            "success": True,
            "brain_id": result.brain_id,
            "brain_root": str(result.brain_root),
            "project_root": str(result.project_root),
            "created": result.created,
            "sync_returncode": result.sync_returncode,
            "inventory_path": result.inventory_path.as_posix() if result.inventory_path else None,
            "inventory_count": result.inventory_count,
            "inventory_warning_count": result.inventory_warning_count,
            "launch_journey": build_project_init_launch_journey(result),
            "launch_context": launch_context_payload,
        },
        indent=2,
        default=str,
    )


async def brain_active_context_impl() -> str:
    """Return the persisted Browse/action folder context plus selectable options."""
    from src.config.paths import get_project_root
    from src.lib.brain_active_context import get_active_brain_folder_context

    result = get_active_brain_folder_context(
        cwd=Path.cwd(),
        project_root=get_project_root(),
    )
    return json.dumps(
        {
            "success": result.success,
            "context": asdict(result.context),
            "options": result.options,
            "repaired": result.repaired,
            "error": result.error,
        },
        indent=2,
        default=str,
    )


async def brain_set_active_context_impl(scope: str = "all", brain_id: str = "") -> str:
    """Persist the selected Browse/action folder context after validation."""
    from src.config.paths import get_project_root
    from src.lib.brain_active_context import set_active_brain_folder_context

    requested = {"scope": scope}
    if brain_id:
        requested["brain_id"] = brain_id
    result = set_active_brain_folder_context(
        requested,
        cwd=Path.cwd(),
        project_root=get_project_root(),
    )
    return json.dumps(
        {
            "success": result.success,
            "context": asdict(result.context),
            "options": result.options,
            "repaired": result.repaired,
            "error": result.error,
        },
        indent=2,
        default=str,
    )


async def brain_folder_scan_impl(project_root: str) -> str:
    """Run read-only AI artifact inventory for a folder without initializing it."""
    from src.lib.ai_artifact_inventory import scan_ai_artifacts

    target: Path | None = None
    try:
        target = Path(project_root).expanduser().resolve()
        inventory = scan_ai_artifacts(
            project_root=target,
            project_brain_id=f"preview-{target.name}",
        )
    except Exception as exc:  # noqa: BLE001 - report scan failures to dashboard
        return json.dumps(
            {
                "success": False,
                "error": str(exc),
                "project_root": str(target) if target else project_root,
            }
        )
    warning_count = len(inventory.warnings) + sum(len(record.warnings) for record in inventory.artifacts)
    return json.dumps(
        {
            "success": True,
            "project_root": str(target),
            "inventory_count": len(inventory.artifacts),
            "inventory_warning_count": warning_count,
            "artifacts": [asdict(record) for record in inventory.artifacts[:50]],
            "warnings": inventory.warnings,
            "writes_metadata": False,
        },
        indent=2,
        default=str,
    )

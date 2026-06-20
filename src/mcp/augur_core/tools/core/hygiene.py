"""hygiene-scan and hygiene-apply MCP tool implementations.

Thin wrappers around the routine-vault skill's scripts. The skill at
project-brain/capabilities/skills/routine-vault/ owns the logic; this file owns the
MCP-tool surface.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from src.config.paths import get_project_brain_skills_dir, get_project_root
from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp")

EXPECTED_SELECTION_ERROR_NAMES = {
    "HygieneApplyError",
    "HygieneScanError",
}


def _load_skill_module(module_filename: str, spec_name: str):
    """Load a script from the routine-vault skill via importlib.

    Skill directories contain hyphens, which makes dotted module imports
    impossible. We load by file path and register under a non-hyphenated
    spec name in sys.modules.
    """
    cached = sys.modules.get(spec_name)
    if cached is not None:
        return cached
    module_path = get_project_brain_skills_dir(Path(get_project_root())) / "routine-vault" / "scripts" / module_filename
    if not module_path.is_file():
        raise RuntimeError(f"routine-vault script not found: {module_path}")
    spec = importlib.util.spec_from_file_location(spec_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot create spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec_name] = module
    spec.loader.exec_module(module)
    return module


async def hygiene_scan_impl(path: str) -> str:
    """MCP tool: recursively scan a folder under Documents (read-only).

    Returns a JSON string with the structured scan result. The agent
    in the user's session reasons over this output.
    """
    try:
        mod = _load_skill_module("hygiene_scan.py", "loop_hygiene_mcp_scan")
        result = mod.hygiene_scan(path)
        return json.dumps({"success": True, **result})
    except Exception as exc:
        # Catch HygieneScanError specifically by class name to avoid
        # importing the exception class at module top-level.
        if exc.__class__.__name__ == "HygieneScanError":
            logger.warning("hygiene-scan refused path=%r: %s", path, exc)
            return json.dumps({"success": False, "error": str(exc)})
        # Unexpected error — log and re-raise.
        logger.exception("hygiene-scan unexpected error for path=%r", path)
        return json.dumps({"success": False, "error": f"unexpected error: {exc}"})


async def hygiene_apply_impl(
    root: str,
    moves: list[dict[str, Any]],
    dry_run: bool = True,
) -> str:
    """MCP tool: apply (or dry-run) a list of archive moves.

    `dry_run` defaults to True for safety. The slash command must pass
    `dry_run=False` explicitly when `--apply` is in scope.
    """
    try:
        mod = _load_skill_module("hygiene_apply.py", "loop_hygiene_mcp_apply")
        result = mod.hygiene_apply(root=root, moves=moves, dry_run=dry_run)
        return json.dumps({"success": True, **result})
    except Exception as exc:
        if exc.__class__.__name__ == "HygieneApplyError":
            logger.warning("hygiene-apply refused: %s", exc)
            return json.dumps({"success": False, "error": str(exc)})
        logger.exception("hygiene-apply unexpected error")
        return json.dumps({"success": False, "error": f"unexpected error: {exc}"})


def _is_expected_selection_error(exc: Exception) -> bool:
    return isinstance(exc, ValueError) or exc.__class__.__name__ in EXPECTED_SELECTION_ERROR_NAMES


async def hygiene_create_selection_impl(
    source_tab: str,
    filter_summary: dict[str, Any] | None,
    targets: list[dict[str, Any]],
) -> str:
    """MCP tool: validate and persist a typed Browse sweep selection."""
    try:
        mod = _load_skill_module("sweep_selection.py", "loop_hygiene_mcp_selection")
        result = mod.create_selection(
            source_tab=source_tab,
            filter_summary=filter_summary or {},
            targets=targets,
        )
        return json.dumps({"success": True, **result})
    except Exception as exc:
        if _is_expected_selection_error(exc):
            logger.warning("hygiene-create-selection refused: %s", exc)
            return json.dumps({"success": False, "error": str(exc)})
        logger.exception("hygiene-create-selection unexpected error")
        return json.dumps({"success": False, "error": f"unexpected error: {exc}"})


async def hygiene_scan_selection_impl(selection_id: str) -> str:
    """MCP tool: scan a previously persisted typed Browse sweep selection."""
    try:
        selection_mod = _load_skill_module("sweep_selection.py", "loop_hygiene_mcp_selection")
        scan_mod = _load_skill_module("hygiene_scan.py", "loop_hygiene_mcp_scan")
        selection = selection_mod.read_selection(selection_id)
        result = scan_mod.hygiene_scan_selection(selection)
        return json.dumps({"success": True, **result})
    except Exception as exc:
        if _is_expected_selection_error(exc):
            logger.warning("hygiene-scan-selection refused: %s", exc)
            return json.dumps({"success": False, "error": str(exc)})
        logger.exception("hygiene-scan-selection unexpected error")
        return json.dumps({"success": False, "error": f"unexpected error: {exc}"})


async def hygiene_apply_selection_impl(
    selection_id: str,
    moves: list[dict[str, Any]],
    dry_run: bool = True,
) -> str:
    """MCP tool: apply or dry-run approved moves for a typed Browse sweep selection."""
    try:
        selection_mod = _load_skill_module("sweep_selection.py", "loop_hygiene_mcp_selection")
        apply_mod = _load_skill_module("hygiene_apply.py", "loop_hygiene_mcp_apply")
        selection = selection_mod.read_selection(selection_id)
        result = apply_mod.hygiene_apply_selection(
            selection=selection,
            moves=moves,
            dry_run=dry_run,
        )
        return json.dumps({"success": True, **result})
    except Exception as exc:
        if _is_expected_selection_error(exc):
            logger.warning("hygiene-apply-selection refused: %s", exc)
            return json.dumps({"success": False, "error": str(exc)})
        logger.exception("hygiene-apply-selection unexpected error")
        return json.dumps({"success": False, "error": f"unexpected error: {exc}"})

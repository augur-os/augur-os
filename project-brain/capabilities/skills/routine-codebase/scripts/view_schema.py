"""auto-view-schema: Validate view YAML files — required fields, block refs, grid layout."""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import yaml

from src.config.paths import get_runtime_dir
from src.lib.ops_protocol import (
    FixResult, OpsContext, ScanResult, collect_all_block_ids, report_only_fix,
)

name = "auto-view-schema"

REQUIRED_VIEW_FIELDS = {"title", "blocks", "layout"}
REQUIRED_LAYOUT_FIELDS = {"columns", "rowHeight"}


def _check_grid_overlaps(blocks: list[dict]) -> list[tuple[str, str]]:
    """Check for overlapping block positions. Returns list of (id1, id2) overlap pairs."""
    overlaps: list[tuple[str, str]] = []
    positioned = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        pos = block.get("position")
        if not isinstance(pos, dict):
            continue
        instance_id = block.get("instanceId", "?")
        x, y = pos.get("x", 0), pos.get("y", 0)
        w, h = pos.get("w", 1), pos.get("h", 1)
        positioned.append((instance_id, x, y, w, h))

    for i, (id1, x1, y1, w1, h1) in enumerate(positioned):
        for j, (id2, x2, y2, w2, h2) in enumerate(positioned):
            if j <= i:
                continue
            # Check rectangle intersection
            if x1 < x2 + w2 and x1 + w1 > x2 and y1 < y2 + h2 and y1 + h1 > y2:
                overlaps.append((id1, id2))

    return overlaps


def scan(ctx: OpsContext) -> ScanResult:
    """Validate view YAML files in state/views/."""
    views_dir = get_runtime_dir() / "views"
    if not views_dir.is_dir():
        return ScanResult(issues=[], summary="No views directory", severity="info")

    view_files = sorted(views_dir.glob("*.yaml"))
    if not view_files:
        return ScanResult(issues=[], summary="No view files found", severity="info")

    all_block_ids = collect_all_block_ids(ctx.project_root)
    issues: list[dict] = []

    for view_file in view_files:
        try:
            data = yaml.safe_load(view_file.read_text())
        except Exception:
            issues.append({
                "type": "invalid_yaml",
                "file": view_file.name,
                "detail": f"View '{view_file.name}' has invalid YAML",
            })
            continue

        if not isinstance(data, dict):
            issues.append({
                "type": "invalid_structure",
                "file": view_file.name,
                "detail": f"View '{view_file.name}' top-level must be a mapping",
            })
            continue

        view_name = view_file.stem

        # Check required fields
        for field in REQUIRED_VIEW_FIELDS:
            if field not in data:
                issues.append({
                    "type": "missing_field",
                    "file": view_file.name,
                    "detail": f"View '{view_name}' missing required field '{field}'",
                })

        # Check layout sub-fields
        layout = data.get("layout")
        if isinstance(layout, dict):
            for field in REQUIRED_LAYOUT_FIELDS:
                if field not in layout:
                    issues.append({
                        "type": "missing_field",
                        "file": view_file.name,
                        "detail": f"View '{view_name}' layout missing required field '{field}'",
                    })

        # Check block references
        blocks = data.get("blocks", [])
        if isinstance(blocks, list):
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                block_id = block.get("blockId", "")
                if block_id and block_id not in all_block_ids:
                    issues.append({
                        "type": "orphan_block_ref",
                        "file": view_file.name,
                        "block_id": block_id,
                        "detail": f"View '{view_name}' references block '{block_id}' not declared in any skill",
                    })

            # Check grid overlaps
            for id1, id2 in _check_grid_overlaps(blocks):
                issues.append({
                    "type": "grid_overlap",
                    "file": view_file.name,
                    "detail": f"View '{view_name}' blocks '{id1}' and '{id2}' overlap",
                })

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} view schema issue(s) across {len(view_files)} view(s)",
        severity="warning" if issues else "info",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    return report_only_fix(ctx, "view-schema-latest.json", issues, noun="view schema issue")

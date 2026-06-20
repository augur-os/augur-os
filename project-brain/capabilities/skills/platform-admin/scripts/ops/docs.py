"""auto-docs: Compatibility shim for documentation sync workflow."""
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
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-docs"


def scan(ctx: OpsContext) -> ScanResult:
    return ScanResult(
        issues=[],
        summary="auto-docs: no autonomous scanner (findings fed externally)",
        severity="info",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would process {len(issues)} docs issue(s)",
        )
    if not issues:
        return FixResult(success=True, summary="No docs issues to process")
    return FixResult(
        success=True,
        actions=[{"status": "queued", "count": len(issues)}],
        summary=f"Queued {len(issues)} docs issue(s) for manual documentation sync",
    )

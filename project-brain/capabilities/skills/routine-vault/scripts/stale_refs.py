"""auto-stale-refs: Detect stale page and block references in action YAML files."""
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
from pathlib import Path

import yaml

from src.config.paths import get_all_client_skill_dirs, get_skill_assets_dir, get_skill_data_dir
from src.lib.ops_protocol import (
    FixResult, OpsContext, ScanResult, collect_all_block_ids,
    find_page_routes, report_only_fix,
)

name = "auto-stale-refs"


def _iter_skill_action_dirs(skill_dir: Path) -> list[Path]:
    """Collect local and canonical action directories for a skill."""
    skill_name = skill_dir.name
    candidates = [
        skill_dir / "assets" / "actions",
    ]
    try:
        candidates.append(get_skill_assets_dir(skill_name) / "actions")
    except Exception:
        pass
    try:
        candidates.append(get_skill_data_dir(skill_name) / "actions")
    except Exception:
        pass

    selected: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        selected.append(path)
    return selected


def scan(ctx: OpsContext) -> ScanResult:
    """Scan action YAML files for stale page and block references."""
    skill_dirs = get_all_client_skill_dirs(ctx.project_root)
    if not skill_dirs:
        return ScanResult(issues=[], summary="No skill directories", severity="info")

    page_routes = find_page_routes(ctx.project_root, ctx.shared_snapshot)
    all_block_ids = collect_all_block_ids(ctx.project_root)
    issues: list[dict] = []
    seen: set[tuple[str, str]] = set()

    n_skill_dirs = 0
    for skills_dir in skill_dirs:
        for skill_dir in sorted(d for d in skills_dir.iterdir() if d.is_dir()):
            n_skill_dirs += 1
            skill_name = skill_dir.name
            for actions_dir in _iter_skill_action_dirs(skill_dir):
                if not actions_dir.exists():
                    continue
                for action_file in sorted(actions_dir.glob("*.yaml")):
                    key = (skill_name, action_file.name)
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        data = yaml.safe_load(action_file.read_text())
                    except Exception:
                        continue
                    if not isinstance(data, dict):
                        continue

                    rel = str(action_file.relative_to(ctx.project_root))
                    action_id = data.get("id", action_file.stem)

                    # Check page: field
                    page_ref = data.get("page", "")
                    if page_ref and page_ref not in page_routes:
                        issues.append({
                            "type": "stale_page_ref",
                            "action_id": action_id,
                            "file": rel,
                            "page": page_ref,
                            "detail": f"Action '{action_id}' page '{page_ref}' has no matching route",
                        })

                    # Check block: field
                    block_ref = data.get("block", "")
                    if block_ref and block_ref not in all_block_ids:
                        issues.append({
                            "type": "stale_block_ref",
                            "action_id": action_id,
                            "file": rel,
                            "block": block_ref,
                            "detail": f"Action '{action_id}' block '{block_ref}' not declared in any contributions.blocks",
                        })

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} stale reference(s)",
        severity="warning" if issues else "info",
        items_scanned=n_skill_dirs,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    return report_only_fix(ctx, "stale-refs-latest.json", issues, noun="stale reference")

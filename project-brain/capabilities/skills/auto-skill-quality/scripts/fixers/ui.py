"""UI dimension fixer — promote page states and add missing page contributions."""
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

from src.lib.frontmatter_utils import write_frontmatter


def fix_ui(skill_name: str, skill_dir: Path, signals: dict, ctx_info: dict) -> list[str]:
    """Promote page states and add missing page contributions."""
    changes: list[str] = []
    fm = ctx_info.get("fm", {})
    config = fm.get("x-augur-config") or {}
    pages = (config.get("contributions") or {}).get("pages") or []

    if not pages:
        return changes

    modified = False
    for page in pages:
        if not isinstance(page, dict):
            continue

        state = page.get("state", "dev")
        page_path = page.get("path", "")

        # Promote mock -> dev when augur/dashboard/ dir exists with .tsx files
        if state == "mock":
            dashboard_dir = skill_dir / "augur" / "dashboard"
            if dashboard_dir.exists() and any(dashboard_dir.rglob("*.tsx")):
                page["state"] = "dev"
                changes.append(f"promoted {page_path} mock->dev")
                modified = True

        # Promote dev -> mature when data exists and is populated
        elif state == "dev":
            has_data = ctx_info.get("has_data", False)
            if has_data:
                data_dir = skill_dir / "data"
                data_populated = any(
                    f for f in data_dir.iterdir() if f.name != ".gitkeep"
                )
                if data_populated:
                    page["state"] = "mature"
                    changes.append(f"promoted {page_path} dev->mature")
                    modified = True

    if modified:
        skill_md = skill_dir / "SKILL.md"
        body = ctx_info.get("body", "")
        write_frontmatter(skill_md, fm, body)

    return changes

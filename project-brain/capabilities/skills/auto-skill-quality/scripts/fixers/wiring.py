"""Wiring dimension fixer — fix stale toolName refs and remove fs/spawn bypasses."""
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
import re
from pathlib import Path

from src.config.paths import get_project_root


def fix_wiring(skill_name: str, skill_dir: Path, signals: dict, ctx_info: dict) -> list[str]:
    """Fix stale toolName refs and remove fs/spawn bypasses in API routes."""
    changes: list[str] = []
    root = get_project_root()
    api_dir = root / "apps" / "dashboard" / "app" / "api"

    if not api_dir.exists():
        return changes

    # Find API route files that reference this skill
    for ts_file in api_dir.rglob("*.ts"):
        try:
            content = ts_file.read_text(errors="replace")
        except Exception:
            continue

        if skill_name not in content:
            continue

        modified = False

        # Remove fs imports and replace with TODO markers
        if not signals.get("no_fs_bypasses", True):
            new_content = re.sub(
                r'import\s+\{[^}]*\}\s+from\s+["\']fs["\'];?\n?',
                '// TODO_BUG: fs import removed by auto-skill-quality — replace with MCP tool call\n',
                content,
            )
            new_content = re.sub(
                r'import\s+\{[^}]*(?:spawn|execSync|execFile)[^}]*\}\s+from\s+["\']child_process["\'];?\n?',
                '// TODO_BUG: child_process import removed — replace with MCP tool call\n',
                new_content,
            )
            if new_content != content:
                content = new_content
                modified = True
                changes.append(f"removed fs/spawn bypass in {ts_file.name}")

        if modified:
            ts_file.write_text(content)

    return changes

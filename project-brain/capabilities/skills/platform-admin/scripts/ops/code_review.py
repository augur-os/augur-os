"""auto-code-review: Git diff analysis with TypeScript and ESLint checks."""
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
import importlib.util
import sys
from pathlib import Path

# Load sibling module dynamically — .claude/ is not a Python package
_LIB_MOD_NAME = "code_review_lib"
if _LIB_MOD_NAME not in sys.modules:
    _lib_path = Path(__file__).with_name("code_review_lib.py")
    _spec = importlib.util.spec_from_file_location(_LIB_MOD_NAME, str(_lib_path))
    _lib = importlib.util.module_from_spec(_spec)
    sys.modules[_LIB_MOD_NAME] = _lib
    _spec.loader.exec_module(_lib)

from code_review_lib import (
    CODE_REVIEW_DIFFICULTY_SPEC,
    _git_changed_files,
    _git_diff_stat,
    _lint_targets,
    _needs_tsc_check,
    _run_lint_check,
    _run_tsc_check,
    _snapshot_changed_files,
    fix_code_review,
    scan_code_review,
)
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-code-review"
DIFFICULTY_SPEC = CODE_REVIEW_DIFFICULTY_SPEC


def scan(ctx: OpsContext) -> ScanResult:
    return scan_code_review(
        ctx,
        git_changed_files=_git_changed_files,
        git_diff_stat=_git_diff_stat,
        run_tsc_check=_run_tsc_check,
        run_lint_check=_run_lint_check,
        snapshot_changed_files=_snapshot_changed_files,
        needs_tsc_check=_needs_tsc_check,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    return fix_code_review(ctx, issues)

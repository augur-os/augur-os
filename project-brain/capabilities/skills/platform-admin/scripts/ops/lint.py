"""auto-lint: ESLint auto-fix and manual error reporting."""
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
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


def _load_lint_lib():
    module_path = Path(__file__).resolve().with_name("lint_lib.py")
    spec = importlib.util.spec_from_file_location("devops_lint_lib", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_lint_lib = _load_lint_lib()
LINT_DIFFICULTY_SPEC = _lint_lib.LINT_DIFFICULTY_SPEC
fix_lint = _lint_lib.fix_lint
scan_lint = _lint_lib.scan_lint

name = "auto-lint"
DIFFICULTY_SPEC = LINT_DIFFICULTY_SPEC


def scan(ctx: OpsContext) -> ScanResult:
    return scan_lint(ctx)


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    return fix_lint(ctx, issues)

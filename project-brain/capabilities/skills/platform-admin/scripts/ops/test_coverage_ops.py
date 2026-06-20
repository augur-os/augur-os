"""auto-test-coverage: Jest coverage threshold enforcement."""
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


def _load_test_coverage_lib():
    module_path = Path(__file__).resolve().with_name("test_coverage_lib.py")
    spec = importlib.util.spec_from_file_location("devops_test_coverage_lib", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_coverage_lib = _load_test_coverage_lib()
COVERAGE_DIFFICULTY_SPEC = _coverage_lib.COVERAGE_DIFFICULTY_SPEC
COVERAGE_THRESHOLD = _coverage_lib.COVERAGE_THRESHOLD
_run_coverage = _coverage_lib._run_coverage
fix_test_coverage = _coverage_lib.fix_test_coverage
scan_test_coverage = _coverage_lib.scan_test_coverage

name = "auto-test-coverage"
_COVERAGE_THRESHOLD = COVERAGE_THRESHOLD
DIFFICULTY_SPEC = COVERAGE_DIFFICULTY_SPEC


def scan(ctx: OpsContext) -> ScanResult:
    return scan_test_coverage(ctx, run_coverage=_run_coverage)


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    return fix_test_coverage(ctx, issues)

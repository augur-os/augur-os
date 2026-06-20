"""auto-lint: ESLint auto-fix and manual error reporting."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from bootstrap_paths import ensure_project_paths  # noqa: E402

ensure_project_paths(__file__)

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

# Load lib dynamically — .claude/ is not a valid Python package path.
_LIB_MOD_NAME = "lint_lib"
if _LIB_MOD_NAME in sys.modules:
    _lib = sys.modules[_LIB_MOD_NAME]
else:
    _lib_path = Path(__file__).resolve().parents[2] / "platform-admin" / "scripts" / "ops" / "lint_lib.py"
    _spec = importlib.util.spec_from_file_location(_LIB_MOD_NAME, str(_lib_path))
    _lib = importlib.util.module_from_spec(_spec)
    sys.modules[_LIB_MOD_NAME] = _lib
    _spec.loader.exec_module(_lib)

LINT_DIFFICULTY_SPEC = _lib.LINT_DIFFICULTY_SPEC
fix_lint = _lib.fix_lint
scan_lint = _lib.scan_lint

name = "auto-lint"
DIFFICULTY_SPEC = LINT_DIFFICULTY_SPEC


def scan(ctx: OpsContext) -> ScanResult:
    return scan_lint(ctx)


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    return fix_lint(ctx, issues)

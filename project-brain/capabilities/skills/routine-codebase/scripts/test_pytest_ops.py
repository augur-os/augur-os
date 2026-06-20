"""auto-test-pytest: Python test suite runner with hub scoping."""
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
import shutil
import subprocess
import sys
from pathlib import Path
import yaml

from src.config.paths import get_managed_skill_source_dirs
from src.lib.ops_protocol import OpsContext, ScanResult, report_only_fix

name = "auto-test-pytest"

DIFFICULTY_SPEC = {
    0: "Surface check — verify test directories exist",
    1: "Content check — run pytest with default args",
    2: "Deep check — run pytest with verbose output",
    3: "Exhaustive — run pytest with full tracebacks",
    4: "Expert — run pytest with coverage and no timeout cap",
}


def _find_test_dirs(project_root: Path, hub: str | None = None) -> list[Path]:
    test_dirs: list[Path] = []
    for skills_dir in get_managed_skill_source_dirs(project_root):
        if not skills_dir.is_dir():
            continue
        for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            if hub:
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.is_file():
                    continue
                try:
                    text = skill_md.read_text(encoding="utf-8")
                    if not text.startswith("---"):
                        continue
                    end = text.find("---", 3)
                    if end == -1:
                        continue
                    meta = yaml.safe_load(text[3:end]) or {}
                except Exception:
                    continue
                if meta.get("x-augur-hub") != hub:
                    continue
            test_dir = skill_dir / "augur" / "tests"
            if test_dir.is_dir():
                test_dirs.append(test_dir)
    return test_dirs


def _find_python(project_root: Path | None = None) -> str:
    """Find a reliable Python executable path for subprocess calls.

    In daemon contexts, sys.executable may be a bare 'python' that doesn't
    exist on PATH. Prefer the project virtualenv so repo dependencies from
    uv sync are available, then fall back to sys.executable or python3.
    """
    # 1. Project .venv (use absolute path to handle daemon cwd)
    if project_root:
        windows_venv = project_root / ".venv" / "Scripts" / "python.exe"
        if windows_venv.is_file():
            return str(windows_venv)
        venv = project_root / ".venv" / "bin" / "python3"
        if venv.is_file():
            return str(venv)
    # 2. sys.executable if it's a full path that exists
    if sys.executable and Path(sys.executable).is_file():
        return sys.executable
    # 3. which python3
    found = shutil.which("python3")
    if found:
        return found
    # 4. Last resort — always prefer python3 over bare sys.executable
    #    (daemon context may set sys.executable to 'python' which doesn't exist on macOS)
    return "python3"


def _coerce_requested_targets(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _resolve_requested_targets(project_root: Path, requested: list[str]) -> tuple[list[Path | str], list[dict]]:
    targets: list[Path | str] = []
    issues: list[dict] = []
    for raw_target in requested:
        target = raw_target.strip()
        if not target:
            continue
        path_part, separator, node_id = target.partition("::")
        candidate = Path(path_part).expanduser()
        resolved = candidate if candidate.is_absolute() else project_root / candidate
        if not resolved.exists():
            issues.append({"target": target, "error": "Requested pytest target does not exist"})
            continue
        targets.append(f"{resolved}{separator}{node_id}" if separator else resolved)
    return targets, issues


def _run_pytest(
    project_root: Path,
    test_dirs: list[Path | str],
    extra_args: list[str],
    timeout: int,
) -> subprocess.CompletedProcess:
    cmd = [_find_python(project_root), "-m", "pytest"] + [str(d) for d in test_dirs] + extra_args
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, cwd=str(project_root),
    )


def scan(ctx: OpsContext) -> ScanResult:
    hub = ctx.config.get("hub")
    requested_targets = _coerce_requested_targets(
        ctx.config.get("test_paths") or ctx.config.get("smoke_test_paths")
    )
    if requested_targets:
        test_dirs, target_issues = _resolve_requested_targets(ctx.project_root, requested_targets)
        if target_issues:
            return ScanResult(
                issues=target_issues,
                summary="Requested pytest target does not exist",
                severity="error",
            )
    else:
        test_dirs = _find_test_dirs(ctx.project_root, hub=hub)

    if not test_dirs:
        scope = f" for hub '{hub}'" if hub else ""
        return ScanResult(issues=[], summary=f"No test directories found{scope}", severity="info")

    # Test execution is critical — always run at d1+ regardless of difficulty setting.
    effective_difficulty = max(ctx.difficulty, int(ctx.config.get("min_difficulty", 0)))

    # d0: surface check — just confirm test dirs exist, no execution
    if effective_difficulty < 1:
        return ScanResult(
            issues=[], summary=f"{len(test_dirs)} test dir(s) found (d0 surface only)",
            severity="info", health="verified",
        )

    extra_args = ctx.config.get("pytest_args", ["-x", "--tb=short", "-q"])
    timeout = ctx.config.get("pytest_timeout", 300)

    try:
        result = _run_pytest(ctx.project_root, test_dirs, extra_args, timeout)
    except subprocess.TimeoutExpired:
        return ScanResult(
            issues=[{"error": "pytest timed out", "timeout": timeout}],
            summary=f"pytest timed out after {timeout}s",
            severity="error",
        )

    if result.returncode == 0:
        return ScanResult(issues=[], summary=f"All tests passed: {result.stdout.strip()[-80:]}", severity="info")

    return ScanResult(
        issues=[{"error": result.stdout[-2000:], "exit_code": result.returncode, "hub": hub}],
        summary=f"pytest failed (exit {result.returncode})",
        severity="error",
    )


def fix(ctx: OpsContext, issues: list[dict]):
    return report_only_fix(ctx, "test-pytest-latest.json", issues, noun="pytest failure")

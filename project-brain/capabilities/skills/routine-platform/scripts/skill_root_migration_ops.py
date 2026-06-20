"""auto-skill-root-migration: enforce shared/private vault skill root migration."""
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
import os
import re
import subprocess
import sys
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, report_only_fix

name = "auto-skill-root-migration"

_REPORT_NAME = "skill-root-migration-latest.json"
_GUARD_TIMEOUT_SECONDS = 60
_GUARD_ISSUE_RE = re.compile(r"^(?P<file>[^:]+):(?P<line>\d+):\s*(?P<detail>.+)$")


def _guard_script(project_root: Path) -> Path:
    return project_root / "scripts" / "check_skill_root_migration.py"


def _guard_env(project_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    path_entries = [
        str(project_root / "project-brain"),
        str(project_root),
        str(project_root / "src" / "mcp"),
    ]
    current = env.get("PYTHONPATH")
    if current:
        path_entries.append(current)
    env["PYTHONPATH"] = os.pathsep.join(path_entries)
    return env


def _run_guard(project_root: Path) -> subprocess.CompletedProcess[str]:
    script = _guard_script(project_root)
    return subprocess.run(
        [sys.executable, str(script), "--final-contract"],
        cwd=project_root,
        env=_guard_env(project_root),
        capture_output=True,
        text=True,
        timeout=_GUARD_TIMEOUT_SECONDS,
        check=False,
    )


def _make_issue(detail: str, *, file: str = "(migration-contract)", line: int | None = None) -> dict:
    issue = {
        "category": "skill-root-migration",
        "kind": "actionable",
        "file": file,
        "detail": detail,
        "suggestion": "Use managed skill root helpers instead of repo-root skills paths.",
    }
    if line is not None:
        issue["line"] = line
    return issue


def _parse_guard_issues(output: str) -> list[dict]:
    issues: list[dict] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:].strip()
        match = _GUARD_ISSUE_RE.match(body)
        if match:
            issues.append(
                _make_issue(
                    match.group("detail"),
                    file=match.group("file"),
                    line=int(match.group("line")),
                )
            )
        else:
            issues.append(_make_issue(body))
    return issues


def scan(ctx: OpsContext) -> ScanResult:
    """Run the final shared/private vault skill root migration contract."""
    script = _guard_script(ctx.project_root)
    if not script.is_file():
        issue = _make_issue(f"missing migration guard: {script.relative_to(ctx.project_root)}")
        return ScanResult(
            issues=[issue],
            summary="Missing skill root migration guard",
            severity="error",
            health="broken",
        )

    try:
        result = _run_guard(ctx.project_root)
    except subprocess.TimeoutExpired as exc:
        issue = _make_issue(f"migration guard timed out after {exc.timeout} seconds")
        return ScanResult(
            issues=[issue],
            summary="Skill root migration guard timed out",
            severity="error",
            health="broken",
        )
    except OSError as exc:
        issue = _make_issue(f"migration guard failed to run: {exc}")
        return ScanResult(
            issues=[issue],
            summary="Skill root migration guard failed to run",
            severity="error",
            health="broken",
        )

    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    if result.returncode == 0:
        summary = result.stdout.strip() or "skill root migration contract passed"
        return ScanResult(issues=[], summary=summary, severity="info", health="verified")

    issues = _parse_guard_issues(output)
    if not issues:
        issues = [_make_issue(output or f"guard exited with {result.returncode}")]

    return ScanResult(
        issues=issues,
        summary=f"{len(issues)} skill root migration contract violation(s)",
        severity="error",
        health="degraded",
        items_scanned=len(issues),
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    return report_only_fix(ctx, _REPORT_NAME, issues, noun="skill root migration issue")

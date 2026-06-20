"""sync-agents: Detect IDE config drift and regenerate agent configs.
Extracted from /ops-sync (ADR-200).

Scan: runs ``PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents check`` to detect drift
between source rules and generated IDE configs (CLAUDE.md, .cursorrules,
.windsurfrules, etc.).
Fix: runs ``PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync all`` to regenerate
all configs and commits changes.
"""
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
import subprocess
from pathlib import Path

from src.config.paths import get_python_executable
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


name = "sync-agents"


def _commit_files(project_root: Path, message: str, paths: list[str]) -> str | None:
    for p in paths:
        subprocess.run(["git", "add", p], capture_output=True, cwd=str(project_root))
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        return None
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        return rev.stdout.strip() if rev.returncode == 0 else None
    return None


def _sync_command() -> list[str]:
    return [str(get_python_executable()), "-m", "skills.ai.scripts.sync_agents"]


def _sync_env(project_root: Path) -> dict[str, str]:
    """Subprocess env with the project-brain capabilities root on PYTHONPATH.

    The ``skills.ai.scripts.sync_agents`` package resolves from
    ``project-brain/capabilities`` (ADR-770 layout migration). The MCP server
    process already carries this via its generated ``PYTHONPATH``, but a
    subprocess launched from a plain shell / routine would otherwise hit
    ``ModuleNotFoundError: No module named 'skills'``. Mirror brain_init.py and
    the MCP runtime contract so sync works regardless of ambient env.
    """
    env = os.environ.copy()
    roots = [
        str(project_root / "project-brain" / "capabilities"),
        str(project_root),
        str(project_root / "src" / "mcp"),
    ]
    existing = env.get("PYTHONPATH")
    if existing:
        roots.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(roots)
    return env


def scan(ctx: OpsContext) -> ScanResult:
    result = subprocess.run(
        _sync_command() + ["check"],
        capture_output=True,
        text=True,
        cwd=str(ctx.project_root),
        env=_sync_env(ctx.project_root),
    )

    if result.returncode == 0:
        return ScanResult(
            issues=[],
            summary="IDE configs are up to date",
            severity="info",
        )

    drift_output = (result.stderr or result.stdout or "").strip()
    return ScanResult(
        issues=[{"action": "regenerate-ide-configs", "drift_output": drift_output[:500]}],
        summary="IDE config drift detected — regeneration needed",
        severity="warning",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(success=True, summary="Dry run: would regenerate IDE configs")

    result = subprocess.run(
        _sync_command() + ["sync", "all"],
        capture_output=True,
        text=True,
        cwd=str(ctx.project_root),
        env=_sync_env(ctx.project_root),
    )

    if result.returncode != 0:
        return FixResult(success=False, summary=f"sync_agents failed: {result.stderr[:300]}")

    # Stage only known generated files
    generated_patterns = [
        "CLAUDE.md", "AGENTS.md", "CODEX.md",
        ".claude/agents/",
        ".claude/commands/",
        ".claude/mcp.json",
        ".codex/agents/",
        ".codex/prompts/",
        ".codex/skills/",
        ".gemini/",
        ".opencode/",
        "config/agents/",
    ]
    sha = _commit_files(
        ctx.project_root,
        "chore(adaptive): regenerate IDE configs",
        generated_patterns,
    )
    summary = f"IDE configs regenerated (commit {sha})" if sha else "IDE configs regenerated (no changes to commit)"
    return FixResult(success=True, summary=summary, fix_type="code-fix" if sha else "report")

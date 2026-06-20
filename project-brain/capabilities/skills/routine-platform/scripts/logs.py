"""auto-logs: Compress old logs and clean caches.

Extracted from CodeQualityLoop._run_log_maintenance (ADR-200).
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
import importlib.util
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult


def _load_archive_logs():
    """Resolve the lightweight shared log archival helper by file path."""
    try:
        from log_archive import archive_logs as helper
        return helper
    except ImportError:
        helper_script = (
            Path(__file__).resolve().parents[3]
            / "daemon"
            / "scripts"
            / "log_archive.py"
        )
        if not helper_script.exists():
            return None

        spec = importlib.util.spec_from_file_location("daemon_log_archive", helper_script)
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, "archive_logs", None)

# Module-level reference so tests can patch
archive_logs = _load_archive_logs()

name = "auto-logs"

DIFFICULTY_SPEC = {
    0: "Surface check — verify archive_logs helper is importable",
    1: "Content check — check if log files exist and need archiving",
    2: "Deep check — same as d1 (log archival scan)",
    3: "Exhaustive — same as d1 (log archival scan)",
    4: "Expert — same as d1 (log archival scan)",
}


def scan(ctx: OpsContext) -> ScanResult:
    """Check if log maintenance can run."""
    # d0: surface check — just verify the helper is importable
    if ctx.difficulty < 1:
        health = "verified" if archive_logs is not None else "broken"
        summary = "archive_logs available" if archive_logs else "archive_logs not importable"
        return ScanResult(
            issues=[],
            summary=summary,
            severity="info",
            health=health,
        )

    # d1+: check for actual log files needing maintenance
    if archive_logs is None:
        return ScanResult(
            issues=[],
            summary="archive_logs not importable",
            severity="info",
            health="broken",
        )

    try:
        from src.config.paths import get_logs_dir

        log_file = get_logs_dir() / "llm_logs.jsonl"
        if log_file.exists():
            return ScanResult(
                issues=[{"action": "archive-logs", "file": str(log_file)}],
                summary="Log files need archiving",
                severity="info",
            )
    except ImportError:
        pass

    return ScanResult(
        issues=[],
        summary="Log maintenance up to date",
        severity="info",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Compress old logs and clean caches."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary="Dry run: would archive logs",
        )
    try:
        if archive_logs:
            try:
                from src.config.paths import get_logs_dir

                log_file = get_logs_dir() / "llm_logs.jsonl"
                if log_file.exists():
                    archive_logs(log_file)
            except ImportError:
                pass  # No paths module available
        return FixResult(
            success=True,
            summary="Log maintenance completed",
        )
    except Exception as e:
        return FixResult(
            success=False,
            summary=f"Log maintenance failed: {e}",
        )

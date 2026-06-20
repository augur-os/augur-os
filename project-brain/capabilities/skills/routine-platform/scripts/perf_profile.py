"""auto-perf-profile: Performance metric monitoring, IO optimization, and threshold alerting.

Reads state/metrics/perf_metrics.json and flags entries where duration_ms
exceeds known thresholds.  Also scans for disk usage bloat, stale caches,
oversized build artifacts, and state/log accumulation.

Fix generates a timestamped report at state/reports/perf-latest.json.

Thresholds (ms):
  - dashboard-build: 60,000
  - mcp-response: 5,000
  - command-execution: 30,000

IO thresholds (MB):
  - state/backups: 500
  - logs: 50
  - state/coverage: 20
  - state/test-results: 20
  - state/test-ui-screenshots: 20
  - state/garbage_collector: 20
  - state/test-reports: 10
  - state/screenshots: 10
  - apps/dashboard/.next: 400
  - inactive dashboard worktree caches: 1,024

See ADR-200 for the auto-command protocol.
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
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.config.log_retention import LOG_RETENTION
from src.config.paths import get_cache_dir, get_logs_dir, get_project_root, get_runtime_dir
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-perf-profile"
DIFFICULTY_SPEC = {
    0: "Surface check — reuse cached perf report or verify metric/runtime roots exist",
    1: "Content check — scan metrics, IO bloat, stale files, and cache usage",
    2: "Deep check — same as d1 (perf and IO validation)",
    3: "Exhaustive — same as d1 (perf and IO validation)",
    4: "Expert — same as d1 (perf and IO validation)",
}

THRESHOLDS: dict[str, int] = {
    "dashboard-build": 60_000,
    "mcp-response": 5_000,
    "command-execution": 30_000,
}

IO_THRESHOLDS_MB: dict[str, int] = {
    "state/backups": 500,
    "logs": 50,
    "state/coverage": 20,
    "state/test-results": 20,
    "state/test-ui-screenshots": 20,
    "state/garbage_collector": 20,
    "state/test-reports": 10,
    "state/screenshots": 10,
    "apps/dashboard/.next": 400,
}

STALE_DAYS = 3
BACKUP_KEEP_LATEST = 1
DASHBOARD_WORKTREE_CACHE_PREFIX = "dashboard-worktree-"
DASHBOARD_WORKTREE_CACHE_LIMIT_MB = 1024


# ---------------------------------------------------------------------------
# Helpers (patchable in tests)
# ---------------------------------------------------------------------------

def _collect_metrics(project_root: Path) -> list[dict]:
    """Read and return perf_metrics.json entries."""
    del project_root
    metrics_path = get_runtime_dir() / "metrics" / "perf_metrics.json"
    if not metrics_path.exists():
        return []
    data = json.loads(metrics_path.read_text())
    if isinstance(data, list):
        return data
    return data.get("entries", [])


def _resolve_scan_path(project_root: Path, rel_path: str) -> Path:
    """Resolve state/log display paths to their canonical storage root."""
    is_test_root = project_root.resolve() != Path(get_project_root()).resolve()
    if rel_path == "logs":
        return project_root / "logs" if is_test_root else get_logs_dir()
    if rel_path.startswith("state/"):
        suffix = rel_path.removeprefix("state/")
        return project_root / "state" / suffix if is_test_root else get_runtime_dir() / suffix
    return project_root / rel_path


def _next_build_root(project_root: Path) -> Path:
    """Resolve the dashboard build output, following the repo cache symlink."""
    next_path = project_root / "apps" / "dashboard" / ".next"
    if next_path.is_symlink():
        try:
            return next_path.resolve()
        except OSError:
            return next_path
    return next_path


def _get_dir_size_mb(path: Path) -> float:
    """Return total size of a directory in MB."""
    if not path.is_dir():
        return 0.0
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total / (1024 * 1024)


def _get_next_non_dev_size_mb(project_root: Path) -> float:
    """Measure persistent Next output while ignoring the live `.next/dev` worktree."""
    build_root = _next_build_root(project_root)
    if not build_root.is_dir():
        return 0.0

    total = 0
    for path in build_root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(build_root)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] == "dev":
            continue
        total += path.stat().st_size
    return total / (1024 * 1024)


def _count_stale_files(path: Path, days: int) -> int:
    """Count files older than N days in a directory."""
    if not path.is_dir():
        return 0
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
    return sum(1 for f in path.rglob("*") if f.is_file() and f.stat().st_mtime < cutoff)


def _truncate_large_logs(path: Path) -> int:
    """Truncate oversized log files in-place and return reclaimed file count."""
    if not path.is_dir():
        return 0

    max_bytes = int(LOG_RETENTION.max_log_size_mb * 1024 * 1024)
    keep_bytes = int(LOG_RETENTION.keep_log_size_mb * 1024 * 1024)
    reclaimed = 0
    for log_file in path.rglob("*"):
        if not log_file.is_file():
            continue
        if log_file.suffix not in {".log", ".jsonl"}:
            continue
        try:
            size = log_file.stat().st_size
        except OSError:
            continue
        if size <= max_bytes or size <= keep_bytes:
            continue
        try:
            with log_file.open("rb") as handle:
                handle.seek(-keep_bytes, 2)
                tail = handle.read()
            with log_file.open("wb") as handle:
                handle.write(tail)
            reclaimed += 1
        except OSError:
            continue
    return reclaimed


def _dir_size_mb(path: Path) -> float:
    """Return recursive directory size in MB."""
    if not path.exists():
        return 0.0
    if path.is_file():
        try:
            return path.stat().st_size / (1024 * 1024)
        except OSError:
            return 0.0
    total = 0
    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            total += file_path.stat().st_size
        except OSError:
            continue
    return total / (1024 * 1024)


def _pid_is_running(pid: int) -> bool:
    """Return whether a PID exists without signaling it."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _live_next_lock_pid(cache_dir: Path) -> int | None:
    """Return a live Next.js dev-server PID for a dashboard cache, if present."""
    lock_path = cache_dir / "next" / "dev" / "lock"
    if not lock_path.is_file():
        return None
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
        pid = int(data.get("pid", 0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return pid if _pid_is_running(pid) else None


def _get_inactive_dashboard_worktree_cache_stats() -> tuple[int, float]:
    """Return (count, total MB) for inactive external dashboard worktree caches."""
    cache_root = get_cache_dir()
    if not cache_root.is_dir():
        return (0, 0.0)

    count = 0
    total_mb = 0.0
    for cache_dir in sorted(cache_root.glob(f"{DASHBOARD_WORKTREE_CACHE_PREFIX}*")):
        if not cache_dir.is_dir() or cache_dir.is_symlink():
            continue
        if _live_next_lock_pid(cache_dir) is not None:
            continue
        count += 1
        total_mb += _dir_size_mb(cache_dir)
    return count, round(total_mb, 1)


def _prune_manual_backups(path: Path) -> tuple[int, float]:
    """Prune old manual backup directories toward the configured size budget."""
    if not path.is_dir():
        return (0, 0.0)

    candidates = []
    for child in sorted(path.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not child.is_dir():
            continue
        if not child.name.startswith("manual-"):
            continue
        size_mb = _dir_size_mb(child)
        candidates.append((child, size_mb))

    removed = 0
    freed_mb = 0.0
    total_mb = round(sum(size_mb for _, size_mb in candidates), 1)
    target_mb = float(IO_THRESHOLDS_MB["state/backups"])

    for backup_dir, size_mb in reversed(candidates[BACKUP_KEEP_LATEST:]):
        if total_mb <= target_mb:
            break
        shutil.rmtree(backup_dir, ignore_errors=True)
        removed += 1
        freed_mb += size_mb
        total_mb = max(0.0, round(total_mb - size_mb, 1))

    return (removed, round(freed_mb, 1))


def _cached_perf_scan() -> ScanResult | None:
    """Reuse the last perf report for dry-run d0 scans when available."""
    report_path = get_runtime_dir() / "reports" / "perf-latest.json"
    if not report_path.is_file():
        return None

    try:
        report = json.loads(report_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    violations = report.get("violations", [])
    if not isinstance(violations, list):
        violations = []

    normalized: list[dict] = []
    for issue in violations:
        if not isinstance(issue, dict):
            continue
        kind = str(issue.get("kind") or "maintenance")
        normalized.append({"kind": kind, **issue})

    threshold_count = sum(1 for issue in normalized if issue.get("type") == "threshold_exceeded")
    io_count = sum(
        1 for issue in normalized if issue.get("type") in ("disk_bloat", "stale_files", "cache_bloat")
    )
    parts: list[str] = []
    if threshold_count:
        parts.append(f"{threshold_count} metric threshold violation(s)")
    if io_count:
        parts.append(f"{io_count} IO/disk issue(s)")
    summary = ", ".join(parts) if parts else "All performance and IO metrics within thresholds"
    summary += " [cached report]"

    return ScanResult(
        issues=normalized,
        summary=summary,
        severity="warning" if normalized else "info",
        health="degraded" if normalized else "verified",
    )


# ---------------------------------------------------------------------------
# Protocol implementation
# ---------------------------------------------------------------------------

def scan(ctx: OpsContext) -> ScanResult:
    """Scan for performance metrics exceeding thresholds and IO bloat."""
    if ctx.dry_run and ctx.difficulty < 1:
        cached = _cached_perf_scan()
        if cached is not None:
            return cached
        metrics_path = get_runtime_dir() / "metrics" / "perf_metrics.json"
        return ScanResult(
            issues=[],
            summary=(
                "perf metrics cache available (d0 surface)"
                if metrics_path.exists()
                else "perf metrics cache missing (d0 surface)"
            ),
            severity="info",
            health="verified",
        )

    issues: list[dict] = []

    # --- Duration threshold checks ---
    metrics = _collect_metrics(ctx.project_root)
    for entry in metrics:
        metric_type = entry.get("type", "")
        duration = entry.get("duration_ms", 0)
        threshold = THRESHOLDS.get(metric_type)
        if threshold is not None and duration > threshold:
            issues.append({
                "type": "threshold_exceeded",
                "kind": "actionable",
                "root_cause_type": "repo_bug",
                "metric": metric_type,
                "duration_ms": duration,
                "threshold_ms": threshold,
                "overage_ms": duration - threshold,
            })

    # --- IO / disk usage checks ---
    for rel_path, limit_mb in IO_THRESHOLDS_MB.items():
        if rel_path == "apps/dashboard/.next":
            size_mb = _get_next_non_dev_size_mb(ctx.project_root)
        else:
            abs_path = _resolve_scan_path(ctx.project_root, rel_path)
            size_mb = _get_dir_size_mb(abs_path)
        if size_mb > limit_mb:
            issues.append({
                "type": "disk_bloat",
                "kind": "maintenance",
                "root_cause_type": "generated_artifact",
                "path": rel_path,
                "size_mb": round(size_mb, 1),
                "threshold_mb": limit_mb,
                "overage_mb": round(size_mb - limit_mb, 1),
            })

    # --- Stale file accumulation ---
    stale_dirs = ["logs", "state/test-results", "state/coverage",
                  "state/test-ui-screenshots", "state/test-reports"]
    for rel_path in stale_dirs:
        abs_path = _resolve_scan_path(ctx.project_root, rel_path)
        stale_count = _count_stale_files(abs_path, STALE_DAYS)
        if stale_count > 10:
            issues.append({
                "type": "stale_files",
                "kind": "maintenance",
                "root_cause_type": "generated_artifact",
                "path": rel_path,
                "stale_count": stale_count,
                "age_days": STALE_DAYS,
            })

    # --- Build cache check ---
    next_cache = _next_build_root(ctx.project_root) / "cache"
    if next_cache.is_dir():
        cache_mb = _get_dir_size_mb(next_cache)
        if cache_mb > 150:
            issues.append({
                "type": "cache_bloat",
                "kind": "maintenance",
                "root_cause_type": "generated_artifact",
                "path": "apps/dashboard/.next/cache",
                "size_mb": round(cache_mb, 1),
                "threshold_mb": 300,
            })

    inactive_worktree_count, inactive_worktree_cache_mb = _get_inactive_dashboard_worktree_cache_stats()
    if inactive_worktree_cache_mb > DASHBOARD_WORKTREE_CACHE_LIMIT_MB:
        issues.append({
            "type": "cache_bloat",
            "kind": "maintenance",
            "root_cause_type": "generated_artifact",
            "path": "get_cache_dir()/dashboard-worktree-*",
            "size_mb": inactive_worktree_cache_mb,
            "threshold_mb": DASHBOARD_WORKTREE_CACHE_LIMIT_MB,
            "inactive_cache_count": inactive_worktree_count,
            "stale_cache_count": inactive_worktree_count,
            "recommendation": "Run /dev-clean to purge inactive dashboard worktree caches",
        })

    severity = "warning" if issues else "info"
    # Summarize by category
    threshold_count = sum(1 for i in issues if i["type"] == "threshold_exceeded")
    io_count = sum(1 for i in issues if i["type"] in ("disk_bloat", "stale_files", "cache_bloat"))
    parts = []
    if threshold_count:
        parts.append(f"{threshold_count} metric threshold violation(s)")
    if io_count:
        parts.append(f"{io_count} IO/disk issue(s)")
    summary = ", ".join(parts) if parts else "All performance and IO metrics within thresholds"

    return ScanResult(issues=issues, summary=summary, severity=severity)


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Generate a performance report and clean up stale files."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            actions=[{"action": "dry_run", "description": "Would generate perf report and clean stale files"}],
            summary="Dry run — no changes made",
        )

    actions: list[dict] = []
    changes: list[str] = []

    # --- Clean stale files ---
    for issue in issues:
        if issue["type"] == "stale_files":
            abs_path = _resolve_scan_path(ctx.project_root, issue["path"])
            cutoff = datetime.now(timezone.utc).timestamp() - (STALE_DAYS * 86400)
            removed = 0
            for f in abs_path.rglob("*"):
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            # Clean empty dirs left behind (skip symlinks)
            for d in sorted(abs_path.rglob("*"), reverse=True):
                if d.is_dir() and not d.is_symlink() and not any(d.iterdir()):
                    d.rmdir()
            if removed:
                actions.append({"action": "clean_stale", "path": issue["path"], "removed": removed})
                changes.append(f"Removed {removed} stale file(s) from {issue['path']}")

    # --- Purge Next.js cache if bloated ---
    for issue in issues:
        if issue["type"] == "cache_bloat" and issue.get("path") == "apps/dashboard/.next/cache":
            cache_path = _next_build_root(ctx.project_root) / "cache"
            if cache_path.is_dir():
                shutil.rmtree(cache_path)
                actions.append({"action": "purge_cache", "path": issue["path"], "size_mb": issue["size_mb"]})
                changes.append(f"Purged {issue['size_mb']}MB build cache at {issue['path']}")

        if issue["type"] == "disk_bloat" and issue["path"] == "apps/dashboard/.next":
            build_root = _next_build_root(ctx.project_root)
            if build_root.is_dir():
                shutil.rmtree(build_root)
                actions.append({"action": "purge_next_build", "path": issue["path"], "size_mb": issue["size_mb"]})
                changes.append(f"Purged {issue['size_mb']}MB Next.js build output at {issue['path']}")
        if issue["type"] == "disk_bloat" and issue["path"] == "logs":
            logs_dir = _resolve_scan_path(ctx.project_root, issue["path"])
            truncated = _truncate_large_logs(logs_dir)
            if truncated:
                actions.append({"action": "truncate_logs", "path": issue["path"], "count": truncated})
                changes.append(f"Truncated {truncated} oversized log file(s) in {issue['path']}")
        if issue["type"] == "disk_bloat" and issue["path"] == "state/backups":
            backup_dir = _resolve_scan_path(ctx.project_root, issue["path"])
            removed, freed_mb = _prune_manual_backups(backup_dir)
            if removed:
                actions.append({
                    "action": "prune_backups",
                    "path": issue["path"],
                    "removed": removed,
                    "freed_mb": freed_mb,
                })
                changes.append(f"Pruned {removed} manual backup dir(s) from {issue['path']} ({freed_mb} MB)")

    # --- Generate report ---
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "thresholds": THRESHOLDS,
        "io_thresholds_mb": IO_THRESHOLDS_MB,
        "violations": [
            {k: v for k, v in i.items()}
            for i in issues
        ],
        "count": len(issues),
        "cleanup_actions": len(actions),
    }
    report_dir = _resolve_scan_path(ctx.project_root, "state/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "perf-latest.json"
    report_path.write_text(json.dumps(report, indent=2))
    actions.append({"action": "generate_report", "path": str(report_path)})

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=f"Generated perf report with {len(issues)} issue(s), {len(changes)} cleanup action(s)",
        fix_type="code-fix" if changes else "report",
    )

#!/usr/bin/env python3
"""
Cleanup Collateral Script
Deletes or archives old artifacts to keep the system clean.
Supports deep cleanup of caches, log truncation, and root directory enforcement.

Retention settings are centralized in src/lib/config/log_retention.py
"""

import os
import sys
import time
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path for imports
from bootstrap_paths import ensure_project_paths  # noqa: E402

project_root = ensure_project_paths(__file__)

from src.config.paths import get_project_root, get_python_executable, get_runtime_dir
from src.lib.repo_hygiene import is_allowed_root_item


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))

try:
    from src.config.log_retention import LOG_RETENTION
except ImportError as e:
    from src.logging.self_heal_event import emit_heal_event

    emit_heal_event(
        source="cleanup_collateral",
        category="import_failure",
        severity="high",
        message=f"Cannot import LOG_RETENTION: {e}",
        context={"expected_module": "src.config.log_retention"},
    )
    raise

RETENTION_POLICIES = {
    "chain-executions": LOG_RETENTION.chain_executions_days,
    "retrospectives": LOG_RETENTION.retrospectives_days,
    "tasks-completed": LOG_RETENTION.tasks_completed_days,
}
MAX_LOG_SIZE_MB = LOG_RETENTION.max_log_size_mb
KEEP_LOG_SIZE_MB = LOG_RETENTION.keep_log_size_mb

# Deep Cleanup Targets (Recursive)
CACHE_DIRS = ["__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".DS_Store"]
TEMP_FILES = [".DS_Store", "*.tmp", "*.bak", "*.swp"]

# Data Repo Whitelist (updated for monorepo - data/ is now inside augur/)
# Data directory contains plugin data organized by bundle/skill
ALLOWED_DATA_ROOT_ITEMS = {
    # Plugin bundle data directories
    "ai-bridge",
    "terminal-automation-template",
    "capture",
    "career",
    "channels",
    "content",
    "core",  # Core runtime data
    "dev",
    "daemon",
    "smb-client-template",
    "consulting-template",
    "eisenhower",
    "enterprise",
    "factory",
    "finance",
    "health",
    "home",
    "icloud",
    "ideas",
    "knowledge",
    "lifestyle",
    "file-manager",
    "platform",
    "runtime",  # Runtime logs/cache
    "scraper",
    "venture",
    # Config and meta
    "config",
    ".DS_Store",
    # Files
    "README.md",
}


def get_file_age_days(file_path: Path) -> float:
    """Return the age of the file in days."""
    return (time.time() - file_path.stat().st_mtime) / (24 * 3600)


def cleanup_directory(directory: Path, days: int, dry_run: bool = False) -> dict:
    """
    Remove files in directory older than 'days'.
    Returns stats on deleted files and space reclaimed.
    """
    stats = {"deleted": 0, "space_reclaimed_mb": 0.0, "errors": 0}

    if not directory.exists():
        return stats

    _out(f"🧹 Scanning {directory} (Threshold: >{days} days)...")

    files = [f for f in directory.rglob("*") if f.is_file()]

    for file_path in files:
        try:
            age = get_file_age_days(file_path)
            if age > days:
                size_mb = file_path.stat().st_size / (1024 * 1024)

                if dry_run:
                    _out(f"  [DRY RUN] Would delete: {file_path.name} ({age:.1f} days old, {size_mb:.2f} MB)")
                else:
                    file_path.unlink()
                    _out(f"  🗑️  Deleted: {file_path.name}")

                stats["deleted"] += 1
                stats["space_reclaimed_mb"] += size_mb
        except Exception:
            stats["errors"] += 1

    return stats


def deep_clean_caches(base_path: Path, dry_run: bool = False) -> dict:
    """Recursively delete cache directories and temp files."""
    stats = {"deleted_dirs": 0, "deleted_files": 0, "space_reclaimed_mb": 0.0}

    _out(f"🧽 Deep Cleaning Caches in {base_path}...")

    # 1. Remove Cache Directories
    for cache_name in CACHE_DIRS:
        for found_dir in base_path.rglob(cache_name):
            if found_dir.is_dir():
                size_mb = 0
                for f in found_dir.rglob("*"):
                    if f.is_file():
                        size_mb += f.stat().st_size
                size_mb /= 1024 * 1024

                if dry_run:
                    _out(f"  [DRY RUN] Would remove dir: {found_dir} ({size_mb:.2f} MB)")
                else:
                    shutil.rmtree(found_dir)
                    _out(f"  🗑️  Removed dir: {found_dir}")

                stats["deleted_dirs"] += 1
                stats["space_reclaimed_mb"] += size_mb

    # 2. Remove Temp Files
    for pattern in TEMP_FILES:
        for found_file in base_path.rglob(pattern):
            if found_file.is_file():
                size_mb = found_file.stat().st_size / (1024 * 1024)
                if dry_run:
                    _out(f"  [DRY RUN] Would delete file: {found_file} ({size_mb:.2f} MB)")
                else:
                    found_file.unlink()
                    _out(f"  🗑️  Deleted file: {found_file}")

                stats["deleted_files"] += 1
                stats["space_reclaimed_mb"] += size_mb

    return stats


def truncate_logs(base_path: Path, dry_run: bool = False) -> dict:
    """Truncate large log files."""
    stats = {"truncated": 0, "space_reclaimed_mb": 0.0}

    _out(f"✂️  Scanning for large logs (> {MAX_LOG_SIZE_MB}MB) in {base_path}...")

    for log_file in base_path.rglob("*.log"):
        if log_file.is_file():
            size_mb = log_file.stat().st_size / (1024 * 1024)
            if size_mb > MAX_LOG_SIZE_MB:
                reclaim_mb = size_mb - KEEP_LOG_SIZE_MB
                if dry_run:
                    _out(f"  [DRY RUN] Would truncate: {log_file.name} ({size_mb:.2f} MB -> {KEEP_LOG_SIZE_MB} MB)")
                else:
                    # Keep only the last 1MB bytes
                    keep_bytes = int(KEEP_LOG_SIZE_MB * 1024 * 1024)
                    with open(log_file, "rb") as f:
                        f.seek(-keep_bytes, 2)
                        content = f.read()
                    with open(log_file, "wb") as f:
                        f.write(content)
                    _out(f"  ✂️  Truncated: {log_file.name}")

                stats["truncated"] += 1
                stats["space_reclaimed_mb"] += reclaim_mb

    return stats


def enforce_root_structure(project_root: Path, whitelist: set | None, dry_run: bool = False) -> dict:
    """Move unauthorized files/dirs from root using LLM-powered routing (ADR-135).

    For non-whitelisted items, calls classify_collateral.py first to intelligently
    route work product to the correct skill assets dir. Falls back to _archive for
    unclassifiable files. Direct archive is used as a last resort.
    """
    stats = {"moved": 0, "space_reclaimed_mb": 0.0}

    # Prepare Archive Dir (fallback only)
    archive_dir = project_root / ".agent" / "archive" / datetime.now().strftime("%Y%m%d_%H%M%S")

    _out(f"🏗️  Enforcing Root Structure in {project_root}...")

    # Collect non-whitelisted items first
    stray_items = []
    for item in project_root.iterdir():
        name = item.name

        # Canonical repo-root rules are prefix/suffix based, not just a flat set.
        if whitelist is None:
            if is_allowed_root_item(name):
                continue
        elif name in whitelist:
            continue

        if whitelist is not None and (name.endswith(".md") or name.endswith(".txt") or name.startswith("augur")):
            continue

        stray_items.append(item)

    if not stray_items:
        return stats

    # Try LLM-powered routing via classify_collateral.py (ADR-135)
    classify_script = project_root / "src" / "scripts" / "classify_collateral.py"
    llm_routing_done = False

    if classify_script.exists() and not dry_run:
        import subprocess  # nosec B404
        try:
            cmd = [
                str(get_python_executable()),
                str(classify_script),
                "--root-dir", str(project_root),
                "--verbose",
            ]
            result = subprocess.run(  # nosec B603
                cmd,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=90,
                encoding="utf-8",
            )
            if result.returncode == 0:
                _out("  ✅ LLM collateral routing complete:")
                for line in result.stdout.splitlines():
                    if "[classify]" in line:
                        _out(f"    {line}")
                llm_routing_done = True
                # Count routed items
                stats["moved"] = sum(
                    1 for line in result.stdout.splitlines()
                    if "Routed:" in line or "Archived:" in line
                )
            else:
                _out(f"  ⚠️  classify_collateral.py failed (rc={result.returncode}), falling back to direct archive")
                if result.stderr:
                    _out(f"    stderr: {result.stderr[:500]}")
        except Exception as e:
            _out(f"  ⚠️  classify_collateral.py error: {e}, falling back to direct archive")
    elif dry_run and classify_script.exists():
        cmd = [
            str(get_python_executable()),
            str(classify_script),
            "--root-dir", str(project_root),
            "--dry-run",
            "--verbose",
        ]
        import subprocess  # nosec B404
        try:
            result = subprocess.run(  # nosec B603
                cmd,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=90,
                encoding="utf-8",
            )
            for line in result.stdout.splitlines():
                _out(f"  {line}")
            llm_routing_done = True
            stats["moved"] = len(stray_items)
        except Exception as e:
            _out(f"  ⚠️  classify_collateral.py dry-run error: {e}")

    # Fallback: direct archive for items that weren't routed by LLM
    if not llm_routing_done:
        for item in stray_items:
            name = item.name
            size_mb = 0
            if item.is_file():
                size_mb = item.stat().st_size / (1024 * 1024)
            elif item.is_dir():
                for f in item.rglob("*"):
                    if f.is_file():
                        size_mb += f.stat().st_size
                size_mb /= 1024 * 1024

            if dry_run:
                _out(f"  [DRY RUN] Would quarantine: {name} ({size_mb:.2f} MB)")
            else:
                if not archive_dir.exists():
                    archive_dir.mkdir(parents=True, exist_ok=True)
                dest = archive_dir / name
                shutil.move(str(item), str(dest))
                _out(f"  📦 Quarantined: {name} -> {dest}")

            stats["moved"] += 1

    return stats


def prune_archive(base_path: Path, dry_run: bool = False) -> float:
    """Cleanup the archive folder itself."""
    reclaimed = 0.0
    archive_dir = base_path / ".agent" / "archive"
    if archive_dir.exists():
        days = RETENTION_POLICIES.get("archive", 30)
        stats = cleanup_directory(archive_dir, days, dry_run)
        reclaimed += stats["space_reclaimed_mb"]

        # Prune empty dirs
        if not dry_run:
            for item in archive_dir.iterdir():
                if item.is_dir() and not any(item.iterdir()):
                    item.rmdir()
    return reclaimed


def main():
    parser = argparse.ArgumentParser(description="Clean up old system collateral.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate deletion")
    parser.add_argument("--days", type=int, help="Override default retention days")

    # Allow arbitrary args to be ignored (orchestrator compatibility)
    args, _ = parser.parse_known_args()

    data_dir = os.environ.get("AUGUR_ROOT", str(get_project_root()))
    project_root = get_project_root()
    base_path = Path(data_dir)

    _out("🚀 Starting Extended System Cleanup")
    _out(f"   Mode: {'DRY RUN' if args.dry_run else 'LIVE DELETION'}")

    total_reclaimed = 0.0

    # 1. Chain Executions (Data Repo)
    exec_dir = get_runtime_dir() / "chain-executions"
    days = args.days if args.days else RETENTION_POLICIES["chain-executions"]
    stats = cleanup_directory(exec_dir, days, args.dry_run)
    total_reclaimed += stats["space_reclaimed_mb"]

    # 2. Retrospectives (Data Repo)
    retro_dir = base_path / "plugins" / "dev" / "skills" / "frontend" / "data" / "retrospectives"

    days = args.days if args.days else RETENTION_POLICIES["retrospectives"]

    stats = cleanup_directory(retro_dir, days, args.dry_run)
    total_reclaimed += stats["space_reclaimed_mb"]

    # 3. Completed Tasks (Data Repo)
    tasks_dir = base_path / "plugins" / "core" / "skills" / "executor" / "data" / "agent-tasks" / "completed"
    days = args.days if args.days else RETENTION_POLICIES["tasks-completed"]
    stats = cleanup_directory(tasks_dir, days, args.dry_run)
    total_reclaimed += stats["space_reclaimed_mb"]

    # 4. Deep Cleanup (Caches) - Both Repos
    stats = deep_clean_caches(project_root, args.dry_run)
    total_reclaimed += stats["space_reclaimed_mb"]

    stats = deep_clean_caches(base_path, args.dry_run)
    total_reclaimed += stats["space_reclaimed_mb"]

    # 5. Log Truncation - Both Repos
    stats = truncate_logs(project_root, args.dry_run)
    total_reclaimed += stats["space_reclaimed_mb"]

    # 6. Root Structure Enforcement
    # Main Repo
    enforce_root_structure(project_root, None, args.dry_run)
    # Data Repo
    enforce_root_structure(base_path, ALLOWED_DATA_ROOT_ITEMS, args.dry_run)

    # 7. Cleanup Archive Itself - Both Repos
    total_reclaimed += prune_archive(project_root, args.dry_run)
    total_reclaimed += prune_archive(base_path, args.dry_run)

    _out("-" * 50)
    _out("✅ Extended Cleanup Complete.")
    _out(f"   Space Reclaimed: {total_reclaimed:.2f} MB")


if __name__ == "__main__":
    main()

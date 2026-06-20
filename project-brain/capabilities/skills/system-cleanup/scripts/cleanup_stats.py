#!/usr/bin/env python3
"""System health stats and disk-waste category size estimates. Read-only.

Reports CPU load, memory pressure, disk usage, uptime, and an estimated size
per cleanup category — the pre-cleanup overview the /cleanup command presents
before any scan or confirmation.

Usage:
    uv run python cleanup_stats.py
    uv run python cleanup_stats.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cleanup_common import (  # noqa: E402
    CATEGORY_PATHS,
    DEV_ARTIFACT_NAMES,
    DEV_SCAN_ROOTS,
    LARGE_FILE_SCAN_DIRS,
    LARGE_FILE_THRESHOLD,
    dir_size_fast,
    format_bytes,
    iso_now,
    walk_limited,
)


def gather_system_stats() -> dict:
    """Gather CPU, memory, disk, and uptime stats (macOS, Linux fallback)."""
    import time

    stats: dict = {}

    # CPU — load average as a usage proxy
    try:
        cpu_count = os.cpu_count() or 1
        load1, _, _ = os.getloadavg()
        cpu_usage = min(100.0, (load1 / cpu_count) * 100)
        stats["cpu"] = {"usage": round(cpu_usage, 1), "cores": cpu_count}
    except (OSError, AttributeError):
        stats["cpu"] = {"usage": 0, "cores": os.cpu_count() or 1}

    # Memory — vm_stat on macOS, /proc/meminfo on Linux
    try:
        if sys.platform == "darwin":
            result = subprocess.run(  # nosec B603
                ["/usr/bin/vm_stat"], capture_output=True, text=True, timeout=5,
            )
            page_size = 16384  # Apple Silicon default
            ps_result = subprocess.run(  # nosec B603
                ["/usr/sbin/sysctl", "-n", "hw.pagesize"],
                capture_output=True, text=True, timeout=5,
            )
            if ps_result.returncode == 0:
                page_size = int(ps_result.stdout.strip())

            vm: dict[str, int] = {}
            for line in result.stdout.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    val = val.strip().rstrip(".")
                    try:
                        vm[key.strip()] = int(val)
                    except ValueError:
                        pass

            used_pages = (
                vm.get("Pages active", 0)
                + vm.get("Pages wired down", 0)
                + vm.get("Pages occupied by compressor", 0)
            )
            used_bytes = used_pages * page_size

            mem_result = subprocess.run(  # nosec B603
                ["/usr/sbin/sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5,
            )
            total_bytes = int(mem_result.stdout.strip()) if mem_result.returncode == 0 else 0

            if total_bytes > 0:
                stats["memory"] = {
                    "used": used_bytes,
                    "total": total_bytes,
                    "percent": round((used_bytes / total_bytes) * 100, 1),
                }
            else:
                stats["memory"] = {"used": 0, "total": 0, "percent": 0}
        else:
            with open("/proc/meminfo") as f:
                meminfo: dict[str, int] = {}
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        meminfo[key] = int(val) * 1024
            total = meminfo.get("MemTotal", 0)
            available = meminfo.get("MemAvailable", 0)
            used = total - available
            stats["memory"] = {
                "used": used,
                "total": total,
                "percent": round((used / total) * 100, 1) if total > 0 else 0,
            }
    except Exception:
        stats["memory"] = {"used": 0, "total": 0, "percent": 0}

    # Disk
    try:
        disk = shutil.disk_usage("/")
        stats["disk"] = {
            "used": disk.used,
            "total": disk.total,
            "percent": round((disk.used / disk.total) * 100, 1) if disk.total > 0 else 0,
            "path": "/",
        }
    except Exception:
        stats["disk"] = {"used": 0, "total": 0, "percent": 0, "path": "/"}

    # Uptime
    try:
        if sys.platform == "darwin":
            result = subprocess.run(  # nosec B603
                ["/usr/sbin/sysctl", "-n", "kern.boottime"],
                capture_output=True, text=True, timeout=5,
            )
            import re
            match = re.search(r"sec\s*=\s*(\d+)", result.stdout)
            if match:
                uptime_secs = int(time.time()) - int(match.group(1))
            else:
                uptime_secs = -1
        else:
            with open("/proc/uptime") as f:
                uptime_secs = int(float(f.read().split()[0]))
        if uptime_secs >= 0:
            days = uptime_secs // 86400
            hours = (uptime_secs % 86400) // 3600
            minutes = (uptime_secs % 3600) // 60
            secs = uptime_secs % 60
            if days > 0:
                stats["uptime"] = (
                    f"{days} day{'s' if days != 1 else ''}, {hours}:{minutes:02d}:{secs:02d}"
                )
            else:
                stats["uptime"] = f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            stats["uptime"] = "unknown"
    except Exception:
        stats["uptime"] = "unknown"

    stats["timestamp"] = iso_now()
    return stats


def gather_category_sizes(
    category_paths: dict[str, list[str]] | None = None,
    dev_scan_roots: list[str] | None = None,
    large_file_dirs: list[str] | None = None,
) -> list[dict]:
    """Estimate total size for each cleanup category. Read-only."""
    import glob as globmod

    paths_config = category_paths if category_paths is not None else CATEGORY_PATHS

    results = []
    for cat_id, patterns in paths_config.items():
        total_size = 0
        total_items = 0
        for pattern in patterns:
            expanded = os.path.expanduser(pattern)
            if "*" in expanded or "?" in expanded:
                for match in globmod.glob(expanded):
                    size, count = dir_size_fast(Path(match))
                    total_size += size
                    total_items += count
            else:
                p = Path(expanded)
                if p.exists():
                    size, count = dir_size_fast(p)
                    total_size += size
                    total_items += count
        results.append({"id": cat_id, "size": total_size, "itemCount": total_items})

    dev_size, dev_count = _estimate_dev_artifacts(dev_scan_roots)
    results.append({"id": "dev-artifacts", "size": dev_size, "itemCount": dev_count})

    large_size, large_count = _estimate_large_files(large_file_dirs)
    results.append({"id": "large-files", "size": large_size, "itemCount": large_count})

    return results


def _estimate_dev_artifacts(scan_roots: list[str] | None = None) -> tuple[int, int]:
    """Quick estimate of dev artifact sizes by scanning known project roots."""
    total_size = 0
    total_count = 0
    for root_pattern in (scan_roots if scan_roots is not None else DEV_SCAN_ROOTS):
        root = Path(os.path.expanduser(root_pattern))
        if not root.is_dir():
            continue
        for item in walk_limited(root, max_depth=3):
            if item.name in DEV_ARTIFACT_NAMES and item.is_dir():
                size, _ = dir_size_fast(item)
                total_size += size
                total_count += 1
    return total_size, total_count


def _estimate_large_files(scan_dirs: list[str] | None = None) -> tuple[int, int]:
    """Quick estimate of large files in common directories."""
    total_size = 0
    total_count = 0
    for dir_pattern in (scan_dirs if scan_dirs is not None else LARGE_FILE_SCAN_DIRS):
        d = Path(os.path.expanduser(dir_pattern))
        if not d.is_dir():
            continue
        try:
            for entry in d.rglob("*"):
                try:
                    if entry.is_file() and entry.stat().st_size >= LARGE_FILE_THRESHOLD:
                        total_size += entry.stat().st_size
                        total_count += 1
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            continue
    return total_size, total_count


def _print_human(payload: dict) -> None:
    system = payload["system"]
    cpu = system.get("cpu", {})
    mem = system.get("memory", {})
    disk = system.get("disk", {})
    print(f"cpu:    {cpu.get('usage', 0)}% load ({cpu.get('cores', '?')} cores)")
    print(f"memory: {format_bytes(mem.get('used', 0))} / "
          f"{format_bytes(mem.get('total', 0))} ({mem.get('percent', 0)}%)")
    print(f"disk:   {format_bytes(disk.get('used', 0))} / "
          f"{format_bytes(disk.get('total', 0))} ({disk.get('percent', 0)}% of /)")
    print(f"uptime: {system.get('uptime', 'unknown')}")
    print()
    print("cleanup categories (estimated):")
    for cat in sorted(payload["categories"], key=lambda c: c["size"], reverse=True):
        print(f"  {format_bytes(cat['size']):>10}  {cat['id']} "
              f"({cat['itemCount']} items)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="System health stats and cleanup category size estimates "
                    "(read-only).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--skip-estimates", action="store_true",
                        help="Skip category size estimation (system stats only)")
    args = parser.parse_args(argv)

    payload = {
        "system": gather_system_stats(),
        "categories": [] if args.skip_estimates else gather_category_sizes(),
        "timestamp": iso_now(),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_human(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Real-data verification of dashboard worktree toolchain sharing.

Run from the main checkout:
    uv run --python 3.12 python scripts/verify_worktree_toolchain.py

Creates a throwaway worktree, runs preflight repair, measures hardlink
count and disk delta, then tears the worktree down. Prints evidence to
stdout for inclusion in merge commits.

Does NOT mutate main, does NOT push, does NOT touch any persistent state.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _is_windows() -> bool:
    """Windows detection seam. Tests patch THIS (not the global os.name) so that
    simulating Windows never mutates os.name globally — mutating os.name makes
    pathlib.Path() construct WindowsPath, which raises on non-Windows runners and
    leaks into unrelated fixture teardowns under CI collection order."""
    return os.name == "nt"


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _resolve_main_checkout() -> Path:
    """Return the main checkout path even when run from a linked worktree.

    Uses `git rev-parse --git-common-dir` (which resolves to <main>/.git for both main
    and linked worktrees) and returns its parent. Falls back to PROJECT_ROOT.
    """
    try:
        common_dir = subprocess.check_output(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "--git-common-dir"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return PROJECT_ROOT
    common_path = (
        (PROJECT_ROOT / common_dir).resolve()
        if not os.path.isabs(common_dir)
        else Path(common_dir).resolve()
    )
    if common_path.name == ".git":
        return common_path.parent
    return PROJECT_ROOT


def _df_kb(path: Path) -> int:
    """Return free space in KB on the volume containing path."""
    if _is_windows():
        return shutil.disk_usage(path).free // 1024
    stat = os.statvfs(path)
    return (stat.f_bavail * stat.f_frsize) // 1024


def _file_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.rglob("*") if _.is_file())


def _hardlinked_file_count(path: Path) -> int:
    """Count files with st_nlink > 1 — meaningful for the pnpm-install path only.

    Note: APFS/btrfs/ReFS CoW clones share disk blocks but each file keeps st_nlink=1.
    For clone-path validation, use _du_apparent_minus_actual() instead.
    """
    if not path.exists():
        return 0
    count = 0
    for entry in path.rglob("*"):
        try:
            if entry.is_file() and entry.stat().st_nlink > 1:
                count += 1
        except OSError:
            continue
    return count


def _du_apparent_mb(path: Path) -> int:
    """Apparent size (sum of file lengths) in MB via `du -A -k -s`."""
    if not path.exists():
        return 0
    try:
        out = subprocess.check_output(
            ["du", "-A", "-k", "-s", str(path)], text=True
        ).strip().split()
        return int(out[0]) // 1024
    except (subprocess.CalledProcessError, OSError, ValueError, IndexError):
        return 0


def _du_actual_mb(path: Path) -> int:
    """Disk-block-allocated size in MB via `du -k -s` (counts CoW-shared blocks once)."""
    if not path.exists():
        return 0
    try:
        out = subprocess.check_output(
            ["du", "-k", "-s", str(path)], text=True
        ).strip().split()
        return int(out[0]) // 1024
    except (subprocess.CalledProcessError, OSError, ValueError, IndexError):
        return 0


def _preflight_time_limit_ms() -> int:
    """Return the platform-appropriate verifier time budget."""
    return 120000 if _is_windows() else 60000


def _volume_delta_limit_mb() -> int:
    """Return tolerated transient disk overhead while the throwaway worktree exists."""
    # Windows hardlink materialization still pays for deep directory metadata,
    # command shims, and non-hardlinked package files. The hardlink percentage is
    # the sharing signal; this limit catches runaway copies without failing a
    # healthy pnpm-install path.
    return 700 if _is_windows() else 200


def _remove_tree(path: Path) -> None:
    """Remove a throwaway tree, including read-only files left by git worktree add."""
    if not path.exists():
        return

    def _retry_writable(func, value, _exc_info) -> None:
        target = Path(value)
        try:
            target.chmod(stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
        except OSError:
            pass
        func(value)

    target: Path | str = path
    if _is_windows():
        resolved = str(path.resolve())
        if not resolved.startswith("\\\\?\\"):
            target = "\\\\?\\" + resolved

    shutil.rmtree(target, onerror=_retry_writable)
    if path.exists():
        raise RuntimeError(f"failed to remove throwaway worktree: {path}")


def main() -> int:
    main_wt = _resolve_main_checkout()
    main_node_modules = main_wt / "apps" / "dashboard" / "node_modules"

    if not (main_node_modules / ".bin" / "next").exists():
        print(
            f"ERROR: main worktree {main_wt} has no apps/dashboard/node_modules. "
            "Run `pnpm install` in main first.",
            file=sys.stderr,
        )
        return 1

    throwaway_name = f"toolchain-verify-{int(time.time())}"
    throwaway_path = main_wt / ".worktrees" / f"augur-verify-{throwaway_name}"
    throwaway_branch = f"verify/{throwaway_name}"

    print("=" * 70)
    print("Layer 3 verification — dashboard worktree toolchain sharing")
    print("=" * 70)
    print(f"Invoked from:      {PROJECT_ROOT}")
    print(f"Main checkout:     {main_wt}")
    print(f"Throwaway worktree: {throwaway_path}")
    print(f"Throwaway branch:  {throwaway_branch}")
    print()

    main_files = _file_count(main_node_modules)
    main_hardlinks = _hardlinked_file_count(main_node_modules)
    print(f"BEFORE (main): {main_files} files, {main_hardlinks} hardlinked")
    free_before = _df_kb(PROJECT_ROOT)
    print(f"BEFORE: {free_before // 1024} MB free on volume")
    print()

    pass_checks: list[tuple[str, bool]] = [("verification completed", False)]
    try:
        # Branch from the invoker's HEAD so the throwaway inherits the calling worktree's
        # code (critical when verifying changes that haven't merged to main yet).
        base_ref = _run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"]
        )
        _run(
            ["git", "worktree", "add", "-b", throwaway_branch, str(throwaway_path), base_ref],
            cwd=main_wt,
        )
        print(f"Worktree created at {throwaway_path} (base: {base_ref[:12]})")
        print()

        free_after_create = _df_kb(PROJECT_ROOT)
        print(f"After git worktree add: "
              f"{(free_before - free_after_create) // 1024} MB consumed")

        t0 = time.monotonic()
        preflight_result = subprocess.run(
            [
                "uv",
                "run",
                "--python",
                "3.12",
                "python",
                "scripts/worktree_preflight.py",
                "--repair",
                "--profile",
                "worktree",
            ],
            cwd=throwaway_path,
            capture_output=True,
            text=True,
        )
        materialize_ms = int((time.monotonic() - t0) * 1000)
        print(f"Preflight --repair completed in {materialize_ms} ms (rc={preflight_result.returncode})")
        if preflight_result.stdout:
            for line in preflight_result.stdout.splitlines():
                if any(k in line for k in ("dashboard_node_modules", "pnpm_alignment", "Repair", "cow-clone", "npm-install", "materialize")):
                    print(f"  preflight: {line}")
        if preflight_result.returncode != 0:
            print(f"  preflight stderr: {preflight_result.stderr[:800]}")
        print()

        throwaway_nm = throwaway_path / "apps" / "dashboard" / "node_modules"
        new_files = _file_count(throwaway_nm)
        new_hardlinks = _hardlinked_file_count(throwaway_nm)
        next_bin = throwaway_nm / ".bin" / "next"

        # Detect which materialize path was taken from the preflight Repair record.
        cow_used = "cow-clone" in preflight_result.stdout
        install_used = "npm-install" in preflight_result.stdout

        apparent_mb = _du_apparent_mb(throwaway_nm)
        actual_mb = _du_actual_mb(throwaway_nm)
        free_after = _df_kb(PROJECT_ROOT)
        volume_delta_mb = (free_before - free_after) // 1024
        # On APFS, `du` does not see CoW sharing — both apparent and actual report per-file
        # block allocation. The true byte-sharing signal is the *volume free-space delta*
        # against the apparent (full) size: if apparent is 1360 MB but the volume only
        # lost 86 MB, ~1274 MB of bytes are CoW-shared with the source worktree.
        share_pct = max(
            0,
            (apparent_mb - volume_delta_mb) * 100 // max(apparent_mb, 1),
        )

        print("AFTER (throwaway):")
        print(f"  files:                  {new_files}")
        print(f"  st_nlink>1 hardlinks:   {new_hardlinks} ({(new_hardlinks * 100 // max(new_files, 1))}%)")
        print(f"  apparent (du -A):       {apparent_mb} MB  (sum of file sizes)")
        print(f"  on-disk (du):           {actual_mb} MB  (du does not detect APFS CoW sharing)")
        print(f"  volume free delta:      {volume_delta_mb} MB consumed since BEFORE")
        print(f"  CoW byte-sharing rate:  {share_pct}%   (apparent - volume_delta) / apparent")
        print(f"  .bin/next exists:       {next_bin.exists()}")
        print(f"  materialize path used:  {'cow-clone' if cow_used else ('pnpm-install' if install_used else 'unknown')}")
        print()

        pass_checks = [
            (".bin/next exists", next_bin.exists()),
            ("preflight succeeded (rc=0)", preflight_result.returncode == 0),
        ]

        print("PASS CRITERIA:")
        print(f"  - .bin/next exists:                              {pass_checks[0][1]}")
        print(f"  - preflight succeeded (rc=0):                    {pass_checks[1][1]}")
        if cow_used:
            # CoW byte-sharing is the real signal (vs hardlinks which CoW doesn't produce).
            pass_checks.append(("CoW byte-sharing rate >= 80% (clone path)", share_pct >= 80))
            print(f"  - CoW byte-sharing rate >= 80% (clone path):     {pass_checks[-1][1]} ({share_pct}%)")
        elif install_used:
            # For install path: hardlinks indicate pnpm store reuse (requires .npmrc + same volume).
            hardlink_pct = (new_hardlinks * 100 // max(new_files, 1))
            pass_checks.append(("hardlink rate >= 80% (install path)", hardlink_pct >= 80))
            print(f"  - hardlink rate >= 80% (install path):           {pass_checks[-1][1]} ({hardlink_pct}%)")
        else:
            pass_checks.append(("materialize path detected", False))
        volume_limit_mb = _volume_delta_limit_mb()
        pass_checks.append((f"volume disk delta < {volume_limit_mb} MB", volume_delta_mb < volume_limit_mb))
        time_limit_ms = _preflight_time_limit_ms()
        pass_checks.append(("preflight within platform time budget", materialize_ms < time_limit_ms))
        print(
            f"  - volume disk delta < {volume_limit_mb} MB:                    "
            f"{pass_checks[-2][1]} ({volume_delta_mb} MB)"
        )
        print(
            "  - preflight within platform time budget:          "
            f"{pass_checks[-1][1]} ({materialize_ms} ms < {time_limit_ms} ms)"
        )

    finally:
        print()
        print("Cleaning up...")
        if throwaway_path.exists():
            try:
                _run(["git", "worktree", "remove", "--force", str(throwaway_path)],
                     cwd=main_wt)
            except subprocess.CalledProcessError:
                pass
            if throwaway_path.exists():
                _remove_tree(throwaway_path)
        try:
            _run(["git", "branch", "-D", throwaway_branch], cwd=main_wt)
        except subprocess.CalledProcessError:
            pass
        print("Cleanup complete.")
        free_final = _df_kb(PROJECT_ROOT)
        print(f"Final disk delta: {(free_before - free_final) // 1024} MB net consumed (should be ~0)")

    return 0 if all(ok for _, ok in pass_checks) else 1


if __name__ == "__main__":
    sys.exit(main())

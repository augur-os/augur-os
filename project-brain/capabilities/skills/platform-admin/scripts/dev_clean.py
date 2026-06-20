#!/usr/bin/env python3
"""dev_clean — Idempotent repo hygiene for Augur.

Reclaims disk and inode budget by removing regenerable artifacts that
`.gitignore` already excludes. Tier 1 touches only filesystem caches and
duplicate virtualenvs. Tier 2 touches `.git` (LFS prune + `git gc`) and the
global pnpm content-addressable store.

Defaults are conservative: Tier 1 only, no `.git` or global package-store
mutation. Use `--include-git` or `--all` to opt in to Tier 2.

Safety contract
---------------
* Every target is either (a) listed in `.gitignore` or (b) verified to be
  unreachable git state (LFS prune verifies against remote before removing).
* Refuses to operate outside the repo root.
* `--dry-run` reports what *would* be reclaimed without deleting.
* Idempotent: re-running on a clean tree is a no-op that reports 0 bytes.

Exit codes: 0 success; 2 misuse; 1 unexpected failure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

def _discover_repo_root() -> Path:
    """Return the checkout root from this skill script location."""
    start = Path(__file__).resolve()
    for candidate in (start.parent, *start.parents):
        if (candidate / "project.yaml").is_file() and (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError(f"Could not discover Augur repo root from {start}")


REPO_ROOT = _discover_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config.paths import get_cache_dir

DASHBOARD_WORKTREE_CACHE_PREFIX = "dashboard-worktree-"


def fmt_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:.1f} {u}" if u != "B" else f"{int(f)} {u}"
        f /= 1024
    return f"{f:.1f} TB"


def dir_stats(path: Path) -> tuple[int, int]:
    """Return (total_bytes, file_count) for a directory tree. Safe on missing."""
    if not path.exists():
        return 0, 0
    total = 0
    files = 0
    for root, _dirs, names in os.walk(path, followlinks=False):
        for name in names:
            try:
                st = os.lstat(os.path.join(root, name))
                total += st.st_size
                files += 1
            except OSError:
                pass
    return total, files


@dataclass
class Operation:
    name: str
    tier: int
    rationale: str
    run: Callable[[bool], "OpResult"]
    enabled: bool = True


@dataclass
class OpResult:
    name: str
    tier: int
    rationale: str
    bytes_reclaimed: int = 0
    files_reclaimed: int = 0
    targets_touched: int = 0
    skipped_reason: str | None = None
    notes: list[str] = field(default_factory=list)


def remove_dir(path: Path, dry_run: bool) -> tuple[int, int, bool]:
    """Return (bytes, files, removed?)."""
    if not path.exists():
        return 0, 0, False
    size, files = dir_stats(path)
    if not dry_run:
        shutil.rmtree(path, ignore_errors=True)
    return size, files, True


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


def op_stale_dashboard_worktree_caches(dry_run: bool) -> OpResult:
    """Remove inactive external dashboard worktree caches under get_cache_dir().

    The active main dashboard cache lives in `dashboard/` and is intentionally
    excluded. Worktree caches are fully rebuildable, but a live Next dev server
    may still hold its `next/dev/lock`, so those are skipped.
    """
    res = OpResult(
        name="stale-dashboard-worktree-caches",
        tier=1,
        rationale="Inactive external dashboard worktree caches under get_cache_dir()",
    )
    cache_root = get_cache_dir()
    if not cache_root.is_dir():
        return res

    for candidate in sorted(cache_root.glob(f"{DASHBOARD_WORKTREE_CACHE_PREFIX}*")):
        if not candidate.is_dir() or candidate.is_symlink():
            continue
        live_pid = _live_next_lock_pid(candidate)
        if live_pid is not None:
            res.notes.append(f"skipped {candidate.name}: active lock pid {live_pid}")
            continue
        bytes_, files, removed = remove_dir(candidate, dry_run)
        res.bytes_reclaimed += bytes_
        res.files_reclaimed += files
        if removed:
            res.targets_touched += 1
            res.notes.append(f"removed {candidate.name}")
    return res


def op_pnpm_ignored_cache(dry_run: bool) -> OpResult:
    """Remove pnpm's stale-symlink graveyard (node_modules/.ignored).

    pnpm relocates here when upgrades obsolete a hoisted layout. The tree is
    never read by Node or by pnpm at runtime; it exists only so pnpm can
    rollback. After install completes, it is pure waste.
    """
    target = REPO_ROOT / "apps" / "dashboard" / "node_modules" / ".ignored"
    res = OpResult(
        name="pnpm-ignored-cache",
        tier=1,
        rationale="Stale pnpm symlink graveyard (apps/dashboard/node_modules/.ignored)",
    )
    bytes_, files, removed = remove_dir(target, dry_run)
    res.bytes_reclaimed = bytes_
    res.files_reclaimed = files
    res.targets_touched = 1 if removed else 0
    return res


def op_duplicate_mcp_venv(dry_run: bool) -> OpResult:
    """Remove the duplicate `src/mcp/.venv` left over from local experimentation.

    The project uses the root `.venv` (driven by `uv sync` at repo root).
    Anything under `src/mcp/.venv` is shadowed by the root venv and pulls
    PYTHONPATH only by mistake. If a user genuinely needs an isolated MCP venv
    they will recreate it explicitly; the root sync does not depend on it.
    """
    target = REPO_ROOT / "src" / "mcp" / ".venv"
    res = OpResult(
        name="duplicate-mcp-venv",
        tier=1,
        rationale="Duplicate virtualenv at src/mcp/.venv (shadowed by root .venv)",
    )
    bytes_, files, removed = remove_dir(target, dry_run)
    res.bytes_reclaimed = bytes_
    res.files_reclaimed = files
    res.targets_touched = 1 if removed else 0
    return res


def _find_pycache_dirs(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for dirpath, dirs, _files in os.walk(root, followlinks=False):
        for d in list(dirs):
            if d == "__pycache__":
                yield Path(dirpath) / d
                dirs.remove(d)


def op_pycache_purge(dry_run: bool) -> OpResult:
    """Remove every `__pycache__` directory under user-editable trees.

    `.gitignore` excludes `__pycache__/` so these never reach git, but they
    accumulate on disk as the Python interpreter writes bytecode next to
    sources in `project-brain/capabilities/skills/` and `src/`. Nothing reads them except
    the next Python run, which will regenerate what it needs.
    """
    res = OpResult(
        name="pycache-purge",
        tier=1,
        rationale="Stale __pycache__ directories (regenerated by Python)",
    )
    scan_roots = [REPO_ROOT / "project-brain", REPO_ROOT / "src", REPO_ROOT / "scripts"]
    for scan_root in scan_roots:
        for pyc_dir in _find_pycache_dirs(scan_root):
            bytes_, files, removed = remove_dir(pyc_dir, dry_run)
            res.bytes_reclaimed += bytes_
            res.files_reclaimed += files
            if removed:
                res.targets_touched += 1
    return res


def op_tool_caches(dry_run: bool) -> OpResult:
    """Remove regenerable tool caches at repo root."""
    res = OpResult(
        name="tool-caches",
        tier=1,
        rationale="Tool caches (.pytest_cache, .ruff_cache) — regenerated on next run",
    )
    for cache_dir in (".pytest_cache", ".ruff_cache"):
        target = REPO_ROOT / cache_dir
        bytes_, files, removed = remove_dir(target, dry_run)
        res.bytes_reclaimed += bytes_
        res.files_reclaimed += files
        if removed:
            res.targets_touched += 1
            res.notes.append(f"removed {cache_dir}")
    return res


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def _git_dir_bytes() -> int:
    try:
        proc = _git("rev-parse", "--git-common-dir", check=False)
        if proc.returncode == 0:
            git_dir_text = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
            if git_dir_text:
                git_dir = Path(git_dir_text).expanduser()
                if not git_dir.is_absolute():
                    git_dir = REPO_ROOT / git_dir
                bytes_, _ = dir_stats(git_dir)
                return bytes_
    except (OSError, IndexError):
        pass
    bytes_, _ = dir_stats(REPO_ROOT / ".git")
    return bytes_


def op_git_lfs_prune(dry_run: bool) -> OpResult:
    """Prune LFS objects already pushed to remote.

    `git lfs prune` defaults to verifying that each pruned object exists on
    the remote before deleting locally. We do not bypass that check, so this
    cannot lose unpushed work.
    """
    res = OpResult(
        name="git-lfs-prune",
        tier=2,
        rationale="Orphaned LFS objects already replicated to remote",
    )
    try:
        _git("rev-parse", "--git-dir")
    except subprocess.CalledProcessError:
        res.skipped_reason = "not a git repository"
        return res
    try:
        _git("lfs", "version")
    except (subprocess.CalledProcessError, FileNotFoundError):
        res.skipped_reason = "git-lfs not installed"
        return res

    before = _git_dir_bytes()
    if dry_run:
        try:
            proc = _git("lfs", "prune", "--dry-run", "--verify-remote", check=False)
            if proc.stdout:
                res.notes.append(proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "")
        except Exception as exc:  # noqa: BLE001
            res.notes.append(f"dry-run failed: {exc}")
    else:
        try:
            _git("lfs", "prune", "--verify-remote")
        except subprocess.CalledProcessError as exc:
            res.skipped_reason = f"lfs prune failed: {exc.stderr.strip()[:200]}"
            return res
        after = _git_dir_bytes()
        res.bytes_reclaimed = max(0, before - after)
        res.targets_touched = 1
    return res


def op_git_gc(dry_run: bool) -> OpResult:
    """Repack and prune unreachable objects.

    `git gc --prune=now` consolidates pack files and drops objects unreachable
    from any ref or reflog older than 0 seconds. It cannot remove anything
    reachable from a branch, tag, stash, or HEAD.
    """
    res = OpResult(
        name="git-gc",
        tier=2,
        rationale="Repack git objects + prune unreachable (git gc --prune=now)",
    )
    try:
        _git("rev-parse", "--git-dir")
    except subprocess.CalledProcessError:
        res.skipped_reason = "not a git repository"
        return res

    before = _git_dir_bytes()
    if dry_run:
        res.notes.append(f".git is currently {fmt_bytes(before)}; gc would repack")
    else:
        try:
            _git("gc", "--prune=now", "--quiet")
        except subprocess.CalledProcessError as exc:
            res.skipped_reason = f"git gc failed: {exc.stderr.strip()[:200]}"
            return res
        after = _git_dir_bytes()
        res.bytes_reclaimed = max(0, before - after)
        res.targets_touched = 1
    return res


def _resolve_pnpm_command() -> list[str] | None:
    pnpm = shutil.which("pnpm")
    if pnpm:
        return [pnpm]
    corepack = shutil.which("corepack")
    if corepack:
        return [corepack, "pnpm"]
    return None


def _run_pnpm(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _pnpm_store_path(pnpm_cmd: list[str]) -> Path | None:
    try:
        proc = _run_pnpm(pnpm_cmd + ["store", "path"], timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    path = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    return Path(path).expanduser() if path else None


def _parse_pnpm_store_prune_output(output: str) -> tuple[int, int]:
    files_match = re.search(r"(?:Removed|Would remove)\s+(\d+)\s+files?", output, re.IGNORECASE)
    packages_match = re.search(
        r"(?:Removed|Would remove)\s+(\d+)\s+packages?", output, re.IGNORECASE
    )
    files_removed = int(files_match.group(1)) if files_match else 0
    packages_removed = int(packages_match.group(1)) if packages_match else 0
    return files_removed, packages_removed


def _is_unknown_dry_run_option(proc: subprocess.CompletedProcess[str]) -> bool:
    stderr = (proc.stderr or "").lower()
    return proc.returncode != 0 and "unknown option" in stderr and "dry-run" in stderr


def _prune_pnpm_store(dry_run: bool) -> OpResult:
    """Tier 2 operation: prune unreferenced packages from the global pnpm store."""
    res = OpResult(
        name="pnpm-store-prune",
        tier=2,
        rationale=(
            "Unreferenced package versions in the global pnpm content-addressable store"
        ),
    )
    pnpm_cmd = _resolve_pnpm_command()
    if pnpm_cmd is None:
        res.skipped_reason = (
            "pnpm not found (neither pnpm nor corepack on PATH); run "
            "`corepack enable && corepack prepare pnpm@latest --activate`"
        )
        return res

    store_path = _pnpm_store_path(pnpm_cmd)
    before_bytes, before_files = dir_stats(store_path) if store_path else (0, 0)
    cmd = pnpm_cmd + ["store", "prune"]
    if dry_run:
        cmd.append("--dry-run")

    try:
        proc = _run_pnpm(cmd)
    except subprocess.TimeoutExpired:
        res.skipped_reason = "pnpm store prune timed out after 300s"
        return res
    except OSError as exc:
        res.skipped_reason = f"pnpm store prune failed: {exc}"
        return res

    if dry_run and _is_unknown_dry_run_option(proc):
        res.bytes_reclaimed = before_bytes
        res.files_reclaimed = before_files
        res.targets_touched = 0
        res.notes.append(
            "dry-run estimate: pnpm does not support store prune --dry-run; "
            f"current store upper bound is {fmt_bytes(before_bytes)}"
        )
        return res

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "no output").strip()
        res.skipped_reason = f"pnpm store prune failed: {detail[:200]}"
        return res

    files_removed, packages_removed = _parse_pnpm_store_prune_output(proc.stdout)
    res.files_reclaimed = files_removed
    if dry_run:
        res.targets_touched = 0
        res.notes.append(
            f"dry-run: would prune {files_removed} files across {packages_removed} packages"
        )
    else:
        after_bytes, after_files = dir_stats(store_path) if store_path else (0, 0)
        res.bytes_reclaimed = max(0, before_bytes - after_bytes)
        if res.files_reclaimed == 0 and before_files:
            res.files_reclaimed = max(0, before_files - after_files)
        res.targets_touched = 1
        res.notes.append(f"pruned {files_removed} files across {packages_removed} packages")
    return res


def build_operations(include_git: bool) -> list[Operation]:
    ops = [
        Operation("pnpm-ignored-cache", 1, "", op_pnpm_ignored_cache),
        Operation("duplicate-mcp-venv", 1, "", op_duplicate_mcp_venv),
        Operation("pycache-purge", 1, "", op_pycache_purge),
        Operation("tool-caches", 1, "", op_tool_caches),
        Operation(
            "stale-dashboard-worktree-caches",
            1,
            "",
            op_stale_dashboard_worktree_caches,
        ),
    ]
    if include_git:
        ops.append(Operation("git-lfs-prune", 2, "", op_git_lfs_prune))
        ops.append(Operation("git-gc", 2, "", op_git_gc))
        ops.append(Operation("pnpm-store-prune", 2, "", _prune_pnpm_store))
    return ops


def render_report(results: list[OpResult], dry_run: bool) -> str:
    width = max((len(r.name) for r in results), default=20)
    lines = []
    header = "would reclaim" if dry_run else "reclaimed"
    lines.append(f"{'OPERATION'.ljust(width)}  TIER  TARGETS  {header.upper():>14}  FILES")
    lines.append("-" * (width + 50))
    total_bytes = 0
    total_files = 0
    total_targets = 0
    for r in results:
        if r.skipped_reason:
            lines.append(f"{r.name.ljust(width)}  T{r.tier}    SKIPPED  {r.skipped_reason}")
            continue
        lines.append(
            f"{r.name.ljust(width)}  T{r.tier}    "
            f"{r.targets_touched:>7}  {fmt_bytes(r.bytes_reclaimed):>14}  {r.files_reclaimed:>6}"
        )
        total_bytes += r.bytes_reclaimed
        total_files += r.files_reclaimed
        total_targets += r.targets_touched
    lines.append("-" * (width + 50))
    lines.append(
        f"{'TOTAL'.ljust(width)}  --    {total_targets:>7}  "
        f"{fmt_bytes(total_bytes):>14}  {total_files:>6}"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dev_clean",
        description="Idempotent repo hygiene — Tier 1 caches + optional Tier 2 git",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be reclaimed without deleting anything",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--include-git",
        action="store_true",
        help="Also run Tier 2: git lfs prune + git gc --prune=now",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Run Tier 1 + Tier 2 (alias for --include-git)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON report instead of the table",
    )
    args = parser.parse_args(argv)

    include_git = args.include_git or args.all
    operations = build_operations(include_git=include_git)

    print(
        f"dev_clean: {'DRY RUN' if args.dry_run else 'EXECUTING'} "
        f"({'Tier 1+2' if include_git else 'Tier 1 only'}) "
        f"at {REPO_ROOT}",
        file=sys.stderr,
    )

    results: list[OpResult] = []
    for op in operations:
        try:
            results.append(op.run(args.dry_run))
        except Exception as exc:  # noqa: BLE001
            r = OpResult(name=op.name, tier=op.tier, rationale=op.rationale)
            r.skipped_reason = f"failed: {exc}"
            results.append(r)

    if args.json:
        payload = {
            "dry_run": args.dry_run,
            "tier_2_included": include_git,
            "repo_root": str(REPO_ROOT),
            "results": [
                {
                    "name": r.name,
                    "tier": r.tier,
                    "bytes_reclaimed": r.bytes_reclaimed,
                    "files_reclaimed": r.files_reclaimed,
                    "targets_touched": r.targets_touched,
                    "skipped_reason": r.skipped_reason,
                    "notes": r.notes,
                }
                for r in results
            ],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(render_report(results, args.dry_run))

    return 0


if __name__ == "__main__":
    sys.exit(main())

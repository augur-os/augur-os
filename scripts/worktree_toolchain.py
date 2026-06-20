"""Worktree toolchain helpers: pnpm alignment, CoW clones, node_modules materialization.

This module owns the cheapest-path materialization of apps/dashboard/node_modules
across worktrees. It is imported by scripts/worktree_preflight.py and runs entirely
under the existing preflight Incident/Repair contract.

Pure functions:
    verify_pnpm_alignment(project_root) -> Incident | None
    probe_clone_primitive(path) -> CloneFn | None
    materialize_node_modules(worktree_root, source_worktree) -> MaterializeResult
"""

from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# Reuse the Incident dataclass from worktree_preflight to keep the contract single-source.
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from worktree_preflight import Incident  # noqa: E402


def _resolve_pnpm_store_dir() -> Path | None:
    """Return the resolved pnpm store directory, or None if unresolvable."""
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        return None
    try:
        result = subprocess.run(
            [pnpm, "config", "get", "store-dir"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    value = (result.stdout or "").strip()
    if not value or value.lower() == "undefined":
        # pnpm prints "undefined" when no override is set; fall back to platform default.
        value = _platform_default_store_dir()
    if not value:
        return None
    candidate = Path(value).expanduser()
    if not candidate.exists():
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None
    return candidate


def _platform_default_store_dir() -> str:
    if sys.platform == "darwin":
        return str(Path.home() / "Library" / "pnpm" / "store")
    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return str(Path(local) / "pnpm" / "store")
        return str(Path.home() / "AppData" / "Local" / "pnpm" / "store")
    return str(Path.home() / ".local" / "share" / "pnpm" / "store")


def _device_id(path: Path) -> int:
    return os.stat(path).st_dev


def verify_pnpm_alignment(project_root: Path) -> Incident | None:
    """Return an Incident when the pnpm store and project root are on different volumes.

    Hardlinks cannot cross filesystem boundaries. When they're misaligned pnpm
    silently falls back to copying files, defeating the content-addressable store
    benefit. The user must choose how to resolve (move projects, or set store-dir
    to a path on the projects volume) — this check does NOT auto-fix.
    """
    store_dir = _resolve_pnpm_store_dir()
    if store_dir is None:
        return Incident(
            fingerprint="worktree/toolchain/pnpm-store-unresolved",
            severity="high",
            message=(
                "Could not resolve pnpm store-dir. Install pnpm (corepack enable && "
                "corepack prepare pnpm@latest --activate) or set store-dir via "
                "`pnpm config set store-dir <path>`."
            ),
            owner_path=str(project_root),
            safe_to_repair=False,
            repaired=False,
        )

    project_dev = _device_id(project_root)
    store_dev = _device_id(store_dir)
    if project_dev == store_dev:
        return None

    return Incident(
        fingerprint="worktree/toolchain/pnpm-store-misaligned",
        severity="high",
        message=(
            f"pnpm store and projects directory live on different filesystem volume. "
            f"Project root: {project_root} (dev={project_dev}). "
            f"Store: {store_dir} (dev={store_dev}). "
            f"Hardlinks cannot cross volumes; pnpm will copy files instead. "
            f"Resolve by either moving projects to the store volume, or running "
            f"`pnpm config set store-dir <path-on-projects-volume>`."
        ),
        owner_path=str(project_root),
        safe_to_repair=False,
        repaired=False,
    )


CloneFn = Callable[[Path, Path], None]


def _detect_fs_type(path: Path) -> str:
    """Return the filesystem type for the given path, or '' if undetectable.

    macOS: parses `mount` output (stat -f %T returns file type, not fs type).
    Linux: parses `stat -f -c %T`.
    Windows: parses `Get-Volume` PowerShell output.
    """
    if sys.platform == "darwin":
        try:
            mount_result = subprocess.run(
                ["mount"], capture_output=True, text=True, check=True, timeout=5
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return ""
        resolved = str(path.resolve())
        best_match = ""
        best_len = -1
        for line in mount_result.stdout.splitlines():
            # Format: /dev/disk3s1s1 on / (apfs, sealed, local, ...)
            if " on " not in line or "(" not in line:
                continue
            try:
                mountpoint = line.split(" on ", 1)[1].split(" (", 1)[0]
                fs_info = line.split("(", 1)[1].rstrip(")")
                fs_type = fs_info.split(",", 1)[0].strip().lower()
            except IndexError:
                continue
            if resolved.startswith(mountpoint) and len(mountpoint) > best_len:
                best_match = fs_type
                best_len = len(mountpoint)
        return best_match

    if sys.platform.startswith("linux"):
        try:
            result = subprocess.run(
                ["stat", "-f", "-c", "%T", str(path)],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            return result.stdout.strip().lower()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return ""

    if sys.platform.startswith("win"):
        try:
            drive = Path(path).resolve().drive  # e.g. "C:"
            if not drive:
                return ""
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-Volume -DriveLetter {drive[0]}).FileSystemType",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            return result.stdout.strip().lower()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return ""

    return ""


def _cp_clone(src: Path, dst: Path, *, mode: str) -> None:
    """Run the platform-appropriate CoW clone command and raise on failure."""
    if mode == "apfs":
        cmd = ["cp", "-c", "-R", str(src), str(dst)]
    elif mode == "reflink":
        cmd = ["cp", "--reflink=auto", "-R", str(src), str(dst)]
    elif mode == "refs":
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Copy-Item -Path '{src}' -Destination '{dst}' -Recurse -Force",
        ]
    else:
        raise ValueError(f"Unknown clone mode: {mode}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Clone failed ({mode}): rc={result.returncode} "
            f"stderr={result.stderr.strip()[:300]}"
        )


def probe_clone_primitive(path: Path) -> CloneFn | None:
    """Return a callable (src, dst) -> None for CoW cloning, or None if unsupported.

    `path` selects which filesystem to probe — pass the target worktree directory
    so the primitive is matched to the volume the clone will land on.
    """
    fs_type = _detect_fs_type(path)
    if sys.platform == "darwin" and fs_type == "apfs":
        return lambda src, dst: _cp_clone(src, dst, mode="apfs")
    if sys.platform.startswith("linux") and fs_type in {"btrfs", "xfs"}:
        return lambda src, dst: _cp_clone(src, dst, mode="reflink")
    if sys.platform.startswith("win") and fs_type == "refs":
        return lambda src, dst: _cp_clone(src, dst, mode="refs")
    return None


@dataclass
class MaterializeResult:
    method: str  # "skip" | "clone" | "install" | "failed"
    duration_ms: int
    source_worktree: str | None
    clone_primitive: str | None
    incidents: list[Incident] = field(default_factory=list)


def _next_bin(worktree_root: Path) -> Path:
    return worktree_root / "apps" / "dashboard" / "node_modules" / ".bin" / "next"


def _lockfile_hash(worktree_root: Path) -> str | None:
    lockfile = worktree_root / "apps" / "dashboard" / "pnpm-lock.yaml"
    if not lockfile.exists():
        return None
    return hashlib.sha256(lockfile.read_bytes()).hexdigest()


def _pnpm_install_frozen(dashboard_dir: Path) -> Incident | None:
    """Run `pnpm install --frozen-lockfile` with hardlink imports in dashboard_dir."""
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        corepack = shutil.which("corepack")
        if corepack is None:
            return Incident(
                fingerprint="worktree/toolchain/no-pnpm",
                severity="high",
                message=(
                    "Neither pnpm nor corepack found on PATH. Run "
                    "`corepack enable && corepack prepare pnpm@latest --activate`."
                ),
                owner_path=str(dashboard_dir),
                safe_to_repair=False,
                repaired=False,
            )
        cmd = [
            corepack,
            "pnpm",
            "install",
            "--frozen-lockfile",
            "--package-import-method",
            "hardlink",
        ]
    else:
        cmd = [
            pnpm,
            "install",
            "--frozen-lockfile",
            "--package-import-method",
            "hardlink",
        ]

    try:
        subprocess.run(
            cmd,
            cwd=dashboard_dir,
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        return Incident(
            fingerprint="worktree/toolchain/install-failed",
            severity="high",
            message=(
                f"pnpm install failed in {dashboard_dir}: "
                f"{stderr[:500] or 'pnpm exited non-zero'} "
                f"(cmd={' '.join(shlex.quote(p) for p in cmd)})"
            ),
            owner_path=str(dashboard_dir),
            safe_to_repair=False,
            repaired=False,
        )
    except subprocess.TimeoutExpired:
        return Incident(
            fingerprint="worktree/toolchain/install-timeout",
            severity="high",
            message=f"pnpm install timed out after 600s in {dashboard_dir}",
            owner_path=str(dashboard_dir),
            safe_to_repair=False,
            repaired=False,
        )
    return None


def _clone_dashboard_node_modules(
    source: Path, target: Path, clone_fn: CloneFn
) -> Incident | None:
    """CoW-clone source/apps/dashboard/node_modules into target/apps/dashboard/."""
    src_nm = source / "apps" / "dashboard" / "node_modules"
    target_dashboard = target / "apps" / "dashboard"
    dst_nm = target_dashboard / "node_modules"

    if dst_nm.exists():
        shutil.rmtree(dst_nm, ignore_errors=True)
    target_dashboard.mkdir(parents=True, exist_ok=True)

    try:
        clone_fn(src_nm, dst_nm)
    except Exception as exc:  # noqa: BLE001 — fall-through path
        if dst_nm.exists():
            shutil.rmtree(dst_nm, ignore_errors=True)
        return Incident(
            fingerprint="worktree/toolchain/clone-failed",
            severity="medium",
            message=f"CoW clone failed ({exc}); falling through to pnpm install.",
            owner_path=str(target),
            safe_to_repair=True,
            repaired=True,  # handled by falling through
        )
    return None


@contextmanager
def _materialize_lock(worktree_root: Path):
    """Cross-platform exclusive file lock for the duration of materialization."""
    lock_dir = worktree_root / "apps" / "dashboard"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / ".materialize.lock"
    lock_file = open(lock_path, "a+")
    try:
        if sys.platform.startswith("win"):
            import msvcrt

            while True:
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    finally:
        lock_file.close()


def materialize_node_modules(
    worktree_root: Path,
    source_worktree: Path | None,
) -> MaterializeResult:
    """Ensure worktree_root/apps/dashboard/node_modules is ready, cheaply.

    Decision tree:
      1. If .bin/next already exists at target → method="skip".
      2. If source worktree provided, has matching lockfile, has .bin/next,
         and a clone primitive is available → attempt clone.
      3. On clone success → method="clone".
      4. Otherwise → pnpm install --frozen-lockfile.
      5. On install success → method="install"; on failure → method="failed".
    """
    start = time.monotonic()
    target_dashboard = worktree_root / "apps" / "dashboard"
    incidents: list[Incident] = []
    clone_primitive_name: str | None = None

    with _materialize_lock(worktree_root):
        if _next_bin(worktree_root).exists():
            return MaterializeResult(
                method="skip",
                duration_ms=int((time.monotonic() - start) * 1000),
                source_worktree=str(source_worktree) if source_worktree else None,
                clone_primitive=None,
                incidents=[],
            )

        clone_fn = probe_clone_primitive(target_dashboard)
        if clone_fn is not None:
            clone_primitive_name = (
                clone_fn.__name__ if hasattr(clone_fn, "__name__") else "anon"
            )

        can_clone = (
            source_worktree is not None
            and clone_fn is not None
            and _next_bin(source_worktree).exists()
            and _lockfile_hash(worktree_root) is not None
            and _lockfile_hash(worktree_root) == _lockfile_hash(source_worktree)
        )

        if can_clone:
            clone_incident = _clone_dashboard_node_modules(
                source_worktree, worktree_root, clone_fn
            )
            if clone_incident is None and _next_bin(worktree_root).exists():
                return MaterializeResult(
                    method="clone",
                    duration_ms=int((time.monotonic() - start) * 1000),
                    source_worktree=str(source_worktree),
                    clone_primitive=clone_primitive_name,
                    incidents=[],
                )
            if clone_incident is not None:
                incidents.append(clone_incident)

        install_incident = _pnpm_install_frozen(target_dashboard)
        if install_incident is None:
            return MaterializeResult(
                method="install",
                duration_ms=int((time.monotonic() - start) * 1000),
                source_worktree=str(source_worktree) if source_worktree else None,
                clone_primitive=clone_primitive_name,
                incidents=incidents,
            )

        incidents.append(install_incident)
        return MaterializeResult(
            method="failed",
            duration_ms=int((time.monotonic() - start) * 1000),
            source_worktree=str(source_worktree) if source_worktree else None,
            clone_primitive=clone_primitive_name,
            incidents=incidents,
        )

"""Runtime identity helpers for main-owned global state and worktree overlays."""

from __future__ import annotations

import contextlib
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path


class GlobalIdentityError(RuntimeError):
    """Raised when a command would mutate shared identity from an unsafe root."""


@dataclass(frozen=True)
class RuntimeIdentity:
    current_root: Path
    authority_root: Path
    main_root: Path | None
    is_linked_worktree: bool
    can_mutate_global: bool
    branch: str | None = None


@dataclass(frozen=True)
class WorktreeRecord:
    path: Path
    branch: str | None
    is_bare: bool = False


def _run_git(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return result.stdout


def _parse_worktree_list(output: str) -> list[WorktreeRecord]:
    records: list[WorktreeRecord] = []
    current: dict[str, str | bool] = {}

    def append_current() -> None:
        if "worktree" not in current:
            return
        records.append(
            WorktreeRecord(
                path=Path(str(current["worktree"])).expanduser().resolve(),
                branch=str(current["branch"]) if current.get("branch") else None,
                is_bare=bool(current.get("bare")),
            )
        )

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            append_current()
            current = {}
            continue
        if line.startswith("worktree "):
            current["worktree"] = line.removeprefix("worktree ").strip()
        elif line.startswith("branch "):
            current["branch"] = line.removeprefix("branch ").strip().removeprefix("refs/heads/")
        elif line == "bare":
            current["bare"] = True
    append_current()
    return records


def _main_checkout_from_git_file(project_root: Path) -> Path | None:
    git_entry = project_root / ".git"
    if not git_entry.is_file():
        return None
    try:
        marker = git_entry.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not marker.startswith("gitdir:"):
        return None

    gitdir = Path(marker.split("gitdir:", 1)[1].strip()).expanduser()
    if not gitdir.is_absolute():
        gitdir = (project_root / gitdir).resolve()
    parts = gitdir.parts
    try:
        worktrees_index = parts.index("worktrees")
    except ValueError:
        return None
    main_git_dir = Path(*parts[:worktrees_index])
    main_checkout = main_git_dir.parent
    if (main_checkout / "project.yaml").is_file() or (main_checkout / "pyproject.toml").is_file():
        return main_checkout.resolve()
    return None


def _branch_for(root: Path) -> str | None:
    output = _run_git(root, "branch", "--show-current")
    branch = output.strip() if output else ""
    return branch or None


def main_checkout_for_worktree(project_root: str | Path) -> Path | None:
    """Resolve the stable main checkout for a linked worktree, when available."""
    root = Path(project_root).expanduser().resolve()
    output = _run_git(root, "worktree", "list", "--porcelain")
    if output:
        records = [record for record in _parse_worktree_list(output) if not record.is_bare]
        if records:
            primary_checkout = records[0].path
            return None if primary_checkout == root else primary_checkout
    return _main_checkout_from_git_file(root)


def resolve_runtime_identity(project_root: str | Path | None = None) -> RuntimeIdentity:
    """Resolve the current checkout and the authority root for global identity writes."""
    root = Path(project_root or Path.cwd()).expanduser().resolve()
    main_root = main_checkout_for_worktree(root)
    is_linked = main_root is not None and main_root != root
    authority = (main_root or root).resolve()
    return RuntimeIdentity(
        current_root=root,
        authority_root=authority,
        main_root=main_root,
        is_linked_worktree=is_linked,
        can_mutate_global=not is_linked,
        branch=_branch_for(root),
    )


def global_mcp_project_root(project_root: str | Path | None = None) -> Path:
    """Return the root that user-global MCP configs should embed."""
    return resolve_runtime_identity(project_root).authority_root


class GlobalMutationGuard:
    """Context guard for writes to shared global identity surfaces."""

    def __init__(
        self,
        identity: RuntimeIdentity,
        *,
        target_root: str | Path,
        operation: str,
        allow_delegated: bool = False,
    ) -> None:
        self.identity = identity
        self.target_root = Path(target_root).expanduser().resolve()
        self.operation = operation
        self.allow_delegated = allow_delegated

    def __enter__(self) -> GlobalMutationGuard:
        authority = self.identity.authority_root.resolve()
        if self.target_root != authority:
            raise GlobalIdentityError(
                f"worktree cannot mutate shared global identity for {self.operation}: "
                f"target={self.target_root} authority={authority} current={self.identity.current_root}"
            )
        if self.identity.is_linked_worktree and not self.allow_delegated:
            raise GlobalIdentityError(
                f"worktree cannot mutate shared global identity for {self.operation}: "
                f"current={self.identity.current_root} authority={authority}"
            )
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


def build_worktree_overlay_env(
    identity: RuntimeIdentity,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build a process-local environment overlay that points at the current worktree."""
    env = dict(base_env or os.environ)
    root = identity.current_root
    canonical = [
        str(root / "project-brain" / "capabilities"),
        str(root),
        str(root / "src" / "mcp"),
    ]
    kept = [entry for entry in (env.get("PYTHONPATH") or "").split(os.pathsep) if entry and entry not in canonical]
    root_str = str(root)
    env["AUGUR_PROJECT_ROOT"] = root_str
    env["AUGUR_ROOT"] = root_str
    env["AUGUR_CORE"] = root_str
    env["AUGUR_REPO"] = root_str
    env["PYTHONPATH"] = os.pathsep.join([*canonical, *kept])
    return env


class GlobalIdentityLock:
    """Filesystem lock for serializing shared global identity mutations."""

    _thread_locks: dict[Path, threading.Lock] = {}
    _thread_locks_guard = threading.Lock()

    def __init__(self, lock_path: Path, *, timeout_sec: float = 30.0) -> None:
        self.lock_path = lock_path.expanduser().resolve()
        self.timeout_sec = timeout_sec
        self._fh = None
        self._thread_lock: threading.Lock | None = None

    @classmethod
    def _lock_for_path(cls, lock_path: Path) -> threading.Lock:
        with cls._thread_locks_guard:
            return cls._thread_locks.setdefault(lock_path, threading.Lock())

    def __enter__(self) -> GlobalIdentityLock:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_sec
        self._thread_lock = self._lock_for_path(self.lock_path)
        while not self._thread_lock.acquire(blocking=False):
            if time.monotonic() >= deadline:
                raise GlobalIdentityError(f"timed out waiting for global identity lock {self.lock_path}")
            time.sleep(0.05)

        self._fh = self.lock_path.open("a+")
        try:
            while True:
                try:
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return self
                except OSError:
                    if time.monotonic() >= deadline:
                        raise GlobalIdentityError(f"timed out waiting for global identity lock {self.lock_path}")
                    time.sleep(0.05)
        except Exception:
            self._release_thread_lock()
            with contextlib.suppress(OSError):
                self._fh.close()
            self._fh = None
            raise

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._fh is not None:
            with contextlib.suppress(OSError):
                if os.name == "nt":
                    import msvcrt

                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            self._fh.close()
            self._fh = None
        self._release_thread_lock()

    def _release_thread_lock(self) -> None:
        if self._thread_lock is not None:
            self._thread_lock.release()
            self._thread_lock = None


def default_global_identity_lock_path() -> Path:
    """Return the default shared global identity lock path."""
    try:
        from src.config.paths import get_runtime_dir

        return get_runtime_dir() / "global-identity.lock"
    except Exception:
        return Path.home() / ".augur" / "state" / "global-identity.lock"

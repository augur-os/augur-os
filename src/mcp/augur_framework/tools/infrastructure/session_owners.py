"""Session-ownership registry core (ADR-766 v1)."""

from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_LOCK = threading.Lock()
_VALID_SURFACES = {"dashboard-pty", "native-terminal"}


class SessionClaimInput(BaseModel):
    """Input for claiming a local live owner for a CLI session id."""

    session_id: str = Field(..., min_length=1, description="CLI session id being claimed")
    surface: str = Field(..., description="dashboard-pty | native-terminal")
    pid: int = Field(..., gt=0, description="OS pid of the live CLI process")
    cli_id: str = Field(default="claude", min_length=1, description="claude | codex | gemini")

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    @field_validator("surface")
    @classmethod
    def _valid_surface(cls, value: str) -> str:
        if value not in _VALID_SURFACES:
            raise ValueError(f"surface must be one of: {', '.join(sorted(_VALID_SURFACES))}")
        return value


class SessionReleaseInput(BaseModel):
    """Input for releasing a local owner for a CLI session id."""

    session_id: str = Field(..., min_length=1, description="CLI session id to release")
    surface: str = Field(..., description="surface releasing the claim")
    pid: int | None = Field(default=None, gt=0, description="Optional pid that must match the owner")

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    @field_validator("surface")
    @classmethod
    def _valid_surface(cls, value: str) -> str:
        if value not in _VALID_SURFACES:
            raise ValueError(f"surface must be one of: {', '.join(sorted(_VALID_SURFACES))}")
        return value


class SessionStatusInput(BaseModel):
    """Input for reading the local session-owner registry."""

    session_id: str | None = Field(default=None, description="Optional session id filter")

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


def _registry_path() -> Path:
    from src.config.paths import get_runtime_dir

    return get_runtime_dir() / "state" / "session-owners.json"


def _lock_path() -> Path:
    path = _registry_path()
    return path.with_name(f"{path.name}.lock")


def _host_id() -> str:
    return socket.gethostname()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lock_file(lock_file) -> None:
    if os.name == "nt":
        import msvcrt

        lock_file.seek(0)
        if lock_file.read(1) == b"":
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        return

    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def _unlock_file(lock_file) -> None:
    if os.name == "nt":
        import msvcrt

        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def _locked_registry():
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path()
    with _LOCK:
        with lock_path.open("a+b") as lock_file:
            _lock_file(lock_file)
            try:
                yield
            finally:
                _unlock_file(lock_file)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import psutil

        return psutil.pid_exists(pid)
    except Exception:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True


def _proc_start_time(pid: int) -> str | None:
    try:
        import psutil

        return str(psutil.Process(pid).create_time())
    except Exception:
        return None


def _load() -> dict[str, dict[str, Any]]:
    path = _registry_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): value for key, value in data.items() if isinstance(value, dict)}


def _atomic_save(data: dict[str, Any]) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.write(payload)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def _is_live_local_owner(owner: dict[str, Any]) -> bool:
    if owner.get("host") != _host_id():
        return False
    pid = owner.get("pid")
    if not isinstance(pid, int) or not _pid_alive(pid):
        return False
    expected_start = owner.get("proc_start_time")
    current_start = _proc_start_time(pid)
    if current_start is None:
        return True
    return not expected_start or expected_start == current_start


def _public_owner(owner: dict[str, Any] | None) -> dict[str, Any] | None:
    if owner is None or not _is_live_local_owner(owner):
        return None
    return dict(owner)


def _same_process(owner: dict[str, Any], *, surface: str, pid: int) -> bool:
    if owner.get("surface") != surface or owner.get("pid") != pid:
        return False
    expected_start = owner.get("proc_start_time")
    current_start = _proc_start_time(pid)
    return current_start is None or not expected_start or expected_start == current_start


def _release_matches(owner: dict[str, Any], params: SessionReleaseInput) -> bool:
    if owner.get("host") != _host_id() or owner.get("surface") != params.surface:
        return False
    if params.pid is None:
        return not _is_live_local_owner(owner)
    return _same_process(owner, surface=params.surface, pid=params.pid)


def _prune_stale_local_owners(registry: dict[str, dict[str, Any]]) -> bool:
    changed = False
    for session_id, owner in list(registry.items()):
        if owner.get("host") == _host_id() and not _is_live_local_owner(owner):
            registry.pop(session_id, None)
            changed = True
    return changed


async def session_claim_impl(params: SessionClaimInput) -> str:
    """Claim a session id for the calling local process."""

    with _locked_registry():
        registry = _load()
        existing = registry.get(params.session_id)
        existing_same_process = False
        if existing and _is_live_local_owner(existing):
            existing_same_process = _same_process(existing, surface=params.surface, pid=params.pid)
            if not existing_same_process:
                return json.dumps({"ok": False, "conflict": _public_owner(existing)}, indent=2)

        now = _now()
        owner = {
            "session_id": params.session_id,
            "surface": params.surface,
            "pid": params.pid,
            "host": _host_id(),
            "cli_id": params.cli_id,
            "started_at": existing.get("started_at") if existing_same_process and existing else now,
            "proc_start_time": _proc_start_time(params.pid),
            "last_seen": now,
        }
        registry[params.session_id] = owner
        _atomic_save(registry)
        return json.dumps({"ok": True, "session_id": params.session_id, "owner": owner}, indent=2)


async def session_release_impl(params: SessionReleaseInput) -> str:
    """Release the local owner if it matches the releasing surface."""

    with _locked_registry():
        registry = _load()
        existing = registry.get(params.session_id)
        released = False
        if existing and _release_matches(existing, params):
            registry.pop(params.session_id, None)
            _atomic_save(registry)
            released = True
        return json.dumps({"ok": True, "released": released}, indent=2)


async def session_status_impl(params: SessionStatusInput) -> str:
    """Return the live local owner for one session or all sessions."""

    with _locked_registry():
        registry = _load()
        changed = _prune_stale_local_owners(registry)
        if changed:
            _atomic_save(registry)
        if params.session_id:
            return json.dumps({"ok": True, "owner": _public_owner(registry.get(params.session_id))}, indent=2)
        owners = {session_id: owner for session_id, owner in registry.items() if _public_owner(owner) is not None}
        return json.dumps({"ok": True, "owners": owners}, indent=2)

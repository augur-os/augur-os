"""AI Monitor Sidecar Manager.

Manages the AI client process that monitors daemon stderr logs and vault repo.
Uses build_sidecar_cmd() for interactive session invocation and resolve_cli()
for multi-client resolution.
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
import logging
import os
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from subprocess import DEVNULL, Popen
from typing import Any, Optional

# Windows: spawn the sidecar CLI without a visible console window. The daemon
# parent runs under pythonw.exe (no console), so a console-subsystem child would
# otherwise pop its own window. 0 on POSIX (the pty branch handles that case).
_NO_WINDOW_CREATIONFLAGS = (
    getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
)

from src.config.paths import get_logs_dir, get_runtime_dir, get_vault_dir
from src.lib.llm_retry import build_sidecar_cmd, resolve_cli

logger = logging.getLogger("augur.daemon.ai_sidecar")

MONITOR_PROMPT = """You are the Augur daemon AI monitor sidecar.

Run as a persistent monitoring loop without asking the user for routine approval.

1. Read current state:
   python3 project-brain/capabilities/skills/daemon/scripts/ai_monitor_watcher.py --status
2. Loop forever:
   python3 project-brain/capabilities/skills/daemon/scripts/ai_monitor_watcher.py --wait-for-event --timeout 300
3. If the watcher returns a timeout event, run:
   python3 project-brain/capabilities/skills/daemon/scripts/ai_monitor_watcher.py --vault-check
   Then continue the loop.
4. If the watcher returns an actionable runtime error, acquire the fix lock,
   inspect the real cause, make the smallest correct fix, verify it, commit with
   a fix(self-heal): prefix when a commit is appropriate, and record the result
   with ai_monitor_watcher.py --record-fix.

Use the instructions in project-brain/capabilities/skills/daemon/SKILL.md Monitor Sidecar Mode as the policy source.
"""


class AISidecarManager:
    """Manages the AI client sidecar process."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.enabled = config.get("enabled", True)
        self.pressure_threshold = config.get("context_pressure_bytes", 500_000)
        self.process: Optional[Popen] = None
        self.state = "stopped"  # stopped | running | unavailable | disabled
        self.restart_delay = 30
        self.max_restart_delay = 960  # 32x base
        self.consecutive_failures = 0
        self.total_restarts = 0
        self.restart_timestamps: list[float] = []
        self.max_restarts_per_hour = 3
        self.last_started: Optional[str] = None
        self._last_started_ts: Optional[float] = None
        self._stderr_file: Any = None
        self._pty_master_fd: int | None = None
        self._pty_reader_thread: threading.Thread | None = None

        # Set by daemon after init
        self._state_dir: Optional[Path] = None
        self._fix_lock_file: Optional[Path] = None
        self._stderr_logs_dir: Optional[Path] = None
        self._project_root: Optional[Path] = None
        self._env: dict[str, str] = dict(os.environ)

    def start(self) -> bool:
        """Start the AI client sidecar."""
        if not self.enabled:
            self.state = "disabled"
            return False

        if self.process and self.process.poll() is None:
            return True

        try:
            cli_path = resolve_cli(search_path=self._env.get("PATH"))
        except RuntimeError as e:
            logger.warning("No AI client available, skipping sidecar: %s", e)
            self.state = "unavailable"
            return False

        try:
            cmd = build_sidecar_cmd(
                cli_path,
                MONITOR_PROMPT,
                allowed_tools="Read,Edit,Bash,Grep,Glob,Write",
                additional_dirs=self._additional_dirs(),
                bypass_approvals=True,
            )

            # Close stale stderr handle from a previous crashed run
            self._close_stderr()

            if self._stderr_logs_dir:
                self._stderr_logs_dir.mkdir(parents=True, exist_ok=True)
                stderr_path = self._stderr_logs_dir / "ai_monitor.stderr.log"
                self._stderr_file = open(stderr_path, "a")  # noqa: SIM115
            else:
                self._stderr_file = DEVNULL

            process_env = {**self._env, "PYTHONUNBUFFERED": "1", "TERM": self._env.get("TERM", "xterm-256color")}
            if self.config.get("use_pty", True) and os.name == "posix":
                self.process = self._popen_with_pty(cmd, process_env)
            else:
                self.process = Popen(
                    cmd,
                    cwd=str(self._project_root) if self._project_root else None,
                    stdout=DEVNULL,
                    stderr=self._stderr_file,
                    env=process_env,
                    creationflags=_NO_WINDOW_CREATIONFLAGS,
                )
            self.state = "running"
            self._last_started_ts = time.time()
            self.last_started = datetime.now().isoformat()
            self._reset_bytes_counter()
            logger.info("AI sidecar started (PID %s)", self.process.pid)
            return True
        except Exception as e:
            logger.error("Failed to start AI sidecar: %s", e)
            self._close_stderr()
            self.state = "unavailable"
            return False

    def stop(self, timeout: int = 10) -> None:
        """Gracefully stop the sidecar."""
        if not self.process or self.process.poll() is not None:
            self.state = "stopped"
            self.process = None
            return

        pid = self.process.pid
        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=timeout)
            except Exception:
                self.process.kill()
                self.process.wait(timeout=5)
        except Exception as e:
            logger.error("Error stopping sidecar: %s", e)

        self.process = None
        self._close_stderr()
        self.state = "stopped"
        logger.info("AI sidecar stopped (was PID %s)", pid)

    def check_health(self) -> dict[str, Any]:
        """Check sidecar health, handle restarts and context pressure."""
        if not self.enabled:
            return self._status_dict()

        if not self.process:
            if self.state in {"stopped", "unavailable", "exited"}:
                self._maybe_restart()
            return self._status_dict()

        exit_code = self.process.poll()
        if exit_code is None:
            # Running — check context pressure
            if self._check_context_pressure():
                if not self._fix_lock_held():
                    logger.info("Context pressure threshold reached, restarting sidecar")
                    self.stop()
                    self.start()
            # Reset failures after 60s uptime
            if self._last_started_ts and self.consecutive_failures > 0:
                if time.time() - self._last_started_ts > 60:
                    self.consecutive_failures = 0
            return self._status_dict()

        # Process exited
        self.process = None
        self._close_stderr()
        self.state = "exited"
        self.consecutive_failures += 1
        logger.warning("AI sidecar exited (code %s)", exit_code)
        self._maybe_restart()
        return self._status_dict()

    def _maybe_restart(self) -> None:
        if self.consecutive_failures >= 10:
            self.state = "unavailable"
            return
        now = time.time()
        one_hour_ago = now - 3600
        self.restart_timestamps = [t for t in self.restart_timestamps if t > one_hour_ago]
        if len(self.restart_timestamps) >= self.max_restarts_per_hour:
            self.state = "unavailable"
            return
        delay = self.restart_delay * (2 ** min(self.consecutive_failures, 5))
        delay = min(delay, self.max_restart_delay)
        if self._last_started_ts:
            if now - self._last_started_ts < delay:
                return
        self.total_restarts += 1
        self.restart_timestamps.append(now)
        self.start()

    def _check_context_pressure(self) -> bool:
        if not self._state_dir:
            return False
        bytes_file = self._state_dir / "ai_monitor_bytes.json"
        try:
            data = json.loads(bytes_file.read_text())
            return data.get("bytes_outputted", 0) >= self.pressure_threshold
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return False

    def _fix_lock_held(self) -> bool:
        if not self._fix_lock_file:
            return False
        try:
            data = json.loads(self._fix_lock_file.read_text())
            pid = data.get("pid", 0)
            if pid:
                os.kill(pid, 0)
                return True
        except (FileNotFoundError, ProcessLookupError, PermissionError, json.JSONDecodeError):
            pass
        return False

    def _reset_bytes_counter(self) -> None:
        if not self._state_dir:
            return
        bytes_file = self._state_dir / "ai_monitor_bytes.json"
        _atomic_write(bytes_file, json.dumps({"bytes_outputted": 0}))

    def _close_stderr(self) -> None:
        self._close_pty()
        if self._stderr_file is not None and self._stderr_file is not DEVNULL:
            try:
                self._stderr_file.close()
            except Exception:
                pass
            self._stderr_file = None

    def _popen_with_pty(self, cmd: list[str], env: dict[str, str]) -> Popen:
        """Start an interactive CLI behind a pseudo-terminal and drain output."""
        import pty

        master_fd, slave_fd = pty.openpty()
        self._pty_master_fd = master_fd
        try:
            process = Popen(
                cmd,
                cwd=str(self._project_root) if self._project_root else None,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
            )
        finally:
            os.close(slave_fd)

        self._start_pty_reader()
        return process

    def _start_pty_reader(self) -> None:
        fd = self._pty_master_fd
        if fd is None:
            return

        def drain() -> None:
            while True:
                try:
                    data = os.read(fd, 4096)
                except OSError:
                    break
                if not data:
                    break
                if self._stderr_file is not None and self._stderr_file is not DEVNULL:
                    try:
                        self._stderr_file.write(data.decode("utf-8", errors="replace"))
                        self._stderr_file.flush()
                    except Exception:
                        break

        self._pty_reader_thread = threading.Thread(target=drain, name="ai-monitor-sidecar-pty", daemon=True)
        self._pty_reader_thread.start()

    def _close_pty(self) -> None:
        fd = self._pty_master_fd
        self._pty_master_fd = None
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        thread = self._pty_reader_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1)
        self._pty_reader_thread = None

    def _additional_dirs(self) -> list[str]:
        """Grant the sidecar the non-cwd Augur folders it must monitor."""
        dirs: list[Path] = []
        if self._project_root is not None:
            dirs.append(self._project_root)
        dirs.extend([get_logs_dir(), get_runtime_dir()])
        try:
            dirs.append(get_vault_dir())
        except Exception:
            pass
        for raw_path in self.config.get("additional_dirs", []):
            dirs.append(Path(str(raw_path)).expanduser())

        resolved: list[str] = []
        seen: set[str] = set()
        for directory in dirs:
            path = str(directory)
            if path not in seen:
                resolved.append(path)
                seen.add(path)
        return resolved

    def _status_dict(self) -> dict[str, Any]:
        pid = self.process.pid if self.process and self.process.poll() is None else None
        state = "exited" if self.state == "running" and pid is None else self.state
        return {
            "state": state,
            "pid": pid,
            "total_restarts": self.total_restarts,
            "last_started": self.last_started,
        }


def _atomic_write(path: Path, content: str) -> None:
    """Write file atomically via mkstemp + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.rename(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

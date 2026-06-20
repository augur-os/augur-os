"""
Single Instance Lock for MCP Server

Prevents multiple instances from running simultaneously using a PID file.
"""

from __future__ import annotations

import os
import shutil
import signal
import time
from pathlib import Path
from subprocess import CompletedProcess, run  # nosec B404
from typing import Any

from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("mcp.lock")


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable path to absolute when available.

    Falls back to well-known system paths on macOS/Linux when the executable
    is not on the current PATH (common inside Python venvs where /usr/sbin
    is stripped).
    """
    if not command:
        raise ValueError("Command must not be empty")

    executable = command[0]
    if Path(executable).is_absolute():
        return command

    resolved = shutil.which(executable)
    if resolved:
        return [resolved, *command[1:]]

    # Fallback: check standard system directories not always on venv PATH
    for sysdir in ("/usr/sbin", "/usr/bin", "/sbin", "/bin"):
        candidate = Path(sysdir) / executable
        if candidate.is_file():
            return [str(candidate), *command[1:]]

    return command


def _run_command(command: list[str], **kwargs: Any) -> CompletedProcess[Any]:
    """Run subprocess command with resolved executable."""
    return run(_resolve_command(command), **kwargs)  # nosec B603


def _get_canonical_lock_dir() -> Path:
    """Get a canonical lock directory that's consistent across all environments.

    CRITICAL: tempfile.gettempdir() returns different paths depending on whether
    TMPDIR is set in the environment:
    - With TMPDIR: /var/folders/xx/xxx/T (macOS per-user temp)
    - Without TMPDIR: /tmp

    This causes duplicate MCP instances when one is started with TMPDIR and
    another without it. We use /tmp as the canonical location to ensure
    all processes check the same directory.
    """
    # Always use /tmp on Unix-like systems for consistency.
    if os.name != "nt":  # Not Windows
        return Path("/tmp")  # nosec B108
    # On Windows, use the standard temp directory
    import tempfile

    return Path(tempfile.gettempdir())


class InstanceLock:
    """Ensures only one MCP server instance per client (for stdio transport)."""

    def __init__(self, lock_dir: Path | None = None, client_id: str | None = None, port: int | None = None):
        """
        Initialize instance lock.

        Args:
            lock_dir: Directory for PID file (default: /tmp for consistency)
            client_id: Unique client identifier (e.g., "claude", "cursor", "vscode")
                      If None, uses global lock (prevents ALL instances)
            port: Port number for worktree isolation. If provided, uses port-specific
                  lock file (augur-mcp-port{port}.pid). Callers that want MCP_PORT
                  env var support must resolve it themselves before passing it here.
        """
        if lock_dir is None:
            lock_dir = _get_canonical_lock_dir()

        if port:
            self.lock_file = lock_dir / f"augur-mcp-port{port}.pid"
        elif client_id:
            self.lock_file = lock_dir / f"augur-mcp-{client_id}.pid"
        else:
            self.lock_file = lock_dir / "augur-mcp.pid"

        self.client_id = client_id
        self.port = port
        self.acquired = False

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with given PID is running AND is an augur MCP process.

        Returns False for zombie/defunct processes and for PIDs that have been
        reused by unrelated processes (PID reuse after crash).
        """
        if not _is_pid_alive(pid):
            return False
        # Guard against PID reuse: if the process is alive but isn't augur MCP,
        # the lock is stale from a recycled PID.
        if not _is_augur_mcp_process(pid):
            logger.info(f"PID {pid} is alive but not an augur MCP process (PID reuse), treating lock as stale")
            return False
        return True

    def _read_pid(self) -> int | None:
        """Read PID from lock file, return None if invalid."""
        try:
            pid_str = self.lock_file.read_text().strip()
            return int(pid_str)
        except (FileNotFoundError, ValueError, OSError):
            return None

    def _write_pid(self):
        """Write current process PID to lock file."""
        try:
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            self.lock_file.write_text(f"{os.getpid()}\n")
        except Exception as e:
            logger.error(f"Failed to write PID file: {e}")
            raise

    def _check_legacy_lock(self) -> tuple[Path | None, int | None]:
        """Check for a lock file in the legacy temp directory.

        Historical MCP processes may have created locks in a different temp
        directory (e.g., /var/folders/.../T vs /tmp) depending on TMPDIR.
        This method checks for such legacy locks to prevent duplicate instances.

        Returns:
            Tuple of (legacy_lock_path, pid) if found and alive, else (None, None)
        """
        import tempfile

        legacy_dir = Path(tempfile.gettempdir())

        if legacy_dir == self.lock_file.parent:
            return None, None

        legacy_lock = None
        if self.port:
            legacy_lock = legacy_dir / f"augur-mcp-port{self.port}.pid"
        elif self.client_id:
            legacy_lock = legacy_dir / f"augur-mcp-{self.client_id}.pid"
        else:
            legacy_lock = legacy_dir / "augur-mcp.pid"

        if not legacy_lock.exists():
            return None, None

        try:
            pid = int(legacy_lock.read_text().strip())
            if _is_pid_alive(pid):
                return legacy_lock, pid
            else:
                legacy_lock.unlink(missing_ok=True)
                logger.info(f"Cleaned up stale legacy lock: {legacy_lock}")
        except (ValueError, OSError):
            legacy_lock.unlink(missing_ok=True)

        return None, None

    def acquire(self, force: bool = False, wait_timeout: float = 5.0) -> bool:
        """
        Acquire the instance lock.

        Args:
            force: Force acquire even if another instance is running (kill it)
            wait_timeout: Seconds to wait for lock before failing (0 = no wait)

        Returns:
            True if lock acquired, False otherwise

        Raises:
            RuntimeError: If lock cannot be acquired and force=False
        """
        start_time = time.time()

        # 0. Check for legacy lock in different temp directory
        legacy_lock, legacy_pid = self._check_legacy_lock()
        if legacy_lock and legacy_pid:
            if force:
                logger.warning(f"Force killing legacy instance (PID {legacy_pid}) at {legacy_lock}...")
                try:
                    os.kill(legacy_pid, signal.SIGTERM)
                    time.sleep(1)
                    if _is_pid_alive(legacy_pid):
                        os.kill(legacy_pid, signal.SIGKILL)
                    legacy_lock.unlink(missing_ok=True)
                except Exception as e:
                    logger.error(f"Failed to kill legacy instance: {e}")
                    raise RuntimeError(f"Cannot kill legacy instance (PID {legacy_pid}): {e}") from e
            else:
                # Legacy instance is running - treat it like a normal lock conflict
                logger.error(
                    f"Another MCP server instance is already running (PID {legacy_pid}). "
                    f"Legacy lock file: {legacy_lock}"
                )
                raise RuntimeError(
                    f"Another instance already running (PID {legacy_pid}). Use --force to kill it, or stop it manually."
                )

        while True:
            # 1. Try to atomically create/lock the file
            try:
                # O_CREAT | O_EXCL ensures we only succeed if file doesn't exist
                # This eliminates the race where two processes check .exists() at same time
                fd = os.open(self.lock_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
                with os.fdopen(fd, "w") as f:
                    f.write(f"{os.getpid()}\n")
                self.acquired = True
                logger.info(f"Acquired instance lock: {self.lock_file}")
                return True
            except FileExistsError:
                # File exists, fall through to check if it's stale
                pass
            except OSError as e:
                # Other errors (permission, directory missing, etc)
                if not self.lock_file.parent.exists():
                    self.lock_file.parent.mkdir(parents=True, exist_ok=True)
                    continue
                logger.error(f"Failed to acquire lock: {e}")
                raise

            # 2. Lock exists - check if valid/stale
            existing_pid = self._read_pid()

            if existing_pid is None:
                # Invalid PID file - clean up and retry
                logger.warning("Found invalid PID file, cleaning up...")
                self.lock_file.unlink(missing_ok=True)
                continue

            if existing_pid == os.getpid():
                # We already own the lock
                self.acquired = True
                return True

            # Check if the process is still running
            if not self._is_process_running(existing_pid):
                # Stale lock from crashed process
                logger.warning(f"Found stale PID file (PID {existing_pid} not running), cleaning up...")
                self.lock_file.unlink(missing_ok=True)
                continue

            # Another instance is running
            if force:
                logger.warning(f"Force killing existing instance (PID {existing_pid})...")
                try:
                    os.kill(existing_pid, signal.SIGTERM)
                    time.sleep(1)  # Give it time to die gracefully
                    if self._is_process_running(existing_pid):
                        os.kill(existing_pid, signal.SIGKILL)
                    self.lock_file.unlink(missing_ok=True)
                    continue
                except Exception as e:
                    logger.error(f"Failed to kill existing instance: {e}")
                    raise RuntimeError(f"Cannot kill existing instance (PID {existing_pid}): {e}") from e

            # Wait or fail — exponential backoff (0.5s, 1s, 2s, 2s, ...)
            elapsed = time.time() - start_time
            if wait_timeout > 0 and elapsed < wait_timeout:
                # After waiting > half the timeout, check if holder is orphaned
                # (broken stdin pipe or reparented to init). This catches cases
                # where the pre-check in ensure_single_instance missed the orphan
                # (e.g., lsof timing, pipe state race).
                if elapsed > wait_timeout / 2 and _is_stdio_orphaned(existing_pid):
                    logger.warning(
                        f"Lock holder (PID {existing_pid}) detected as orphaned during wait, force-replacing..."
                    )
                    try:
                        os.kill(existing_pid, signal.SIGTERM)
                        time.sleep(0.5)
                        if _is_pid_alive(existing_pid):
                            os.kill(existing_pid, signal.SIGKILL)
                        self.lock_file.unlink(missing_ok=True)
                        continue
                    except Exception as e:
                        logger.warning(f"Failed to kill orphaned instance: {e}")

                attempt = int(elapsed / 0.5) + 1
                backoff = min(0.5 * (2 ** (attempt - 1)), 2.0)
                logger.info(
                    f"Another instance running (PID {existing_pid}), "
                    f"waiting... ({elapsed:.1f}/{wait_timeout}s, backoff={backoff:.1f}s)"
                )
                time.sleep(backoff)
                continue

            # Timeout or no wait
            logger.error(
                f"Another MCP server instance is already running (PID {existing_pid}). Lock file: {self.lock_file}"
            )
            raise RuntimeError(
                f"Another instance already running (PID {existing_pid}). Use --force to kill it, or stop it manually."
            )

    def release(self):
        """Release the instance lock."""
        if not self.acquired:
            return

        try:
            # Only delete if it's our PID
            existing_pid = self._read_pid()
            if existing_pid == os.getpid():
                self.lock_file.unlink(missing_ok=True)
                logger.info("Released instance lock")
            else:
                logger.warning(f"PID file contains different PID ({existing_pid} vs {os.getpid()}), not deleting")
        except Exception as e:
            logger.warning(f"Failed to release lock: {e}")
        finally:
            self.acquired = False

    def __enter__(self):
        """Context manager entry."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()


def _is_pid_alive(pid: int) -> bool:
    """Check if a PID is alive and not a zombie. Shared by cleanup and lock."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False

    # Detect zombie/defunct processes
    try:
        result = _run_command(
            ["ps", "-o", "state=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.stdout.strip().startswith("Z"):
            return False
    except Exception:
        return True

    return True


def cleanup_stale_pid_files() -> int:
    """Remove stale PID files from previous crashed sessions.

    Scans for ALL augur-mcp-*.pid files (both client-named and pid-based)
    and removes any whose process is no longer running or is a zombie.

    IMPORTANT: Checks BOTH /tmp and tempfile.gettempdir() because historical
    processes may have created lock files in either location depending on
    whether TMPDIR was set in their environment.

    Returns:
        Number of stale files removed.
    """
    import tempfile

    # Check both the canonical lock dir (/tmp) and the environment-specific temp dir
    # This handles legacy lock files created before we standardized on /tmp
    dirs_to_check = {_get_canonical_lock_dir(), Path(tempfile.gettempdir())}

    removed = 0
    killed = 0
    for lock_dir in dirs_to_check:
        if not lock_dir.exists():
            continue
        for pid_file in lock_dir.glob("augur-mcp-*.pid"):
            try:
                pid_str = pid_file.read_text().strip()
                pid = int(pid_str)
                if not _is_pid_alive(pid):
                    pid_file.unlink(missing_ok=True)
                    removed += 1
                    logger.debug(f"Removed stale PID file: {pid_file} (PID {pid} not running)")
                elif not _is_augur_mcp_process(pid):
                    # PID is alive but belongs to a different process (PID reuse)
                    pid_file.unlink(missing_ok=True)
                    removed += 1
                    logger.debug(f"Removed stale PID file: {pid_file} (PID {pid} reused by non-MCP process)")
                elif _is_stdio_orphaned(pid):
                    # Process is alive but orphaned (stdin broken or parent chain broken).
                    # Kill it and remove the lock so it doesn't block new instances.
                    logger.info(f"Killing orphaned MCP instance (PID {pid}), stdin/parent broken: {pid_file}")
                    try:
                        os.kill(pid, signal.SIGTERM)
                        # Brief wait for graceful shutdown
                        time.sleep(0.3)
                        if _is_pid_alive(pid):
                            os.kill(pid, signal.SIGKILL)
                        killed += 1
                    except (ProcessLookupError, PermissionError):
                        pass
                    pid_file.unlink(missing_ok=True)
                    removed += 1
                    logger.debug(f"Removed orphaned PID file: {pid_file} (PID {pid} orphaned)")
            except (ValueError, OSError):
                # Invalid PID file, remove it
                pid_file.unlink(missing_ok=True)
                removed += 1
                logger.debug(f"Removed invalid PID file: {pid_file}")

    if removed:
        logger.info(f"Cleaned up {removed} stale PID file(s)")
    return removed


def _is_augur_mcp_process(pid: int) -> bool:
    """Check if a PID belongs to an augur MCP server process.

    Validates that the lock holder is actually our process, not a
    recycled PID from an unrelated process. This prevents stale locks
    from blocking startup when the OS reuses the PID.

    Returns:
        True if the process command line contains augur_mcp indicators.
        False if the process is not ours or cannot be checked.
    """
    try:
        result = _run_command(
            ["ps", "-o", "args=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
        )
        args_lower = result.stdout.strip().lower()
        if not args_lower:
            return False
        # Match common augur MCP invocation patterns
        return "augur_mcp" in args_lower or "augur-mcp" in args_lower
    except Exception:
        # Can't verify — assume it's ours to be safe
        return True


def _is_stdin_pipe_broken(pid: int) -> bool:
    """Check if a process's stdin (fd 0) pipe or socket is broken or closed.

    For stdio MCP servers, the client communicates over stdin/stdout.
    Depending on the client, stdin may be a pipe (Claude Code) or a unix
    domain socket (Claude Desktop).  When the client closes the connection
    (e.g., restart, reload), the pipe/socket breaks but the process may
    linger.  We detect this via lsof.

    Returns:
        True if stdin appears broken or cannot be checked.
    """
    try:
        result = _run_command(
            ["lsof", "-p", str(pid), "-a", "-d", "0"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        # If lsof returns no output for fd 0, stdin is closed
        if result.returncode != 0 or not result.stdout.strip():
            return True
        output_lower = result.stdout.lower()
        if "/dev/null" in output_lower:
            return True  # Redirected to /dev/null — effectively broken
        # PIPE type — stdin is connected via a pipe (e.g., Claude Code)
        if "pipe" in output_lower:
            return False
        # Unix domain socket — used by Claude Desktop and similar clients.
        # A connected socket shows "->0x<nonzero>" peer address.
        # A disconnected socket shows "->0x0" or no peer arrow at all.
        if "unix" in output_lower:
            # Check for a live peer connection (->0x followed by non-zero hex)
            import re

            if re.search(r"->0x[1-9a-f]", output_lower):
                return False  # Peer is connected
            return True  # No peer or peer is 0x0 — socket disconnected
        # fd 0 exists but isn't a pipe or unix socket — unusual but not broken
        return False
    except Exception:
        # Can't check — assume not broken to avoid false positives
        return False


def _is_stdio_orphaned(pid: int) -> bool:
    """Check if a stdio MCP process is orphaned (stdin closed/broken).

    For stdio transport, the MCP server communicates with the client over
    stdin/stdout.  The definitive signal is the state of the stdin fd:

      - If stdin is broken (pipe closed, socket disconnected) → orphaned.
      - If stdin is connected (pipe open, socket peer alive) → NOT orphaned.

    Parent-chain walking is deliberately NOT used because it causes false
    positives for Claude Desktop: the intermediate "disclaimer" wrapper
    may exit after spawning, reparenting the MCP process to launchd (PID 1),
    while the Unix socket connection between Claude Desktop and the MCP
    server remains perfectly healthy.
    """
    return _is_stdin_pipe_broken(pid)


def ensure_single_instance(
    force: bool = False,
    wait_timeout: float = 0,
    client_id: str | None = None,
    transport: str = "stdio",
    port: int | None = None,
) -> InstanceLock:
    """
    Ensure only one MCP server instance per client (stdio) or globally (SSE/HTTP).

    For stdio transport (default):
        - Each client (Claude.ai, Cursor, etc.) can have its own server instance
        - Lock file is client-specific: augur-mcp-{client_id}.pid
        - Prevents duplicate instances from the SAME client
        - Allows instances from DIFFERENT clients
        - If an existing instance has a broken stdin (orphaned), force-replaces it

    For SSE/HTTP transport:
        - Only ONE server instance for all clients
        - Lock file is global: augur-mcp.pid
        - All clients connect to the same server

    For worktree isolation (port provided):
        - Lock file is port-specific: augur-mcp-port{port}.pid
        - Allows multiple worktrees to run concurrently on different ports
        - Port can be provided directly or via MCP_PORT environment variable

    Args:
        force: Force start even if another instance exists (kill it)
        wait_timeout: Seconds to wait for existing instance to exit
        client_id: Client identifier (e.g., "claude", "cursor")
                  Auto-detected from PPID if not provided
        transport: Transport type ("stdio", "sse", "http")
        port: Port number for worktree isolation. Takes priority over client_id.
              Also read from MCP_PORT environment variable if not provided.

    Returns:
        InstanceLock that must be released on shutdown

    Raises:
        RuntimeError: If another instance is running and force=False
    """
    # Resolve MCP_PORT env var only for non-stdio transports or when explicitly
    # provided.  Stdio clients each get their own client-id-based lock and must
    # NOT inherit MCP_PORT from a parent process (e.g., dashboard Next.js sets
    # MCP_PORT=8080 which would make all child Claude Code sessions collide
    # with the dashboard's port-based lock).
    if port is None and transport not in ("stdio",):
        port_str = os.environ.get("MCP_PORT")
        if port_str:
            try:
                port = int(port_str)
            except ValueError:
                logger.warning(f"Invalid MCP_PORT environment variable: {port_str}")

    if transport in ("sse", "http", "streamable-http") and port is None:
        lock = InstanceLock(client_id=None)
    else:
        lock_client_id = _resolve_lock_client_id(client_id=client_id, transport=transport, port=port)
        lock = InstanceLock(client_id=lock_client_id, port=port)

    # For stdio transport with named client IDs (not pid-based), check if
    # the existing instance is orphaned or stale. Stdio is point-to-point:
    # if a new session is starting, the old instance's pipe is broken and useless.
    if transport == "stdio" and lock.client_id and not lock.client_id.startswith("pid") and not force:
        existing_pid = lock._read_pid()
        if existing_pid and _is_pid_alive(existing_pid):
            # Check 1: PID reuse — the process is alive but is NOT an augur MCP server.
            # This happens when the OS recycles the PID after a crash.
            if not _is_augur_mcp_process(existing_pid):
                logger.info(
                    f"Lock holder PID {existing_pid} is not an augur MCP process (PID reuse), cleaning stale lock..."
                )
                lock.lock_file.unlink(missing_ok=True)
                # Don't set force — just removed the stale file, acquire will succeed normally
            # Check 2: The process IS augur MCP but its stdin pipe is broken (orphaned).
            elif _is_stdio_orphaned(existing_pid):
                logger.info(f"Existing instance (PID {existing_pid}) is orphaned (stdin closed), force-replacing...")
                force = True

    lock.acquire(force=force, wait_timeout=wait_timeout)
    return lock


def _sanitize_lock_token(value: str, max_len: int = 64) -> str:
    """Sanitize token for lock-file-safe client IDs."""
    import re

    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")
    return safe[:max_len]


def _resolve_lock_client_id(client_id: str | None, transport: str, port: int | None) -> str | None:
    """Resolve lock identity for this process.

    Stdio transport is point-to-point: each session needs its own MCP server.
    Static client IDs like ``cowork`` or ``codex`` create shared lock files
    that cause false startup conflicts when the previous instance is still
    alive (e.g. orphaned process, manual test, or a new session starting
    before the old one exits).  We derive per-session lock IDs for these
    clients so each launch gets its own lock, and ``cleanup_stale_pid_files``
    removes dead ones on startup.
    """
    if transport != "stdio" or port is not None:
        return client_id

    if client_id is None:
        return _detect_client_id()

    # Codex: derive per-session lock from thread ID when available.
    # When Desktop does not propagate CODEX_THREAD_ID, parent PID is too coarse:
    # every MCP child launched by the same app-server collapses onto one shared
    # lock file and causes false duplicate-instance conflicts. Fall back to the
    # MCP process PID instead so stdio launches remain point-to-point.
    if client_id == "codex":
        thread_id = _sanitize_lock_token(os.environ.get("CODEX_THREAD_ID", ""))
        if thread_id:
            return f"codex-{thread_id}"
        return f"codex-pid{os.getpid()}"

    # Cowork (Claude Desktop): each launch gets a per-PID lock so a new
    # session is never blocked by an orphaned or manually-started instance.
    if client_id == "cowork":
        return f"cowork-{os.getpid()}"

    # OpenCode: stdio MCP launches are point-to-point like Codex. A shared
    # "opencode" lock causes false duplicate-instance conflicts because one
    # background session blocks every later CLI probe or reconnect.
    if client_id == "opencode":
        return f"opencode-pid{os.getpid()}"

    return client_id


def _detect_client_id() -> str:
    """
    Auto-detect client ID from environment variables and parent process.

    First checks environment variables set by known clients (most reliable),
    then walks up the parent chain as fallback.

    Returns:
        Client identifier (e.g., "claude-desktop-{ppid}", "claude-code-{ppid}")
    """
    import os

    # --- Phase 1: Environment variable detection (most reliable) ---
    # Claude Desktop sets CLAUDE_DESKTOP; its wrapper ("disclaimer") may exit
    # after spawning, breaking parent-chain detection, so env var is critical.
    if os.environ.get("CLAUDE_DESKTOP"):
        return f"claude-desktop-{os.getpid()}"
    if os.environ.get("CURSOR_SESSION_ID"):
        return f"cursor-{os.getpid()}"
    if os.environ.get("WINDSURF_SESSION_ID") or os.environ.get("CODEIUM_SESSION"):
        return f"windsurf-{os.getpid()}"

    # --- Phase 2: Parent process chain detection (fallback) ---
    current = os.getpid()
    try:
        for _ in range(3):
            ppid_result = _run_command(
                ["ps", "-o", "ppid=", "-p", str(current)],
                capture_output=True,
                text=True,
                timeout=1,
            )
            ppid_str = ppid_result.stdout.strip()
            if not ppid_str:
                break
            ppid = int(ppid_str)
            if ppid <= 1:
                break

            args_result = _run_command(
                ["ps", "-o", "args=", "-p", str(ppid)],
                capture_output=True,
                text=True,
                timeout=1,
            )
            parent_args = args_result.stdout.strip().lower()

            # Stdio transport is point-to-point: each session needs its own
            # MCP server. Append the client process PID to allow concurrent
            # sessions from the same client app (e.g. two Kimi windows).
            if "kimi" in parent_args:
                return f"kimi-{ppid}"
            elif "gemini" in parent_args:
                return f"gemini-{ppid}"
            elif "claude.app" in parent_args:
                return f"claude-desktop-{ppid}"
            elif "claude" in parent_args or "disclaimer" in parent_args:
                return f"claude-code-{ppid}"
            elif "cursor" in parent_args:
                return f"cursor-{ppid}"
            elif "vscode" in parent_args or "/code" in parent_args:
                return f"vscode-{ppid}"

            current = ppid
    except Exception as e:
        logger.debug(f"Client auto-detection failed, falling back to pid-based client id: {e}")

    # Fallback: use PID as unique identifier (allows concurrent instances)
    return f"pid{os.getpid()}"

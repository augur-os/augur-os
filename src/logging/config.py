"""
Centralized logging configuration for all Augur entities.

Provides entity-specific loggers with:
- Hourly rotating file handlers
- Separate error logs
- JSON formatting for structured logs
- Colored console output
- Correlation ID support

All retention settings are centralized in src/lib/config/log_retention.py
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

from src.config.paths import get_logs_dir
from src.config.log_retention import LOG_RETENTION
from .formatters import JSONFormatter, ColoredFormatter
from .correlation import get_correlation_id

# Cache PID once at module level — it never changes within a process.
_PID = os.getpid()
_SUPPRESSED_IO_ERRNOS = {
    getattr(os, "ENOSPC", 28),
    getattr(os, "EROFS", 30),
    getattr(os, "EIO", 5),
    getattr(os, "EPIPE", 32),
    getattr(os, "EBADF", 9),
    getattr(os, "EACCES", 13),
    getattr(os, "EPERM", 1),
}


def _is_suppressed_io_error(exc: BaseException | None) -> bool:
    if isinstance(exc, PermissionError):
        return True
    return isinstance(exc, OSError) and exc.errno in _SUPPRESSED_IO_ERRNOS


class _DateAwareFileHandler(logging.FileHandler):
    """FileHandler that rotates to a new date directory at midnight.

    Long-running daemon processes (started on day N) must write logs to
    the correct date directory on day N+1, N+2, etc.  This handler checks
    the current date on each emit() and transparently switches the
    underlying file when the date changes.

    Also re-creates the parent directory if it was removed by nightly
    cleanup (resilient behaviour).
    """

    def __init__(self, entity_base_dir: str, filename_pattern: str, **kwargs):
        self._entity_base_dir = Path(entity_base_dir)
        self._filename_pattern = filename_pattern  # e.g. "errors_{pid}.log"
        self._current_date = datetime.now().strftime("%Y-%m-%d")
        log_dir = self._entity_base_dir / self._current_date
        log_dir.mkdir(parents=True, exist_ok=True)
        filepath = str(log_dir / filename_pattern)
        # Lazy-open: don't create empty files for processes that never emit.
        # Short-lived spawns (configure_mcp, plugins, knowledge.*) were
        # creating thousands of zero-byte files per day.
        kwargs.setdefault("delay", True)
        super().__init__(filepath, **kwargs)

    def _rotate_if_needed(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_date:
            self._current_date = today
            new_dir = self._entity_base_dir / today
            new_dir.mkdir(parents=True, exist_ok=True)
            new_path = str(new_dir / self._filename_pattern)
            # Close old file, open new one
            if self.stream:
                self.stream.close()
            self.baseFilename = os.fspath(new_path)
            self.stream = self._open()
            # Update the "latest" symlink
            _update_latest_symlink(self._entity_base_dir, new_dir)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._rotate_if_needed()
        except OSError as exc:
            if not _is_suppressed_io_error(exc):
                self.handleError(record)
            return
        except ValueError as exc:
            if "closed file" not in str(exc):
                self.handleError(record)
            return
        except Exception:
            self.handleError(record)
            return
        try:
            super().emit(record)
        except OSError as exc:
            if not _is_suppressed_io_error(exc):
                self.handleError(record)
        except ValueError as exc:
            if "closed file" not in str(exc):
                self.handleError(record)
        except Exception:
            self.handleError(record)

    def handleError(self, record: logging.LogRecord) -> None:
        """Suppress unrecoverable I/O errors (disk full, read-only FS, broken pipe) silently."""
        _, exc, _ = sys.exc_info()
        if _is_suppressed_io_error(exc):
            return
        if isinstance(exc, ValueError) and "closed file" in str(exc):
            return
        super().handleError(record)


class _DateAwareRotatingHandler(TimedRotatingFileHandler):
    """TimedRotatingFileHandler that also rotates to a new date directory at midnight.

    Combines hourly file rotation (TimedRotatingFileHandler) with date-based
    directory rotation for long-running daemon processes.
    """

    def __init__(self, entity_base_dir: str, filename_pattern: str, **kwargs):
        self._entity_base_dir = Path(entity_base_dir)
        self._filename_pattern = filename_pattern  # e.g. "17-00_497.log"
        self._current_date = datetime.now().strftime("%Y-%m-%d")
        log_dir = self._entity_base_dir / self._current_date
        log_dir.mkdir(parents=True, exist_ok=True)
        filepath = str(log_dir / filename_pattern)
        # Lazy-open: don't create empty files for processes that never emit.
        kwargs.setdefault("delay", True)
        super().__init__(filepath, **kwargs)

    def rotate(self, source: str, dest: str) -> None:
        """Override rotate() to suppress disk-full and I/O errors gracefully.

        When ENOSPC occurs, skip the rotation and keep logging to the current
        file rather than crashing the handler with '--- Logging error ---'.
        """
        try:
            super().rotate(source, dest)
        except OSError as exc:
            if not _is_suppressed_io_error(exc):
                raise

    def doRollover(self) -> None:
        """Override doRollover() to suppress disk-full errors across the entire rollover.

        Defense-in-depth: rotate() already suppresses ENOSPC during the rename step,
        but self._open() inside doRollover() can also fail with ENOSPC when disk is
        full, leaving self.stream=None and propagating to handleError().  Wrapping
        the whole doRollover() prevents that second source of '--- Logging error ---'.
        """
        try:
            super().doRollover()
        except OSError as exc:
            if not _is_suppressed_io_error(exc):
                raise

    def _rotate_if_needed(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_date:
            self._current_date = today
            new_dir = self._entity_base_dir / today
            new_dir.mkdir(parents=True, exist_ok=True)
            # Build new filename with current hour
            current_hour = datetime.now().strftime("%H-00")
            new_pattern = f"{current_hour}_{_PID}.log"
            self._filename_pattern = new_pattern
            new_path = str(new_dir / new_pattern)
            # Close old file, open new one
            if self.stream:
                self.stream.close()
            self.baseFilename = os.fspath(new_path)
            self.stream = self._open()
            _update_latest_symlink(self._entity_base_dir, new_dir)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._rotate_if_needed()
        except OSError as exc:
            if not _is_suppressed_io_error(exc):
                self.handleError(record)
            return
        except ValueError as exc:
            if "closed file" not in str(exc):
                self.handleError(record)
            return
        except Exception:
            self.handleError(record)
            return
        super().emit(record)

    def handleError(self, record: logging.LogRecord) -> None:
        """Suppress unrecoverable I/O errors (disk full, read-only FS, broken pipe) silently."""
        _, exc, _ = sys.exc_info()
        if _is_suppressed_io_error(exc):
            return
        if isinstance(exc, ValueError) and "closed file" in str(exc):
            return
        super().handleError(record)


def _update_latest_symlink(base_dir: Path, target_dir: Path) -> None:
    """Update the 'latest' symlink to point to the given directory."""
    latest_link = base_dir / "latest"
    try:
        if latest_link.exists() or latest_link.is_symlink():
            if latest_link.is_dir() and not latest_link.is_symlink():
                import shutil

                shutil.rmtree(latest_link)
            else:
                latest_link.unlink(missing_ok=True)
        latest_link.symlink_to(target_dir.resolve())
    except (FileExistsError, OSError, PermissionError, FileNotFoundError):
        pass


class CorrelationIDFilter(logging.Filter):
    """Inject correlation ID into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add correlation ID to log record.

        Args:
            record: LogRecord to enrich

        Returns:
            True (always allow record through)
        """
        record.correlation_id = get_correlation_id()
        return True


class EntityLogger:
    """
    Logger factory for Augur entities.

    Creates entity-specific loggers with hourly rotation, error logs,
    and both JSON (file) and colored (console) output.
    """

    def __init__(self, entity_name: str, log_level: str = "INFO"):
        """
        Initialize entity logger.

        Args:
            entity_name: Name of entity (e.g., "cli", "mcp", "skills/careers")
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.entity_name = entity_name
        self.log_level = log_level
        self.file_logging_error: str | None = None
        try:
            self.log_dir = self._get_log_dir()
        except (OSError, PermissionError) as exc:
            self.log_dir = None
            self.file_logging_error = str(exc)
        self._setup_logger()

    def _get_base_log_dir(self) -> Path:
        """Get the base (non-dated) log directory for this entity.

        Returns: <logs>/{entity}/
        """
        return get_logs_dir() / self.entity_name

    def _get_log_dir(self) -> Path:
        """
        Get log directory for this entity with date-based structure.

        Creates: <logs>/{entity}/{date}/

        Returns:
            Path to entity's log directory for today
        """
        base = self._get_base_log_dir()
        today = datetime.now().strftime("%Y-%m-%d")
        log_dir = base / today
        log_dir.mkdir(parents=True, exist_ok=True)

        _update_latest_symlink(base, log_dir)

        return log_dir

    def _setup_logger(self) -> None:
        """Configure logger with handlers and formatters."""
        logger = logging.getLogger(self.entity_name)
        logger.setLevel(getattr(logging, self.log_level.upper()))
        logger.propagate = not self.entity_name.startswith("mcp")

        # Remove existing handlers to avoid duplicates
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

        # Add correlation ID filter
        correlation_filter = CorrelationIDFilter()

        pid = _PID
        base_dir = str(self._get_base_log_dir()) if self.log_dir is not None else None
        file_handler_failures: list[str] = []

        def _attach_handler(factory, *, label: str) -> None:
            if base_dir is None:
                return
            try:
                handler = factory()
            except PermissionError as exc:
                file_handler_failures.append(f"{label}: {exc}")
                return
            except OSError as exc:
                file_handler_failures.append(f"{label}: {exc}")
                return
            logger.addHandler(handler)

        # 1. Main log file (hourly rotation, JSON format, date-aware)
        current_hour = datetime.now().strftime("%H-00")

        def _make_main_handler():
            main_handler = _DateAwareRotatingHandler(
                entity_base_dir=base_dir,
                filename_pattern=f"{current_hour}_{pid}.log",
                when="H",
                interval=LOG_RETENTION.rotation_interval_hours,
                backupCount=LOG_RETENTION.hourly_backup_count,
                encoding="utf-8",
            )
            main_handler.setLevel(logging.DEBUG)
            main_handler.setFormatter(JSONFormatter())
            main_handler.addFilter(correlation_filter)
            return main_handler

        _attach_handler(_make_main_handler, label="main-log")

        # 2. Error log file (ERROR+ only, JSON format, date-aware)
        def _make_error_handler():
            error_handler = _DateAwareFileHandler(
                entity_base_dir=base_dir,
                filename_pattern=f"errors_{pid}.log",
                encoding="utf-8",
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(JSONFormatter())
            error_handler.addFilter(correlation_filter)
            return error_handler

        _attach_handler(_make_error_handler, label="error-log")

        # 3. Console output (stderr, colored format)
        # Skip console for MCP (uses stdout for protocol)
        if not self.entity_name.startswith("mcp"):
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(ColoredFormatter())
            console_handler.addFilter(correlation_filter)
            logger.addHandler(console_handler)

        # 4. Tool-specific log for MCP (if entity is mcp)
        if self.entity_name == "mcp":

            def _make_tools_handler():
                tools_handler = _DateAwareFileHandler(
                    entity_base_dir=base_dir,
                    filename_pattern=f"tools_{pid}.log",
                    encoding="utf-8",
                )
                tools_handler.setLevel(logging.INFO)
                tools_handler.setFormatter(JSONFormatter())
                tools_handler.addFilter(correlation_filter)
                return tools_handler

            _attach_handler(_make_tools_handler, label="tools-log")

        def _suppress_mcp_fallback_output() -> bool:
            if not self.entity_name.startswith("mcp") or logger.handlers:
                return False
            logger.propagate = False
            logger.addHandler(logging.NullHandler())
            return True

        if self.file_logging_error:
            if not _suppress_mcp_fallback_output():
                logger.warning(
                    "File logging disabled for %s: %s",
                    self.entity_name,
                    self.file_logging_error,
                )
        elif file_handler_failures:
            if not _suppress_mcp_fallback_output():
                logger.warning(
                    "File logging disabled for %s: %s",
                    self.entity_name,
                    "; ".join(file_handler_failures),
                )

        self.logger = logger

    def get_logger(self) -> logging.Logger:
        """
        Get configured logger instance.

        Returns:
            Configured Logger for this entity
        """
        return self.logger


# Factory functions for easy access


def get_entity_logger(entity_name: str, log_level: str = "INFO") -> logging.Logger:
    """
    Get logger for an entity.

    Args:
        entity_name: Entity name (e.g., "cli", "ui-server", "mcp", "skills/careers")
        log_level: Logging level (default: INFO)

    Returns:
        Configured Logger instance

    Example:
        >>> logger = get_entity_logger("mcp")
        >>> logger.info("Starting MCP server", extra={"port": 8080})
    """
    entity_logger = EntityLogger(entity_name, log_level)
    return entity_logger.get_logger()


def get_skill_logger(skill_name: str, log_level: str = "INFO") -> logging.Logger:
    """
    Get logger for a skill.

    Creates logs at: <logs>/skills/{skill_name}/

    Args:
        skill_name: Skill name (e.g., "careers", "executor")
        log_level: Logging level (default: INFO)

    Returns:
        Configured Logger instance

    Example:
        >>> logger = get_skill_logger("careers")
        >>> logger.info("Syncing jobs", extra={"count": 42})
    """
    return get_entity_logger(f"skills/{skill_name}", log_level)

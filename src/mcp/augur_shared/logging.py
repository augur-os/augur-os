"""Minimal logging for augur-mcp.

This module provides a lightweight logging setup that works standalone
without requiring the full augur logging infrastructure.
"""

from __future__ import annotations

import errno as _errno
import logging
import os
import sys
from logging.handlers import RotatingFileHandler as _RotatingFileHandler


class _SafeRotatingFileHandler(_RotatingFileHandler):
    """RotatingFileHandler that silently ignores unavailable log files."""

    _SUPPRESS_ERRNOS = {
        _errno.ENOSPC,
        _errno.EROFS,
        _errno.EIO,
        _errno.EPIPE,
        _errno.EBADF,
        _errno.EACCES,
        _errno.EPERM,
    }

    def rotate(self, source: str, dest: str) -> None:
        try:
            super().rotate(source, dest)
        except OSError as exc:
            if exc.errno not in self._SUPPRESS_ERRNOS:
                raise

    def handleError(self, record: logging.LogRecord) -> None:
        _, exc, _ = sys.exc_info()
        if isinstance(exc, PermissionError):
            return
        if isinstance(exc, OSError) and exc.errno in self._SUPPRESS_ERRNOS:
            return
        super().handleError(record)


RotatingFileHandler = _SafeRotatingFileHandler
from pathlib import Path  # noqa: E402

try:
    from src.logging import (
        clear_correlation_id as _src_clear_correlation_id,
    )
    from src.logging import (
        generate_correlation_id as _src_generate_correlation_id,
    )
    from src.logging import (
        get_correlation_id as _src_get_correlation_id,
    )
    from src.logging import (
        set_correlation_id as _src_set_correlation_id,
    )
except Exception:
    _src_clear_correlation_id = None  # type: ignore[assignment]
    _src_generate_correlation_id = None  # type: ignore[assignment]
    _src_get_correlation_id = None  # type: ignore[assignment]
    _src_set_correlation_id = None  # type: ignore[assignment]

# Mapping of log level names to logging constants
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Default format for log messages
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
SIMPLE_FORMAT = "%(levelname)s: %(message)s"


def _resolve_log_file() -> Path | None:
    """Resolve log file path for rotating file logs."""
    env_file = os.environ.get("AUGUR_MCP_LOG_FILE")
    if env_file:
        return Path(env_file).expanduser().resolve()

    env_dir = os.environ.get("AUGUR_MCP_LOG_DIR") or os.environ.get("AUGUR_LOG_DIR")
    if env_dir:
        log_dir = Path(env_dir).expanduser().resolve()
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / "augur_mcp.log"

    try:
        from src.mcp.augur_shared.config import get_logs_dir

        log_dir = get_logs_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / "augur_mcp.log"
    except Exception:
        return None

    return None


def _get_rotation_settings() -> tuple[int, int]:
    """Return (max_bytes, backup_count) for rotating file logs."""
    max_mb = float(os.environ.get("AUGUR_MCP_LOG_MAX_MB", "5"))
    backup_count = int(os.environ.get("AUGUR_MCP_LOG_BACKUPS", "5"))

    try:
        from src.config.log_retention import LOG_RETENTION

        max_mb = LOG_RETENTION.max_log_size_mb
        backup_count = LOG_RETENTION.plugin_backup_count
    except Exception as e:
        logging.getLogger("augur_mcp.logging").debug(
            "Using default log rotation settings; src/lib retention unavailable: %s", e
        )

    return int(max_mb * 1024 * 1024), max(1, backup_count)


def get_logger(
    name: str,
    level: str = "INFO",
    format_string: str | None = None,
) -> logging.Logger:
    """Get or create a logger with the specified configuration.

    Args:
        name: Logger name (typically module or component name).
        level: Log level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        format_string: Optional custom format string.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(f"augur_mcp.{name}")

    # Only configure if not already configured
    if not logger.handlers:
        resolved_level = os.environ.get("AUGUR_LOG_LEVEL", level).upper()
        logger.setLevel(LOG_LEVELS.get(resolved_level, logging.INFO))

        handler = logging.StreamHandler(sys.stderr)
        stderr_level = os.environ.get("AUGUR_MCP_STDERR_LEVEL", "WARNING").upper()
        handler.setLevel(LOG_LEVELS.get(stderr_level, logging.WARNING))

        formatter = logging.Formatter(format_string or SIMPLE_FORMAT)
        handler.setFormatter(formatter)

        logger.addHandler(handler)

        log_file = _resolve_log_file()
        if log_file:
            max_bytes, backup_count = _get_rotation_settings()
            try:
                file_handler = RotatingFileHandler(
                    log_file,
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding="utf-8",
                    delay=True,
                )
            except OSError:
                file_handler = None
            if file_handler is not None:
                file_handler.setLevel(logger.level)
                file_handler.setFormatter(logging.Formatter(format_string or DEFAULT_FORMAT))
                logger.addHandler(file_handler)

        logger.propagate = False

    return logger


def set_log_level(level: str) -> None:
    """Set log level for all augur_mcp loggers.

    Args:
        level: Log level as string.
    """
    level_num = LOG_LEVELS.get(level.upper(), logging.INFO)

    # Update root augur_mcp logger
    root_logger = logging.getLogger("augur_mcp")
    root_logger.setLevel(level_num)

    # Update all handlers
    for handler in root_logger.handlers:
        handler.setLevel(level_num)


class CorrelationFilter(logging.Filter):
    """Filter that adds correlation ID to log records."""

    def __init__(self, correlation_id: str | None = None):
        super().__init__()
        self.correlation_id = correlation_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = self.correlation_id or "-"
        return True


# Thread-local storage for correlation ID
_correlation_id: str | None = None


def set_correlation_id(correlation_id: str | None) -> None:
    """Set the current correlation ID for logging."""
    if _src_set_correlation_id is not None:
        if correlation_id is None:
            if _src_clear_correlation_id is not None:
                _src_clear_correlation_id()
            return
        _src_set_correlation_id(correlation_id)
        return

    global _correlation_id
    _correlation_id = correlation_id


def get_correlation_id() -> str | None:
    """Get the current correlation ID."""
    if _src_get_correlation_id is not None:
        return _src_get_correlation_id()

    return _correlation_id


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    if _src_generate_correlation_id is not None:
        return _src_generate_correlation_id()[:8]

    import uuid

    return str(uuid.uuid4())[:8]


# ============================================
# Backwards compatibility aliases
# These match the src.logging API
# ============================================


def get_entity_logger(name: str, log_level: str = "INFO") -> logging.Logger:
    """Get a logger for an entity (backwards-compatible alias).

    This matches the src/lib.augur_logging.get_entity_logger API.

    Args:
        name: Entity name (e.g., 'mcp', 'virtual-doctor')
        log_level: Log level string (INFO, DEBUG, etc.) - currently ignored, uses global config

    Returns:
        Configured logger instance.
    """
    return get_logger(name)

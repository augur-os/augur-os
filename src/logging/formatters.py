"""
Custom log formatters for structured and colored logging.

Provides JSON formatter for machine-readable logs and colored formatter
for human-readable terminal output.
"""

import json
import logging
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logs.

    Outputs each log record as a single JSON line with timestamp, level,
    entity, message, correlation_id, and any extra fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: LogRecord to format

        Returns:
            JSON string representation of log record
        """
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "entity": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields from record (passed via extra={} in log call)
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """
    Colored console formatter for terminal output.

    Uses ANSI color codes to highlight log levels and provides
    compact, human-readable format.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with colors.

        Args:
            record: LogRecord to format

        Returns:
            Colored string representation of log record
        """
        color = self.COLORS.get(record.levelname, self.RESET)
        correlation = getattr(record, "correlation_id", None)
        correlation_str = f" {self.BOLD}[{correlation[:8]}]{self.RESET}" if correlation else ""

        # Format: LEVEL entity [corr_id] | message
        formatted = (
            f"{color}{record.levelname}{self.RESET} " f"{record.name}{correlation_str} | " f"{record.getMessage()}"
        )

        # Add exception if present
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted

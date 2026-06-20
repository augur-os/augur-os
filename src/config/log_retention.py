"""
Central Log Retention Configuration

All log retention settings in one place. Edit this file to change retention
policies across the entire augur.

Default: 24 hours for all log types.
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class LogRetentionConfig:
    """
    Central configuration for log retention across all augur components.

    All durations are in HOURS unless otherwise noted.
    """

    # === CORE LOG RETENTION (hours) ===

    # How many hourly log file backups to keep (24 = 1 day)
    hourly_backup_count: int = 24

    # Rotation interval in hours
    rotation_interval_hours: int = 1

    # === LOG SIZE LIMITS (MB) ===

    # Maximum log file size before truncation
    max_log_size_mb: float = 5.0

    # Size to keep after truncation
    keep_log_size_mb: float = 1.0

    # === RAG/PLUGIN LOG RETENTION ===

    # Size-based rotation threshold (MB)
    plugin_log_rotation_mb: int = 10

    # Number of backup files for plugin logs
    plugin_backup_count: int = 5

    # === DATA RETENTION (days) ===
    # Note: These are in DAYS, not hours

    # Chain execution logs retention
    chain_executions_days: int = 1  # 24 hours

    # Retrospective data retention
    retrospectives_days: int = 1  # 24 hours

    # Completed tasks retention
    tasks_completed_days: int = 1  # 24 hours

    # === MONITORING ===

    # Maximum bugs to report per hour (circuit breaker)
    max_bugs_per_hour: int = 10

    # Log monitor check interval (seconds)
    monitor_check_interval_seconds: int = 60


# Singleton instance - import this for use
LOG_RETENTION = LogRetentionConfig()


def get_log_rotation_settings() -> Dict[str, Any]:
    """
    Get log rotation settings for file handlers.

    Returns:
        Dict with rotation configuration
    """
    return {
        "when": "H",  # Hourly
        "interval": LOG_RETENTION.rotation_interval_hours,
        "backupCount": LOG_RETENTION.hourly_backup_count,
    }


def get_truncation_settings() -> Dict[str, float]:
    """
    Get log truncation settings.

    Returns:
        Dict with max and keep sizes in MB
    """
    return {
        "max_size_mb": LOG_RETENTION.max_log_size_mb,
        "keep_size_mb": LOG_RETENTION.keep_log_size_mb,
    }

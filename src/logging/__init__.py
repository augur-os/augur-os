"""
Centralized logging for Augur entities.

Public API for entity-based logging with correlation ID support.

Usage:
    >>> from src.logging import get_entity_logger, generate_correlation_id, set_correlation_id
    >>>
    >>> # Set up logger for entity
    >>> logger = get_entity_logger("mcp")
    >>>
    >>> # Generate and set correlation ID
    >>> corr_id = generate_correlation_id()
    >>> set_correlation_id(corr_id)
    >>>
    >>> # Log with automatic correlation ID injection
    >>> logger.info("Processing request", extra={"user_id": 123})
"""

from .config import get_entity_logger, get_skill_logger
from .correlation import (
    generate_correlation_id,
    set_correlation_id,
    get_correlation_id,
    clear_correlation_id,
    get_short_correlation_id,
)
from .formatters import JSONFormatter, ColoredFormatter

__all__ = [
    # Logger factories
    "get_entity_logger",
    "get_skill_logger",
    # Correlation ID management
    "generate_correlation_id",
    "set_correlation_id",
    "get_correlation_id",
    "clear_correlation_id",
    "get_short_correlation_id",
    # Formatters (for advanced usage)
    "JSONFormatter",
    "ColoredFormatter",
]

"""
Correlation ID management for distributed tracing across entities.

This module provides thread-safe correlation ID management using context variables,
enabling request tracing across CLI, UI Server, MCP Server, and Skills.
"""

import uuid
from contextvars import ContextVar
from typing import Optional

# Thread-safe storage for correlation ID
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def generate_correlation_id() -> str:
    """
    Generate a new UUID-based correlation ID.

    Returns:
        String UUID (e.g., "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    """
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: str) -> None:
    """
    Set correlation ID for current context (thread-safe).

    Args:
        correlation_id: UUID string to set as active correlation ID
    """
    _correlation_id.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """
    Get correlation ID for current context.

    Returns:
        Current correlation ID if set, None otherwise
    """
    return _correlation_id.get()


def clear_correlation_id() -> None:
    """Clear the correlation ID from current context."""
    _correlation_id.set(None)


def get_short_correlation_id() -> Optional[str]:
    """
    Get shortened correlation ID (first 8 characters) for compact logging.

    Returns:
        First 8 chars of correlation ID, or None if not set
    """
    corr_id = get_correlation_id()
    return corr_id[:8] if corr_id else None

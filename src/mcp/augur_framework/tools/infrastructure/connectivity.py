"""
Connectivity watchdog for airplane mode auto-detection.

Performs lightweight DNS resolution to determine if the host has internet access.
"""

import socket
from datetime import datetime, timezone
from typing import Any


def check_connectivity(host: str = "api.anthropic.com", port: int = 443) -> dict[str, Any]:
    """Check internet connectivity via DNS resolution.

    Uses socket.getaddrinfo to test DNS — fast, no HTTP overhead, no auth needed.

    Returns:
        Dict with keys: online (bool), host (str), checked_at (ISO timestamp).
    """
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        socket.getaddrinfo(host, port)
        return {"online": True, "host": host, "checked_at": checked_at}
    except (socket.gaierror, OSError):
        return {"online": False, "host": host, "checked_at": checked_at}


__all__ = ["check_connectivity"]

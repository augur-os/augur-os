"""
MCP Server startup and entry point logic.

Contains main(), client auto-detection, PID registry, preflight cleanup,
and the parent-process watchdog.
"""

import argparse
import atexit
import logging
import os
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger("mcp")


def auto_detect_client() -> str:
    """Auto-detect which AI client launched this MCP server.

    Checks environment variables and TTY state to infer the client.
    Falls back to "claude_code" (the most permissive capability set).
    """
    # Claude Desktop sets this env var
    if os.environ.get("CLAUDE_DESKTOP"):
        return "claude_desktop"

    # Cursor sets this
    if os.environ.get("CURSOR_SESSION_ID"):
        return "cursor"

    # Windsurf / Codeium
    if os.environ.get("WINDSURF_SESSION_ID") or os.environ.get("CODEIUM_SESSION"):
        return "windsurf"

    # If stdin is a pipe and no TTY, likely an IDE/desktop client
    # (Claude Code runs with a TTY; desktop apps pipe stdio)
    if not sys.stdin.isatty():
        # Could be any non-TTY client; default to claude_desktop
        # since that's the most common non-TTY case
        return "claude_desktop"

    return "claude_code"


def register_in_pid_registry(client_id: str | None, transport: str) -> None:
    """Register this MCP server in the daemon's PID registry for health monitoring."""
    try:
        monitor_path = (
            Path(__file__).resolve().parents[4]
            / "plugins"
            / "system"
            / "skills"
            / "daemon"
            / "scripts"
            / "mcp_health_monitor.py"
        )
        if not monitor_path.exists():
            return

        import importlib.util

        spec = importlib.util.spec_from_file_location("mcp_health_monitor", monitor_path)
        if spec is None or spec.loader is None:
            return
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        mod.register_mcp_server(
            name="augur",
            pid=os.getpid(),
            client=client_id or "unknown",
            transport=transport,
        )

        # Deregister on clean shutdown
        atexit.register(mod.remove_pid_from_registry, "augur")

    except Exception as e:
        logger.debug(f"PID registry registration skipped: {e}")


def run_preflight_cleanup() -> None:
    """Run preflight orphan cleanup from previous sessions."""
    try:
        monitor_path = (
            Path(__file__).resolve().parents[4]
            / "plugins"
            / "system"
            / "skills"
            / "daemon"
            / "scripts"
            / "mcp_health_monitor.py"
        )
        if not monitor_path.exists():
            return

        import importlib.util

        spec = importlib.util.spec_from_file_location("mcp_health_monitor", monitor_path)
        if spec is None or spec.loader is None:
            return
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        results = mod.scan_system_orphans(allowlist_pids={os.getpid()})
        if results.get("orphans_killed"):
            logger.info(f"Preflight cleanup: killed {results['orphans_killed']} orphaned MCP process(es)")
        elif results.get("orphans_found"):
            logger.debug(f"Preflight scan: {results['orphans_found']} orphan(s) found but none killed")
        else:
            logger.debug(f"Preflight scan: clean ({results.get('scanned', 0)} processes scanned)")

    except Exception as e:
        logger.debug(f"Preflight cleanup skipped: {e}")


def start_parent_watchdog(client_id: str | None) -> None:
    """Start a watchdog thread that exits when the parent process dies.

    For stdio transport, monitors PPID and exits cleanly when the parent
    disconnects. Claude Desktop is excluded because its intermediate
    helper process may exit while the connection remains alive.
    """
    _watchdog_excluded_clients = {"claude_desktop"}
    if client_id in _watchdog_excluded_clients:
        logger.info(f"Parent watchdog disabled for client={client_id} (SDK handles disconnect natively)")
        return

    def _parent_watchdog():
        """Monitor parent process and exit when it dies (client disconnected)."""
        original_ppid = os.getppid()
        while True:
            time.sleep(5)
            current_ppid = os.getppid()
            # On macOS/Linux, when parent dies, PPID changes to 1 (launchd/init)
            if current_ppid != original_ppid or current_ppid <= 1:
                reason = (
                    f"shutdown_reason=parent_disconnected original_ppid={original_ppid} "
                    f"current_ppid={current_ppid} transport=stdio"
                )
                logger.info(reason)
                # Ensure reason is flushed to log file before exit.
                logging.shutdown()
                os._exit(0)

    watchdog = threading.Thread(target=_parent_watchdog, daemon=True, name="parent-watchdog")
    watchdog.start()


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the full CLI argument parser for the MCP server."""
    parser = argparse.ArgumentParser(description="Augur MCP Server")
    parser.add_argument("--force", action="store_true", help="Force start (kill existing instance)")
    parser.add_argument("--no-lock", action="store_true", help="Disable instance locking (not recommended)")
    parser.add_argument("--client-id", default=None, help="Client identifier (auto-detected if not provided)")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse", "streamable-http", "http", "streamable_http"],
        help="Transport protocol (default: stdio). 'http' is an alias for 'streamable-http'.",
    )
    parser.add_argument(
        "--auth",
        default="none",
        choices=["none", "oauth"],
        help="Authentication mode for SSE/HTTP transports (default: none).",
    )
    parser.add_argument(
        "--public-url",
        default=None,
        help="Public base URL for OAuth discovery (e.g. https://example.com).",
    )
    parser.add_argument(
        "--issuer-url",
        default=None,
        help="OAuth issuer URL (defaults to --public-url or http://host:port for localhost).",
    )
    parser.add_argument(
        "--resource-url",
        default=None,
        help="OAuth resource server URL (defaults to <issuer> + transport path).",
    )
    parser.add_argument(
        "--oauth-auto-approve",
        action="store_true",
        help="Skip consent UI and auto-approve OAuth authorizations (not recommended).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for SSE/HTTP server (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE/HTTP server (default: 8000)")
    parser.add_argument(
        "--mount-path",
        default=None,
        help="Optional mount path when running behind a reverse proxy (SSE only).",
    )
    parser.add_argument(
        "--disable-dns-rebinding-protection",
        action="store_true",
        help="Disable DNS rebinding protection checks for Host/Origin headers (not recommended).",
    )
    return parser

"""Entry point: python -m augur_framework."""

from __future__ import annotations

import signal
import sys
import threading
import time

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
from src.mcp.augur_framework.tools import register_framework_tools
from src.mcp.augur_shared.mcp_sdk import (
    _pin_mcp_sdk_package,
    mcp_tool_interceptor,
    metrics,
)


def _client_id_from_argv(argv: list[str] | None = None) -> str:
    args = list(sys.argv[1:] if argv is None else argv)
    for index, arg in enumerate(args):
        if arg == "--client-id" and index + 1 < len(args):
            return args[index + 1]
        if arg.startswith("--client-id="):
            return arg.split("=", 1)[1]
    return "mcp"


def _ignore_interactive_interrupts() -> None:
    """Survive stray console Ctrl+C / Ctrl+Break events.

    The dashboard spawns this bridge `detached`, but on Windows a console
    control event (from a Next.js HMR restart or sibling-process churn) can
    still reach the child. Python's default SIGINT handler would then kill it
    mid-request — exit code 0xC000013A (CONTROL_C_EXIT) — dropping the
    dashboard's MCP connection and forcing a reconnect that hangs in-flight
    searches and flips the "MCP server is down" banner.

    The parent owns lifecycle deliberately: in dev the bridge exits on stdin
    EOF (parent gone); in prod it is killed with SIGTERM (still honored here).
    So ignoring interactive interrupts is safe and matches that contract.
    """
    for signame in ("SIGINT", "SIGBREAK"):
        sig = getattr(signal, signame, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, signal.SIG_IGN)
        except (ValueError, OSError):
            # Not on the main thread or unsupported platform — best effort.
            pass


def _prewarm_search() -> None:
    """Warm the search backend in the background so the first query isn't cold.

    The first unified-search after the bridge starts pays one-time costs — BM25
    index load, ripgrep/process warmup, search-config + retrieval-module imports
    — which cold can stall the user's first query for 15-30s. Running a tiny
    throwaway search here on startup makes those caches hot before the user
    searches. Runs in a daemon thread so it never delays the bridge from
    serving, and is fully best-effort: any failure is swallowed.
    """
    started = time.monotonic()
    try:
        from src.lib.knowledge.unified_search import UnifiedSearcher

        UnifiedSearcher().search("augur", top_k=1)
        print(
            f"[prewarm] search backend warm in {time.monotonic() - started:.1f}s",
            file=sys.stderr,
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001 - warmup must never break the bridge
        print(f"[prewarm] skipped: {exc}", file=sys.stderr, flush=True)


def run() -> int:
    _pin_mcp_sdk_package()
    _ignore_interactive_interrupts()
    mcp = FastMCP("augur-framework")
    register_framework_tools(
        mcp,
        mcp_tool_interceptor,
        metrics,
        capability_target=_client_id_from_argv(),
    )
    threading.Thread(target=_prewarm_search, name="search-prewarm", daemon=True).start()
    mcp.run()
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())

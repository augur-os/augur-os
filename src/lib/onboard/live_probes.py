from __future__ import annotations

import json
import urllib.request

from src.lib.onboard.result import OnboardContext
from src.lib.onboard.verify import VerifyProbes


def _dashboard_interactive(ctx: OnboardContext) -> bool:
    try:
        with urllib.request.urlopen(
            "http://localhost:3000/browse", timeout=10
        ) as resp:  # nosec B310  # hardcoded localhost URL
            body = resp.read().decode("utf-8", "replace")
        # SSR 200 plus an app-root marker; a chunk-load error boundary fails this.
        return resp.status == 200 and "__next" in body.lower()
    except Exception:
        return False


def _mcp_connected(ctx: OnboardContext) -> bool:
    try:
        payload = json.dumps({"tool": "health", "args": {}}).encode()
        req = urllib.request.Request(
            "http://localhost:3000/api/mcp/tool",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310  # hardcoded localhost URL in Request above
            return resp.status == 200
    except Exception:
        return False


def _sample_query(ctx: OnboardContext) -> str:
    # Capability/system query that works on a freshly-seeded empty brain.
    try:
        payload = json.dumps({"tool": "augur-list-capabilities", "args": {}}).encode()
        req = urllib.request.Request(
            "http://localhost:3000/api/mcp/tool",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310  # hardcoded localhost URL in Request above
            return resp.read().decode("utf-8", "replace")
    except Exception:
        return ""


def live_probes(ctx: OnboardContext) -> VerifyProbes:
    return VerifyProbes(
        dashboard_interactive=_dashboard_interactive,
        mcp_connected=_mcp_connected,
        sample_query=_sample_query,
    )

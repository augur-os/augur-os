"""MCP tool wrapper for the local-CLI integration scanner.

Exposes scan-local-clis so the dashboard's setup widget / integrations
page can trigger the scan on demand (and on first dashboard load) to
auto-populate <vault>/integrations/<id>.yaml records — closing the
'Connect first integration' probe without manual yaml-writing.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCAN_SCRIPT = Path(__file__).resolve().parents[1] / "scan_local_clis.py"


def _load_scanner():
    spec = importlib.util.spec_from_file_location(
        "onboard_scan_local_clis", _SCAN_SCRIPT,
    )
    assert spec is not None and spec.loader is not None, (
        f"cannot load {_SCAN_SCRIPT}"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def register_tools(mcp, mcp_tool_interceptor, metrics) -> None:
    @mcp.tool(name="scan-local-clis")
    @mcp_tool_interceptor
    async def scan_local_clis() -> str:
        """Detect installed local CLIs and write integration yamls.

        Walks a registry of well-known tools (Obsidian, gcloud, gh, vscode,
        docker, ollama, claude/codex/gemini, jq) and writes one
        <vault>/integrations/<id>.yaml per detection. Idempotent: user-set
        ``enabled: false`` and user-authored fields like ``note`` are
        preserved across re-runs. Returns a JSON summary dict with
        detected/skipped counts and the list of written file paths.
        """
        if metrics:
            metrics.track_tool("scan_local_clis", skill="onboard")
        try:
            from src.config.paths import get_vault_dir
            from src.lib.brain_layout import vault_machine_dir

            scanner = _load_scanner()
            target = vault_machine_dir(get_vault_dir(), "integrations")
            result = scanner.scan(target_dir=target)
            return json.dumps({"success": True, **result}, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

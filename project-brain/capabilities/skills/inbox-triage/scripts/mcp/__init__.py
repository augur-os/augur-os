"""MCP tools + CLI subcommands for the inbox-triage skill (ADR-744 routine).

Exposes:

- ``register_tools(mcp, mcp_tool_interceptor, metrics)`` — three deterministic
  tools: inbox-triage-list, inbox-triage-file, inbox-triage-report.
  Routine/CLI-callable; not exported as direct client tools (see
  capability_exposure.yaml).
- ``register_subcommands(subparsers)`` — the ``aug inbox-triage <verb>`` CLI
  surface: list, file.
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)

# Put this skill's own `scripts/` dir on sys.path so MCP-server and CLI entry
# points can both `import inbox_triage`, `import inbox_triage_report`.
_augur_scripts_dir = str(_AugurPath(__file__).resolve().parent.parent)
if _augur_scripts_dir not in _augur_sys.path:
    _augur_sys.path.insert(0, _augur_scripts_dir)

import json
from datetime import date as _date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.annotations import tool_annotations
    from src.mcp.augur_shared.logging import get_entity_logger
except ImportError:  # pragma: no cover
    import logging as _logging

    def get_entity_logger(name: str):
        return _logging.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations


logger = get_entity_logger("mcp.command.inbox-triage")

_READ_ONLY = {"destructiveHint": False, "idempotentHint": True,
              "openWorldHint": False, "readOnlyHint": True}
_WRITE = {"destructiveHint": False, "idempotentHint": False,
          "openWorldHint": False, "readOnlyHint": False}


def _resolve_vault_root() -> Path:
    from src.config.paths import get_vault_dir
    return Path(get_vault_dir())


def _resolve_report_root() -> Path:
    from src.config.paths import get_documents_machine_dir
    return get_documents_machine_dir("reports")


def register_tools(mcp: "FastMCP", mcp_tool_interceptor: Callable[..., Any], metrics: Any) -> None:
    """Register the 3 inbox-triage MCP tools (ADR-744 routine pattern)."""
    logger.info("Registering inbox-triage MCP tools...")
    import inbox_triage  # type: ignore[import-not-found]
    import inbox_triage_report  # type: ignore[import-not-found]

    @mcp.tool(name="inbox-triage-list",
              annotations=tool_annotations({"title": "Inbox Triage List", **_READ_ONLY}))
    @mcp_tool_interceptor
    async def inbox_triage_list_tool() -> str:
        """List vault-inbox capture cards awaiting domain filing."""
        metrics.track_tool("inbox_triage_list", skill="inbox-triage")
        cards = inbox_triage.list_inbox_cards(_resolve_vault_root())
        return json.dumps({"count": len(cards), "cards": cards}, indent=2)

    @mcp.tool(name="inbox-triage-file",
              annotations=tool_annotations({"title": "Inbox Triage File", **_WRITE}))
    @mcp_tool_interceptor
    async def inbox_triage_file_tool(card_path: str, target: str, reason: str) -> str:
        """Move one inbox card into a vault domain (move-only, with provenance)."""
        metrics.track_tool("inbox_triage_file", skill="inbox-triage")
        result = inbox_triage.file_card(
            vault_dir=_resolve_vault_root(),
            card_path=Path(card_path),
            target_rel=target,
            reason=reason,
        )
        return json.dumps(result, indent=2)

    @mcp.tool(name="inbox-triage-report",
              annotations=tool_annotations({"title": "Inbox Triage Report", **_WRITE}))
    @mcp_tool_interceptor
    async def inbox_triage_report_tool(entries_json: str, left_in_inbox_json: str = "[]") -> str:
        """Write the daily triage report; entries are the filed cards."""
        metrics.track_tool("inbox_triage_report", skill="inbox-triage")
        entries = json.loads(entries_json)
        left = json.loads(left_in_inbox_json)
        path = inbox_triage_report.write_report(
            _resolve_report_root(), _date.today().isoformat(), entries, left_in_inbox=left,
        )
        return json.dumps({"success": True, "report": path}, indent=2)


def register_subcommands(subparsers: Any) -> None:
    """`aug inbox-triage <list|file>` CLI surface (ADR-260)."""
    p = subparsers.add_parser("inbox-triage", help="Daily vault-inbox triage")
    sub = p.add_subparsers(dest="inbox_triage_cmd", required=True)

    sub.add_parser("list", help="List inbox cards awaiting filing")

    fp = sub.add_parser("file", help="File one card into a domain")
    fp.add_argument("card_path")
    fp.add_argument("target")
    fp.add_argument("reason")

    def _run(args: Any, remaining: Any = None) -> int:
        import inbox_triage  # type: ignore[import-not-found]
        vault = _resolve_vault_root()
        if args.inbox_triage_cmd == "list":
            print(json.dumps(inbox_triage.list_inbox_cards(vault), indent=2))
            return 0
        if args.inbox_triage_cmd == "file":
            result = inbox_triage.file_card(
                vault_dir=vault, card_path=Path(args.card_path),
                target_rel=args.target, reason=args.reason,
            )
            print(json.dumps(result, indent=2))
            return 0 if result.get("success") else 1
        return 2

    p.set_defaults(func=_run)

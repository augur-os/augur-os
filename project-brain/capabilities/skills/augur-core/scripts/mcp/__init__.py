"""
Discovery CLI subcommand plugin.

Provides `aug discover` — prints the Augur capability manifest
for agent bootstrapping and introspection.

Part of ADR-260: CLI Subcommand Plugin Architecture
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
import json
import os
import sys


def register_tools(mcp, mcp_tool_interceptor, metrics) -> None:
    """No MCP tools — discovery is a CLI-only subcommand plugin (ADR-260)."""
    pass


def register_subcommands(subparsers) -> None:
    """Register the 'discover' subcommand."""
    p = subparsers.add_parser("discover", help="Print Augur capability manifest")
    p.add_argument("--hub", help="Filter by hub")
    p.add_argument("--tier", help="Filter by tier")
    p.add_argument("--compact", action="store_true", help="Compact tool listing")
    p.add_argument(
        "--commands",
        action="store_true",
        help="List available slash commands with descriptions (instead of the manifest)",
    )
    p.add_argument("--format", dest="discover_format", help="Output format: json or markdown")
    p.set_defaults(func=_run_discover)

    # `aug ask-retain` — CLI surface for `/ask --retain`.
    # ask-retain is policy-skipped from direct MCP client exposure
    # (capability_exposure.yaml export_to: [cli, agents-md, browse]) with
    # `primary_surface: mcp via dashboard`. The policy promises a `cli` surface;
    # this entrypoint honors it by bridging to retain_ask_outcome_impl in-process,
    # so /ask --retain works from CLI clients, not just the dashboard.
    ar = subparsers.add_parser(
        "ask-retain",
        help="Persist a durable /ask outcome into memory/synthesis (CLI surface for /ask --retain)",
    )
    ar.add_argument("--question", required=True)
    ar.add_argument("--answer", required=True)
    ar.add_argument(
        "--explicit-signal", action="append", dest="explicit_signals", default=None, help="repeatable"
    )
    ar.add_argument(
        "--inferred-signal", action="append", dest="inferred_signals", default=None, help="repeatable"
    )
    ar.add_argument(
        "--kinds", action="append", default=None, help="repeatable; e.g. insight, decision, preference"
    )
    ar.add_argument("--retain-mode", default="default")
    ar.add_argument("--to", default=None, help="brain id; omit to resolve active project brain from cwd")
    ar.add_argument("--tags", action="append", default=None, help="repeatable")
    ar.add_argument("--source", action="append", dest="sources", default=None, help="repeatable")
    ar.add_argument("--cwd", default=None)
    ar.set_defaults(func=_run_ask_retain_cli)


def _print_commands_markdown(payload: dict) -> None:
    """Print the slash-command listing as agent-readable markdown, grouped by tier."""
    sections = payload.get("slash_commands", [])
    print(f"# Augur Slash Commands ({payload.get('total_commands', 0)})")
    for section in sections:
        print()
        print(f"## {section.get('label') or section.get('key') or 'Commands'}")
        for cmd in section.get("commands", []):
            desc = (cmd.get("description") or "").split("\n", 1)[0]
            print(f"- `/{cmd.get('id', '')}` — {desc}")


def _print_manifest_markdown(manifest: dict) -> None:
    """Print the discovery manifest as agent-readable markdown."""
    focus = manifest.get("focus", {})
    m = manifest.get("manifest", {})
    caps = m.get("capabilities", {})
    tools = manifest.get("recommended_tools", [])

    print(f"# Augur — {m.get('description', '')}")
    print()
    print(f"**Hub focus**: {focus.get('hub') or 'none'}")
    managed_skills = caps.get("managed_skills")
    if managed_skills is None:
        print(f"**Skills**: {caps.get('skills', 0)} | **Hubs**: {caps.get('hubs', 0)}")
    else:
        print(
            f"**Skills**: {caps.get('skills', 0)} visible "
            f"({managed_skills} managed) | **Hubs**: {caps.get('hubs', 0)}"
        )
    print(f"**CLI**: `{m.get('cli', {}).get('binary', 'aug')}` | **MCP**: `{m.get('mcp', {}).get('server', 'augur')}`")
    print()

    if tools:
        print(f"## Recommended Tools ({len(tools)})")
        print()
        print("| Tool | Skill | Hub | Tier |")
        print("|------|-------|-----|------|")
        for t in tools:
            print(f"| {t['name']} | {t.get('skill', '')} | {t.get('hub', '')} | {t.get('tier', '')} |")
        print()

    hubs = m.get("hubs", [])
    if hubs:
        print(f"## Hubs ({len(hubs)})")
        print()
        for h in hubs:
            skills_str = ", ".join(h.get("skills", []))
            print(f"- **{h['id']}**: {skills_str}")


def _run_discover(args, remaining) -> int:
    """Execute the discover subcommand."""
    import atexit

    from src.mcp.augur_framework.tools.domain.discovery import assemble_manifest
    from src.mcp.augur_framework.tools.domain.sessions import create_session, delete_session
    from src.config.paths import get_runtime_dir

    runtime_dir = get_runtime_dir()
    sessions_dir = runtime_dir / "sessions"

    # Create session and register cleanup
    session_id = f"cli-{os.getpid()}"
    create_session(sessions_dir, session_id=session_id, source="cli")
    atexit.register(lambda: delete_session(sessions_dir, session_id))

    discover_format = getattr(args, "discover_format", None)
    if discover_format is None:
        discover_format = "markdown" if sys.stdout.isatty() else "json"

    # `aug discover --commands` lists slash commands (shared with list-commands)
    # rather than the capability manifest.
    if getattr(args, "commands", False) or "commands" in (remaining or []):
        from src.plugins.command_listing import render_commands_payload

        payload = render_commands_payload()
        if discover_format == "markdown":
            _print_commands_markdown(payload)
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return 0

    manifest = assemble_manifest(
        runtime_dir,
        hub=args.hub,
        tier=args.tier,
        session_id=session_id,
    )

    if args.compact:
        for tool in manifest.get("recommended_tools", []):
            print(f"  {tool['name']:<35} {tool.get('skill', '')}")
    elif discover_format == "markdown":
        _print_manifest_markdown(manifest)
    else:
        print(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))

    return 0


def _run_ask_retain_cli(args, remaining) -> int:
    """Execute `aug ask-retain` — CLI surface for `/ask --retain` (ADR-260).

    Bridges to retain_ask_outcome_impl in-process. The module-level bootstrap
    (ensure_project_paths) already placed the project root and src/mcp on
    sys.path, so `augur_core` (under src/mcp) and `src.*` both import cleanly.
    Mirrors the ingest skill's `_run_note_url_cli` handler.
    """
    import asyncio
    import json
    import os
    from pathlib import Path

    from augur_core.tools.core.ask_retention import retain_ask_outcome_impl

    result = asyncio.run(
        retain_ask_outcome_impl(
            question=args.question,
            answer=args.answer,
            explicit_signals=args.explicit_signals,
            inferred_signals=args.inferred_signals,
            kinds=args.kinds,
            retain_mode=args.retain_mode,
            sources=args.sources,
            tags=args.tags,
            surface_footer=False,
            to=args.to,
            cwd=Path(args.cwd or os.getcwd()),
        )
    )
    print(result)
    try:
        return 0 if json.loads(result).get("success", True) else 1
    except (ValueError, TypeError):
        return 0

#!/usr/bin/env python3
"""
Augur CLI - Generic MCP Tool Wrapper

A unified command-line interface for interacting with the Augur MCP server.
This CLI wraps MCP tools and makes them available from the command line.

Usage:
    aug <tool-name> [--param value ...]

Examples:
    aug list-skills
    aug get-skill --skill-name career
    aug execute-chain --chain-name bug_workflow --user-input "Fix login issue"
    aug refresh-inbox
    aug find-skill --query "how do I track my health?"

For a list of available tools:
    aug --list-tools
"""

# ruff: noqa: E402

import os
import sys
from pathlib import Path

# Bootstrap must happen before any other Augur imports
from src.cli_bootstrap import bootstrap, reexec_cli_from_project_root_if_needed

PROJECT_ROOT = bootstrap()
reexec_cli_from_project_root_if_needed(PROJECT_ROOT, __file__)

import atexit
import argparse
import asyncio
import json
import logging
import re
from typing import Any, Dict

from src.logging import get_entity_logger
from src.config.paths import get_runtime_dir
from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

logger = get_entity_logger("cli")

_TOOLS_REGISTERED = False
_CLI_MCPS: list[FastMCP] | None = None

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Pure helpers split into sibling modules (WS5 — behavior-preserving, no importer changes)
from src._cli_mcp import (  # noqa: F401
    _pack_tool_params_for_schema,
    _print_manifest_markdown,
    _render_tool_help,
    _schema_ref_target,
    _schema_uses_wrapped_params,
    _wrapped_params_payload_schema,
    format_tool_list,
    format_tool_list_json,
    parse_param_value,
)

# Project subcommand handlers split into sibling module
from src._cli_commands import (  # noqa: F401
    _handle_project_init,
    _handle_project_status,
    _register_project_subcommands,
)


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return _ANSI_RE.sub("", text)


def _should_suppress_color() -> bool:
    """Respect NO_COLOR (https://no-color.org/) and detect piped output."""
    return "NO_COLOR" in os.environ or not sys.stdout.isatty()


def _is_machine_mode(args: argparse.Namespace) -> bool:
    """True when output should be pure machine-readable (no ANSI, JSON to stdout)."""
    return args.json or args.format == "json" or not sys.stdout.isatty()


def _configure_cli_logging(*, verbose: bool) -> None:
    """Configure CLI logging before plugin discovery can emit output."""
    if verbose:
        os.environ["AUGUR_LOG_LEVEL"] = "INFO"
        logging.disable(logging.NOTSET)
    else:
        os.environ.setdefault("AUGUR_LOG_LEVEL", "ERROR")
        os.environ.setdefault("AUGUR_CLI_MODE", "1")
        logging.disable(logging.WARNING)

    for handler in logging.root.handlers:
        if hasattr(handler, "stream") and handler.stream is sys.stdout:
            handler.stream = sys.stderr


_GLOBAL_OPTIONS_WITH_VALUES = {"--format", "-f"}
_GLOBAL_OPTION_VALUE_PREFIXES = ("--format=",)


def _first_command_token_index(argv: list[str]) -> int | None:
    """Return the first positional command/tool token in top-level argv.

    ``argparse`` cannot disambiguate Augur's optional MCP tool positional from
    plugin subparsers. This small pre-scan lets ``main`` decide whether the
    first command token is a registered subcommand or an MCP tool before
    handing control to a parser that would otherwise reject MCP tool names.
    """
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--":
            return index + 1 if index + 1 < len(argv) else None
        if arg in _GLOBAL_OPTIONS_WITH_VALUES:
            index += 2
            continue
        if arg.startswith(_GLOBAL_OPTION_VALUE_PREFIXES):
            index += 1
            continue
        if arg.startswith("-"):
            index += 1
            continue
        return index
    return None


def _get_mcp_tools_dict(mcp: Any) -> Dict[str, Any] | None:
    if hasattr(mcp, "_tools"):
        return mcp._tools  # type: ignore[attr-defined]
    if hasattr(mcp, "_tool_manager") and hasattr(mcp._tool_manager, "_tools"):
        return mcp._tool_manager._tools  # type: ignore[attr-defined]
    return None


def _build_cli_mcps() -> list[FastMCP]:
    """Build in-process MCP runtimes for CLI tool execution."""
    from src.mcp.augur_core.tools import register_core_tools
    from src.mcp.augur_framework.tools import register_framework_tools
    from src.mcp.augur_shared.mcp_sdk import (
        _pin_mcp_sdk_package,
        mcp_tool_interceptor,
        metrics,
    )

    _pin_mcp_sdk_package()
    core_mcp = FastMCP("augur-cli-core")
    register_core_tools(
        core_mcp,
        mcp_tool_interceptor,
        metrics,
        capability_target="cli",
    )
    framework_mcp = FastMCP("augur-cli-framework")
    register_framework_tools(
        framework_mcp,
        mcp_tool_interceptor,
        metrics,
        capability_target="cli",
    )
    return [core_mcp, framework_mcp]


def _get_cli_mcps() -> list[FastMCP]:
    global _CLI_MCPS
    if _CLI_MCPS is None:
        _CLI_MCPS = _build_cli_mcps()
    return _CLI_MCPS


def _ensure_tools_registered() -> None:
    global _TOOLS_REGISTERED
    if _TOOLS_REGISTERED:
        return

    try:
        _get_cli_mcps()
        _TOOLS_REGISTERED = True
    except Exception as exc:
        logger.warning("Could not initialize MCP tools: %s", exc)


def get_available_tools() -> Dict[str, Dict[str, Any]]:
    """Get all available MCP tools with their metadata."""
    tools = {}

    try:
        _ensure_tools_registered()
        for mcp in _get_cli_mcps():
            # Get registered tools from the MCP server using list_tools()
            tool_list = asyncio.run(mcp.list_tools())
            for tool in tool_list:
                tools.setdefault(
                    tool.name,
                    {
                        "name": tool.name,
                        "description": tool.description or "No description",
                        "inputSchema": tool.inputSchema if hasattr(tool, "inputSchema") else None,
                    },
                )
    except Exception as e:
        logger.warning("Could not load MCP tools: %s", e)
        print(f"Warning: Could not load MCP tools: {e}", file=sys.stderr)

    return tools


async def call_tool(tool_name: str, params: Dict[str, Any]) -> str:
    """Call an MCP tool with the given parameters."""
    _ensure_tools_registered()
    mcp = _resolve_cli_mcp_for_tool(tool_name)
    if mcp is None:
        raise ValueError(f"Unknown MCP tool: {tool_name}")

    input_schema = await _input_schema_for_tool(mcp, tool_name)
    call_params = _pack_tool_params_for_schema(params, input_schema)

    # Use MCP's call_tool method
    result = await mcp.call_tool(tool_name, call_params)

    # Result is a tuple of (content_list, metadata)
    if isinstance(result, tuple):
        content_list = result[0]
    else:
        content_list = result

    # Extract the text content from the result
    if isinstance(content_list, list):
        texts = []
        for item in content_list:
            if hasattr(item, "text"):
                texts.append(item.text)
        return "\n".join(texts)

    if hasattr(content_list, "content") and content_list.content:
        texts = []
        for item in content_list.content:
            if hasattr(item, "text"):
                texts.append(item.text)
        return "\n".join(texts)

    return str(result)


def _resolve_cli_mcp_for_tool(tool_name: str) -> FastMCP | None:
    """Return the in-process runtime that owns ``tool_name``."""
    for mcp in _get_cli_mcps():
        tools_dict = _get_mcp_tools_dict(mcp)
        if tools_dict and tool_name in tools_dict:
            return mcp
    return None


async def _input_schema_for_tool(mcp: Any, tool_name: str) -> dict[str, Any] | None:
    """Return the MCP input schema for ``tool_name`` when the runtime exposes it."""
    try:
        tool_list = await mcp.list_tools()
    except Exception:
        return None
    for tool in tool_list:
        if getattr(tool, "name", None) == tool_name:
            schema = getattr(tool, "inputSchema", None)
            return schema if isinstance(schema, dict) else None
    return None


def _get_runtime_dir() -> Path:
    return get_runtime_dir()


def _handle_dev(args: argparse.Namespace, remaining: list[str] | None = None) -> int:
    """Handle `aug dev build` — rebuild + scoped-restart the current dashboard instance."""
    del remaining
    if getattr(args, "dev_command", None) != "build":
        print("usage: aug dev build", file=sys.stderr)
        return 2
    from src.lib.dev_build import run_dev_build

    result = run_dev_build()
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


def _handle_init(args: argparse.Namespace, remaining: list[str] | None = None) -> int:
    """Create or attach a project brain for a project root."""
    del remaining
    from src.lib.brain_init import init_project_brain
    from src.lib.onboarding_journey import (
        build_project_init_launch_journey,
        format_project_init_launch_journey,
    )

    result = init_project_brain(Path(args.project), run_sync=bool(getattr(args, "sync", False)))
    print(format_project_init_launch_journey(build_project_init_launch_journey(result)))
    if result.sync_returncode is not None:
        print(f"Projection sync exit code: {result.sync_returncode}")
    if result.sync_returncode in (None, 0):
        return 0
    return result.sync_returncode


def _project_output_format(args: argparse.Namespace) -> str:
    return str(getattr(args, "format", None) or ("json" if getattr(args, "json", False) else "text"))


def _project_registry_path(args: argparse.Namespace) -> Path | None:
    registry = getattr(args, "registry", None)
    return Path(registry).expanduser() if registry else None


def _launch_context_payload(context_result: Any) -> dict[str, object]:
    from src.lib.onboarding_journey import serialize_project_launch_context

    return serialize_project_launch_context(context_result)


def _print_project_payload(payload: dict[str, object], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return
    launch_journey = payload.get("launch_journey")
    if isinstance(launch_journey, dict):
        from src.lib.onboarding_journey import format_project_init_launch_journey

        print(format_project_init_launch_journey(launch_journey))
        if payload.get("sync_returncode") is not None:
            print(f"Projection sync exit code: {payload['sync_returncode']}")
        return
    print(payload["message"])
    print(f"Project root: {payload['project_root']}")
    print(f"Brain root: {payload['brain_root']}")
    print(f"Status: {payload['status']}")
    if payload.get("brain_id"):
        print(f"Brain id: {payload['brain_id']}")


def _register_builtin_subcommands(subparsers: Any) -> None:
    """Register CLI subcommands that are available without plugins."""
    init = subparsers.add_parser("init", help="Create or attach a project brain in this folder")
    init.add_argument(
        "--project",
        default=".",
        help="Project root to initialize or attach (default: current directory)",
    )
    init.add_argument(
        "--sync",
        action="store_true",
        help="Also regenerate generated AI-client projections after inventory.",
    )
    init.add_argument(
        "--no-sync",
        action="store_true",
        help="Accepted for compatibility; init is inventory-only unless --sync is set.",
    )
    init.set_defaults(func=_handle_init)

    dev = subparsers.add_parser("dev", help="Agent-callable dev operations (build/restart the dashboard)")
    dev_sub = dev.add_subparsers(dest="dev_command", required=True)
    dev_build = dev_sub.add_parser("build", help="Rebuild + scoped-restart the current dashboard instance")
    dev_build.set_defaults(func=_handle_dev)

    project = subparsers.add_parser("project", help="Inspect or initialize the current project folder")
    project_subparsers = project.add_subparsers(dest="project_command", required=True)
    _register_project_subcommands(project_subparsers)


def main():
    """Main CLI entry point."""
    _configure_cli_logging(verbose=("-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]))

    parser = argparse.ArgumentParser(
        description="Augur CLI - Generic MCP Tool Wrapper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    aug list-skills
    aug get-skill --skill-name career
    aug execute-chain --chain-name bug_workflow --user-input "Fix login bug"
    aug refresh-inbox
    aug --list-tools

For tool-specific help:
    aug <tool-name> --help
        """,
    )

    parser.add_argument("tool", nargs="?", help="MCP tool name to execute")
    parser.add_argument("--list-tools", "-l", action="store_true", help="List all available MCP tools")
    parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
    parser.add_argument(
        "--format",
        "-f",
        choices=["json", "text", "markdown"],
        default=None,
        help="Output format (default: auto-detect from tty)",
    )
    parser.add_argument("--pretty", "-p", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    # Plugin-contributed subcommands (ADR-260)
    subparsers = parser.add_subparsers(dest="subcommand")
    _register_builtin_subcommands(subparsers)
    try:
        from src.cli_plugins import discover_subcommands

        discover_subcommands(subparsers)
    except Exception as exc:
        logger.debug("Could not discover plugin subcommands: %s", exc)

    # Track 2: aug config <subcommand> (manifest + per-client config sync)
    try:
        from src.cli_config.config_sync import register_config_subcommands

        register_config_subcommands(subparsers)
    except Exception as exc:
        logger.debug("Could not register aug config subcommands: %s", exc)

    # Track 3: aug onboard <subcommand> (cross-OS onboard engine, M3)
    try:
        from src.cli_onboard import register_onboard_subcommands

        register_onboard_subcommands(subparsers)
    except Exception as exc:
        logger.debug("Could not register aug onboard subcommands: %s", exc)

    # Resolve the `tool` vs. subcommand ambiguity caused by argparse
    # treating the optional positional `tool` as greedier than the
    # subparsers dispatch. Without this, a nested subcommand like
    # `aug config sync` is mis-parsed as `tool=config, subcommand=sync`
    # (because the optional `tool` consumes the first token before
    # subparsers get a chance).
    #
    # Strategy: detect the case where sys.argv[1] is a registered
    # subcommand and bypass argparse's normal parse by handing argv
    # straight to the relevant subparser.
    _registered_subcommands = set(subparsers.choices.keys()) if hasattr(subparsers, "choices") else set()
    argv = sys.argv[1:]
    first_command_index = _first_command_token_index(argv)
    _direct_subcommand = None
    if first_command_index is not None and argv[first_command_index] in _registered_subcommands:
        top_level_args, _ = parser.parse_known_args(argv[:first_command_index])
        _direct_subcommand = argv[first_command_index]
        sub_parser = subparsers.choices[_direct_subcommand]
        _sub_rest = list(argv[first_command_index + 1 :])
        if _direct_subcommand == "a-loops":
            # skill_cli_daemon is the module name assigned by cli_plugins when it loads
            # the daemon skill's mcp/__init__.py; look it up from sys.modules to avoid
            # colliding with the MCP SDK's own 'mcp' package.
            import sys as _sys
            _daemon_mcp = _sys.modules.get("skill_cli_daemon")
            _rewrite_loop_argv = getattr(_daemon_mcp, "_rewrite_loop_argv", None) if _daemon_mcp else None
            if _rewrite_loop_argv is not None:
                _sub_rest, _loop_err = _rewrite_loop_argv(_sub_rest)
                if _loop_err is not None:
                    print(_loop_err)
                    return 2
        args, remaining = sub_parser.parse_known_args(_sub_rest)
        # Reconstruct top-level fields the rest of main() expects.
        args.tool = None
        args.subcommand = _direct_subcommand
        for _flag in ("list_tools", "json", "format", "pretty", "verbose"):
            if not hasattr(args, _flag) or (
                _flag == "format" and getattr(args, _flag) is None and getattr(top_level_args, _flag, None) is not None
            ):
                setattr(
                    args,
                    _flag,
                    getattr(top_level_args, _flag, False if _flag != "format" else None),
                )
    elif first_command_index is not None:
        args, _ = parser.parse_known_args(argv[:first_command_index])
        args.tool = argv[first_command_index]
        args.subcommand = None
        remaining = argv[first_command_index + 1 :]
    else:
        # Parse known args first to handle dynamic tool params
        args, remaining = parser.parse_known_args()

    _configure_cli_logging(verbose=bool(args.verbose))

    # Handle plugin subcommands (ADR-260)
    if hasattr(args, "func") and args.func:
        return args.func(args, remaining)

    # Handle --list-tools
    if args.list_tools:
        tools = get_available_tools()
        if _is_machine_mode(args):
            print(format_tool_list_json(tools))
        else:
            output = format_tool_list(tools)
            if _should_suppress_color():
                output = _strip_ansi(output)
            print(output)
        return 0

    # Handle 'discover' subcommand
    if args.tool == "discover":
        from src.mcp.augur_framework.tools.domain.discovery import assemble_manifest
        from src.mcp.augur_framework.tools.domain.sessions import (
            create_session,
            delete_session,
        )

        runtime_dir = _get_runtime_dir()
        sessions_dir = runtime_dir / "sessions"

        # Create session and register cleanup
        session_id = f"cli-{os.getpid()}"
        create_session(sessions_dir, session_id=session_id, source="cli")
        atexit.register(lambda: delete_session(sessions_dir, session_id))

        # Parse discover-specific flags from remaining args
        discover_hub = None
        discover_tier = None
        discover_compact = False
        # --format from main parser takes precedence; fall back to auto-detect
        discover_format = args.format or ("markdown" if sys.stdout.isatty() else "json")
        i = 0
        while i < len(remaining):
            if remaining[i] == "--hub" and i + 1 < len(remaining):
                discover_hub = remaining[i + 1]
                i += 2
            elif remaining[i] == "--tier" and i + 1 < len(remaining):
                discover_tier = remaining[i + 1]
                i += 2
            elif remaining[i] == "--format" and i + 1 < len(remaining):
                discover_format = remaining[i + 1]
                i += 2
            elif remaining[i] == "--compact":
                discover_compact = True
                i += 1
            else:
                i += 1

        manifest = assemble_manifest(
            runtime_dir,
            hub=discover_hub,
            tier=discover_tier,
            session_id=session_id,
        )

        if discover_compact:
            for tool in manifest.get("recommended_tools", []):
                print(f"  {tool['name']:<35} {tool.get('skill', '')}")
        elif discover_format == "json":
            print(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
        elif discover_format == "text":
            _print_manifest_markdown(manifest)
        else:
            _print_manifest_markdown(manifest)

        return 0

    # Require tool name
    if not args.tool:
        parser.print_help()
        return 1

    # Get tool info
    tools = get_available_tools()

    if not tools:
        print(
            "Error: Could not load MCP tools. Is the MCP server configured?",
            file=sys.stderr,
        )
        print("Try: aug --verbose <tool> to see detailed errors", file=sys.stderr)
        return 1

    if args.tool not in tools:
        print(f"Error: Unknown tool '{args.tool}'", file=sys.stderr)
        print("\nUse --list-tools to see available tools", file=sys.stderr)
        return 1

    # Schema-driven help
    if "--help" in remaining or "-h" in remaining:
        help_text = _render_tool_help(args.tool, tools[args.tool])
        print(help_text)
        return 0

    # Parse remaining args as tool params
    # Convert --param-name value to param_name: value
    params = {}
    i = 0
    while i < len(remaining):
        arg = remaining[i]
        if arg.startswith("--"):
            param_name = arg[2:].replace("-", "_")
            if i + 1 < len(remaining) and not remaining[i + 1].startswith("--"):
                params[param_name] = parse_param_value(remaining[i + 1])
                i += 2
            else:
                # Flag without value = True
                params[param_name] = True
                i += 1
        else:
            # Positional args not supported for now
            print(f"Warning: Ignoring positional argument: {arg}", file=sys.stderr)
            i += 1

    # Execute tool
    try:
        result = asyncio.run(call_tool(args.tool, params))

        # Resolve effective output format: --format > --json/--pretty > default
        output_format = args.format or ("json" if (args.json or args.pretty) else None)

        if output_format == "json":
            try:
                data = json.loads(result) if isinstance(result, str) else result
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except (json.JSONDecodeError, TypeError):
                print(json.dumps({"result": result}, ensure_ascii=False))
        else:
            # Default: try to pretty-print JSON for readability
            try:
                data = json.loads(result) if isinstance(result, str) else result
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except (json.JSONDecodeError, TypeError):
                output = result
                if _should_suppress_color():
                    output = _strip_ansi(output)
                print(output)

        # After successful tool call, update session with tool name
        try:
            from src.mcp.augur_framework.tools.domain.sessions import (
                update_session_tool,
            )

            update_session_tool(_get_runtime_dir() / "sessions", f"cli-{os.getpid()}", args.tool)
        except Exception:
            pass  # Never fail a tool call because of session tracking

        return 0

    except Exception as e:
        if args.verbose:
            import traceback

            traceback.print_exc()
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

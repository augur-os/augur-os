"""
sync_agents — Unified Agent Synchronization Package.

ADR-186: Refactored from monolithic sync_agents.py into a package.

Usage:
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync all
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync all --purge
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync all --purge --confirm
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync all --purge-state
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync all --purge-state --confirm
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync all --purge-state --clients claude,codex
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync agents [client|all]
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync skills [client|all]
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync prompts [client|all]
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents sync commands [client|all]
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents check
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents fix
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents validate
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents clean
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents clean-hygiene
    PYTHONPATH=project-brain/capabilities python -m skills.ai.scripts.sync_agents command-surfaces
"""

from __future__ import annotations

import argparse

from .engine import (
    _normalize_client_filter,
    check_mode,
    clean_hygiene_mode,
    clean_mode,
    fix_mode,
    purge_mode,
    sync_all,
    validate_mode,
)
from .llms_txt import generate_llms_files, llms_files_drift, llms_txt_paths  # noqa: F401
from .modes import command_surfaces_mode, purge_state_mode as _purge_state_mode

from .constants import _ADAPTER_AGENT_PATHS  # noqa: F401
from .discovery import (  # noqa: F401
    _parse_md_frontmatter,
    discover_claude_plugins,
    assemble_claude_plugins,
    resolve_overlaps,
    distribute_imported_agents,
)

_SYNC_ARTIFACTS = ("all", "agents", "skills", "prompts", "commands")
_SYNC_CLIENTS = (
    "all",
    "claude-code",
    "claude-desktop",
    "cline",
    "codex",
    "codex-plugin",
    "cowork",
    "cursor",
    "gemini",
    "gemini-plugin",
    "opencode",
    "kimi",
    "copilot",
    "copilot-plugin",
    "windsurf",
    "antigravity",
)
_STATE_PURGE_CLIENTS = (
    "claude",
    "codex",
    "cursor",
    "gemini",
    "antigravity",
    "opencode",
    "kimi",
    "windsurf",
    "cowork",
)

_SYNC_CLIENT_EXPANSIONS = {
    "codex": {"codex", "codex_plugin"},
    "copilot": {"copilot", "copilot_plugin"},
}


def _parse_state_clients(raw: str | None) -> set[str] | None:
    if raw is None:
        return None
    values = {item.strip().lower() for item in raw.split(",") if item.strip()}
    invalid = values - set(_STATE_PURGE_CLIENTS)
    if invalid:
        raise ValueError(
            "Unsupported --clients value(s): "
            + ", ".join(sorted(invalid))
            + ". Supported: "
            + ", ".join(_STATE_PURGE_CLIENTS)
        )
    return values


def _parse_sync_client(client: str) -> set[str] | None:
    if client == "all":
        return None
    normalized = _normalize_client_filter(client)
    return _SYNC_CLIENT_EXPANSIONS.get(normalized, {normalized})


def purge_state_mode(selected_clients: set[str] | None = None, dry_run: bool = True) -> int:
    """Dispatch to the real state-purge implementation."""
    return _purge_state_mode(selected_clients=selected_clients, dry_run=dry_run)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync Augur agent and client artifacts")
    subparsers = parser.add_subparsers(dest="mode")

    sync_parser = subparsers.add_parser("sync", help="Sync generated artifacts")
    sync_parser.add_argument("artifact", choices=_SYNC_ARTIFACTS, help="Artifact family to sync")
    sync_parser.add_argument(
        "client",
        nargs="?",
        default="all",
        choices=_SYNC_CLIENTS,
        help="Optional client filter",
    )
    sync_parser.add_argument(
        "--purge",
        action="store_true",
        help="Remove all Augur-written files from all clients (dry-run by default)",
    )
    sync_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Execute the purge (requires --purge; without this flag purge is a dry-run)",
    )
    sync_parser.add_argument(
        "--purge-state",
        action="store_true",
        help="Remove supported client state (dry-run by default)",
    )
    sync_parser.add_argument(
        "--clients",
        help="Comma-separated supported clients for --purge-state",
    )

    subparsers.add_parser("check", help="Check if generated files need regeneration")
    subparsers.add_parser("fix", help="Regenerate and stage stale files")
    subparsers.add_parser("validate", help="Validate skill directory structure")
    subparsers.add_parser("clean", help="Delete sync-managed generated files")
    subparsers.add_parser("clean-hygiene", help="Delete repo-local integration scaffolding")
    subparsers.add_parser("command-surfaces", help="Report duplicate Augur command surfaces")

    return parser


def _dispatch_sync(
    artifact: str,
    client: str,
    purge: bool = False,
    purge_state: bool = False,
    confirm: bool = False,
    state_clients: str | None = None,
) -> int:
    if purge and purge_state:
        raise ValueError("--purge and --purge-state cannot be used together")
    if state_clients is not None and not purge_state:
        raise ValueError("--clients is only valid with --purge-state")
    if purge_state:
        if artifact != "all":
            raise ValueError("--purge-state requires sync all; use --clients to target specific clients")
        if client != "all":
            raise ValueError("--purge-state requires sync all; use --clients to target specific clients")
        return purge_state_mode(
            selected_clients=_parse_state_clients(state_clients),
            dry_run=not confirm,
        )
    if purge:
        return purge_mode(dry_run=not confirm)

    selected_clients = _parse_sync_client(client)

    if artifact == "all":
        return sync_all(selected_clients=selected_clients)
    if artifact == "agents":
        return sync_all(
            do_skill_exports=False,
            do_prompt_exports=False,
            do_command_exports=False,
            selected_clients=selected_clients,
        )
    if artifact == "skills":
        return sync_all(
            do_rules=False,
            do_subagents=False,
            do_memory=False,
            do_plugins=False,
            do_mcp_config=False,
            do_prompt_exports=False,
            do_command_exports=False,
            selected_clients=selected_clients,
        )
    if artifact == "prompts":
        return sync_all(
            do_rules=False,
            do_subagents=False,
            do_memory=False,
            do_plugins=False,
            do_mcp_config=False,
            do_skill_exports=False,
            do_command_exports=False,
            selected_clients=selected_clients,
        )
    if artifact == "commands":
        return sync_all(
            do_rules=False,
            do_subagents=False,
            do_memory=False,
            do_plugins=False,
            do_mcp_config=False,
            do_skill_exports=False,
            do_prompt_exports=False,
            selected_clients=selected_clients,
        )
    raise ValueError(f"Unsupported sync artifact: {artifact}")


def main() -> int:
    """CLI entry point for sync_agents."""
    parser = _build_parser()
    args = parser.parse_args()

    mode = args.mode or "sync"
    if mode == "sync":
        artifact = getattr(args, "artifact", "all")
        client = getattr(args, "client", "all")
        purge = getattr(args, "purge", False)
        purge_state = getattr(args, "purge_state", False)
        confirm = getattr(args, "confirm", False)
        state_clients = getattr(args, "clients", None)
        try:
            return _dispatch_sync(
                artifact,
                client,
                purge=purge,
                purge_state=purge_state,
                confirm=confirm,
                state_clients=state_clients,
            )
        except ValueError as exc:
            parser.error(str(exc))
    if mode == "check":
        return check_mode()
    if mode == "fix":
        return fix_mode()
    if mode == "validate":
        return validate_mode()
    if mode == "clean":
        return clean_mode()
    if mode == "clean-hygiene":
        return clean_hygiene_mode()
    if mode == "command-surfaces":
        return command_surfaces_mode()

    parser.error(f"Unknown mode: {mode}")
    return 2

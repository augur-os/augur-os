#!/usr/bin/env python3
"""
Configure Augur MCP server for all supported IDEs/agents.

Reads IDE configurations from config/agents/ide_mcp_configs.yaml and applies
MCP server configuration to each enabled IDE.

Supports external MCP servers declared by plugins via `mcp_servers: [...]` in
their SKILL.md frontmatter. External servers are resolved from the registry at
config/integrations/external_mcp_registry.yaml.

Default behavior is a dry-run that prints a diff. Use --apply to write changes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Setup path - add repo root to path to allow src imports
# CRITICAL: This must happen before other imports to prevent shadowing of standard library modules
repo_root_path = Path(__file__).resolve().parents[1]
SRC_DIR = repo_root_path / "src"

# Remove src dir from path if present (it shadows standard 'logging')
sys.path = [p for p in sys.path if Path(p).resolve() != SRC_DIR]

if str(repo_root_path) not in sys.path:
    sys.path.insert(0, str(repo_root_path))

from src.logging import get_entity_logger

# Configure logging
logger = get_entity_logger("configure_mcp")

import argparse
import contextlib
from typing import Any

# Submodule imports
from scripts.mcp_external_servers import (
    _load_env_file,
    _load_external_mcp_registry,
    _resolve_external_servers,
    _scan_plugin_mcp_requirements,
)
from scripts.mcp_ide_config import (
    _configure_ide,
    _configure_ide_dxt,
    _expand_path,
    _get_config_path_for_platform,
    _load_ide_registry,
    _read_json,
    _read_toml,
)
from src.cli_config.manifest import ServerEntry, load_manifest
from src.cli_config.codex_runtime import build_codex_mcp_entry
from src.config.worktrees import (
    is_linked_worktree as _shared_is_linked_worktree,
    main_checkout_for_worktree as _shared_main_checkout_for_worktree,
)
from src.config.runtime_identity import (
    GlobalIdentityError,
    GlobalIdentityLock,
    GlobalMutationGuard,
    default_global_identity_lock_path,
    resolve_runtime_identity,
)


def _default_repo_root() -> Path:
    """Get repo root from script location: scripts/configure_mcp.py -> repo root."""
    return Path(__file__).resolve().parents[1]


def _default_registry_path(repo_root: Path) -> Path:
    """Get path to IDE MCP configs registry."""
    return repo_root / "config" / "agents" / "ide_mcp_configs.yaml"


def _resolve_project_root(repo_root: Path, arg: str | None) -> Path:
    """Resolve the augur project root directory."""
    if arg and arg.strip():
        return _expand_path(arg.strip())

    env = os.environ.get("AUGUR_ROOT")
    if env and env.strip():
        return _expand_path(env.strip())

    try:
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from src.config.paths import get_project_root

        return get_project_root()
    except Exception:
        return repo_root


def _resolve_python(repo_root: Path, arg: str | None) -> Path:
    """Resolve Python interpreter path."""
    if arg and arg.strip():
        return _expand_path(arg.strip())

    repo_root = repo_root.resolve()

    try:
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from src.config.paths import get_project_root, get_python_executable

        if get_project_root() == repo_root:
            return get_python_executable()
    except Exception:
        pass

    if os.name == "nt":
        venv_python = repo_root / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = repo_root / ".venv" / "bin" / "python3"

    if venv_python.exists():
        return venv_python

    return Path(os.path.realpath(sys.executable))


def _main_checkout_for_repo(repo_root: Path) -> Path | None:
    """Return the primary checkout for a repo, when git worktree metadata is available."""
    return _shared_main_checkout_for_worktree(repo_root)


def _is_linked_worktree(repo_root: Path) -> bool:
    """Return True when repo_root is a linked worktree rather than the main checkout."""
    return _shared_is_linked_worktree(repo_root)


def _config_path_templates(ide_config: dict[str, Any]) -> list[str]:
    """Return raw config path templates from an IDE registry entry."""
    config_path = ide_config.get("config_path")
    if isinstance(config_path, str):
        return [config_path]
    if isinstance(config_path, dict):
        return [value for value in config_path.values() if isinstance(value, str)]
    return []


def _config_path_is_repo_local(ide_config: dict[str, Any]) -> bool:
    """Return True for IDE config files intentionally written under the repo root."""
    return any("{repo_root}" in template for template in _config_path_templates(ide_config))


def _effective_repo_root_for_ide(
    requested_repo_root: Path,
    ide_config: dict[str, Any],
    main_checkout: Path | None = None,
) -> Path:
    """Choose the Augur root to stamp into one IDE config."""
    if _config_path_is_repo_local(ide_config):
        return requested_repo_root
    if main_checkout and _is_linked_worktree(requested_repo_root):
        return main_checkout
    return requested_repo_root


_IDE_CLIENT_IDS: dict[str, str] = {
    "claude_desktop": "cowork",
    "claude_code": "claude",
    "cursor": "cursor",
    "windsurf": "windsurf",
    "codex_cli": "codex",
    "copilot_cli": "copilot",
    "vscode_copilot": "copilot",
    "opencode": "opencode",
    "gemini": "gemini",
    "antigravity": "antigravity",
    "cline": "cline",
}


def _load_augur_server_entries(
    repo_root: Path,
    *,
    client_id: str,
    existing_server_ids: set[str] | None = None,
) -> list[ServerEntry]:
    """Load the canonical Augur MCP server topology."""
    manifest = load_manifest(repo_root / "config" / "system" / "mcp_servers.yaml")
    return manifest.all_augur_servers_for_client(
        client_id,
        existing_server_ids=existing_server_ids,
    )


def _augur_claude_code_plugin_installed() -> bool:
    """Return True when the Augur cowork plugin is installed for Claude Code.

    The plugin's .mcp.json registers the vault_tier (bundle) servers itself,
    so configure_mcp must skip them when writing ~/.claude.json — otherwise
    the same entries are duplicated and Claude Code's /doctor reports
    "MCP server X skipped — same command/URL as already-configured X".
    """
    try:
        registry = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
        if not registry.is_file():
            return False
        import json as _json
        data = _json.loads(registry.read_text(encoding="utf-8"))
        plugins = data.get("plugins") or {}
        return any(name.startswith("augur@") for name in plugins)
    except (OSError, ValueError):
        return False


def _server_module(entry: ServerEntry) -> str | None:
    """Return the Python module launched by a manifest entry, when applicable."""
    try:
        module_index = entry.args.index("-m") + 1
    except ValueError:
        return None
    if module_index >= len(entry.args):
        return None
    return entry.args[module_index]


def _assert_module_exists(repo_root: Path, entry: ServerEntry) -> None:
    """Fail early when a manifest entry points at a missing local MCP module."""
    module = _server_module(entry)
    if not module:
        return
    module_path = repo_root / "src" / "mcp" / Path(*module.split("."))
    if not module_path.exists() and not module_path.with_suffix(".py").exists():
        raise SystemExit(
            f"Expected Augur MCP module at {module_path} or {module_path.with_suffix('.py')}"
        )


def _args_for_client(entry: ServerEntry, client_id: str | None) -> list[str]:
    """Render server args for a concrete client."""
    args = list(entry.args)
    if client_id and client_id in entry.per_client_args:
        args.extend(entry.per_client_args[client_id])
    elif client_id and _server_module(entry) != "augur_shared.bundle_server":
        args.extend(["--client-id", client_id])
    return args


def _resolve_mcp_runtime(
    repo_root: Path,
    entry: ServerEntry,
    client_id: str | None = None,
) -> tuple[list[str], Path]:
    """Resolve MCP launch args and working directory for one split server."""
    _assert_module_exists(repo_root, entry)
    return _args_for_client(entry, client_id), repo_root


def _build_server_entry(
    python_path: Path,
    repo_root: Path,
    mcp_args: list[str],
    mcp_cwd: Path,
) -> dict[str, Any]:
    """Build the MCP server entry for config files."""
    return {
        "command": str(python_path),
        "args": mcp_args,
        "cwd": str(mcp_cwd),
        "env": {
            "AUGUR_ROOT": str(repo_root),
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": os.pathsep.join(
                [
                    str(repo_root / "project-brain" / "capabilities"),
                    str(repo_root),
                    str(repo_root / "src" / "mcp"),
                ]
            ),
        },
    }


def _build_codex_server_entry(entry: ServerEntry, repo_root: Path) -> dict[str, Any]:
    """Build a worktree-aware Codex MCP entry for one manifest server."""
    mcp_args, _ = _resolve_mcp_runtime(repo_root, entry, client_id="codex")
    return build_codex_mcp_entry(
        mcp_args,
        configured_root=repo_root,
        startup_timeout_sec=entry.startup_timeout_sec,
    )


def _build_augur_server_entries_for_ide(
    ide_name: str,
    python_path: Path,
    repo_root: Path,
    existing_server_ids: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build all canonical Augur MCP server entries for a specific IDE/client."""
    client_id = _IDE_CLIENT_IDS.get(ide_name, ide_name)
    entries = _load_augur_server_entries(
        repo_root,
        client_id=client_id,
        existing_server_ids=existing_server_ids,
    )
    # Gemini CLI sends all active MCP tools as function declarations in a
    # single GenerateContent request. The project-tier Augur servers already
    # expose a broad surface, so adding vault-tier bundle servers can exceed
    # Gemini's 512 function-declaration limit before inference starts.
    if ide_name == "gemini":
        entries = [entry for entry in entries if not entry.bundle]
    # When the Augur Claude Code plugin is installed it ships the vault_tier
    # (bundle) servers itself; writing the same entries to ~/.claude.json
    # produces /doctor "skipped — same command/URL" warnings for each one.
    # Skip the bundle entries here so the plugin remains the sole source.
    if ide_name == "claude_code" and _augur_claude_code_plugin_installed():
        entries = [entry for entry in entries if not entry.bundle]

    if ide_name == "codex_cli":
        return {entry.id: _build_codex_server_entry(entry, repo_root) for entry in entries}

    server_entries: dict[str, dict[str, Any]] = {}
    for entry in entries:
        mcp_args, mcp_cwd = _resolve_mcp_runtime(repo_root, entry, client_id=client_id)
        server_entries[entry.id] = _build_server_entry(python_path, repo_root, mcp_args, mcp_cwd)
    return server_entries


def _existing_augur_server_ids_for_ide(
    ide_name: str,
    ide_config: dict[str, Any],
    repo_root: Path,
    cli_overrides: dict[str, str | None],
) -> set[str]:
    """Return Augur MCP server IDs already present in a target IDE config."""
    cli_arg = ide_config.get("cli_arg", f"--{ide_name.replace('_', '-')}-config")
    override_key = cli_arg.lstrip("-").replace("-", "_")
    cli_value = cli_overrides.get(override_key)
    if cli_value == "none":
        return set()

    if cli_value:
        config_path = _expand_path(cli_value, repo_root)
    else:
        config_path = _get_config_path_for_platform(ide_config, repo_root)
    if not config_path:
        return set()

    config_format = ide_config.get("config_format", "json")
    config_structure = ide_config.get("config_structure", "flat")
    server_key = ide_config.get("server_key", "mcpServers")
    current_config = (
        _read_toml(config_path) if config_format == "toml" else _read_json(config_path)
    )

    if config_structure == "per_project":
        projects = current_config.get("projects")
        project_config = None
        if isinstance(projects, dict):
            target_path = repo_root.resolve()
            matched_key = None
            for k in projects:
                try:
                    if Path(k).resolve() == target_path:
                        matched_key = k
                        break
                except Exception:
                    pass
            project_config = projects.get(matched_key or str(repo_root))
        servers = (
            project_config.get(server_key)
            if isinstance(project_config, dict)
            else None
        )
    else:
        servers = current_config.get(server_key)

    if not isinstance(servers, dict):
        return set()
    return {str(server_id) for server_id in servers if str(server_id).startswith("augur")}


def _build_augur_server_entry_for_ide(
    ide_name: str,
    python_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    """Build the framework server entry for legacy single-entry callers."""
    entries = _build_augur_server_entries_for_ide(ide_name, python_path, repo_root)
    return entries.get("augur-framework") or next(iter(entries.values()))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure Augur MCP server for all supported IDEs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run (show what would change)
  python configure_mcp.py

  # Apply changes
  python configure_mcp.py --apply

  # Auto-apply silently (for scripts)
  python configure_mcp.py --auto

  # Skip specific IDE
  python configure_mcp.py --apply --claude-config none

  # Override config path
  python configure_mcp.py --apply --opencode-config ~/.myconfig.json

  # Configure only a specific client (implies --auto)
  python configure_mcp.py --client claude-code

  # Dry-run for a specific client
  python configure_mcp.py --client cursor --check

IDE configurations are loaded from config/agents/ide_mcp_configs.yaml
To add a new IDE, edit that file and add a new entry.
        """,
    )

    parser.add_argument("--repo-root", help="Path to the augur repo root (auto-detected by default)", default=None)
    parser.add_argument("--python", dest="python_path", help="Path to Python interpreter for MCP server", default=None)
    parser.add_argument(
        "--server-name",
        help="Deprecated. Augur now writes canonical split server names from config/system/mcp_servers.yaml.",
        default="augur",
    )
    parser.add_argument("--apply", action="store_true", help="Write changes to config files (default is dry-run)")
    parser.add_argument("--check", action="store_true", help="Check if configured. Returns 0 if OK, 1 if needs config. Silent unless --verbose.")
    parser.add_argument("--auto", action="store_true", help="Auto-apply changes if needed. Silent on success.")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output in --check or --auto mode")
    parser.add_argument("--list-ides", action="store_true", help="List all supported IDEs from registry and exit")
    parser.add_argument("--no-external", action="store_true", help="Skip external MCP servers (only configure augur server)")
    parser.add_argument("--list-external", action="store_true", help="List available external MCP servers and exit")
    parser.add_argument("--validate", action="store_true", help="Validate external MCP registry and plugin declarations, then exit")
    parser.add_argument(
        "--client", metavar="PLATFORM", default=None,
        help="Only configure MCP for the specified client/platform (e.g., claude-code, cursor, obsidian). Implies --auto when used without --apply or --check.",
    )

    # Parse known args first to get repo_root, then add dynamic IDE args
    args, remaining = parser.parse_known_args()

    repo_root = _expand_path(args.repo_root) if args.repo_root else _default_repo_root()
    registry_path = _default_registry_path(repo_root)
    registry = _load_ide_registry(registry_path)
    ides = registry.get("ides", {})

    # Add dynamic arguments for each IDE
    for ide_name, ide_config in ides.items():
        cli_arg = ide_config.get("cli_arg", f"--{ide_name.replace('_', '-')}-config")
        display_name = ide_config.get("display_name", ide_name)
        parser.add_argument(
            cli_arg,
            help=f"Path to {display_name} config. Set to 'none' to skip.",
            default=None,
            dest=cli_arg.lstrip("-").replace("-", "_"),
        )

    # Re-parse with all arguments
    args = parser.parse_args()

    # Handle --client: filter IDEs to a single matching client
    if args.client:
        client_key = args.client.strip().replace("-", "_").lower()
        # Normalize platform aliases (cowork -> claude_desktop)
        _PLATFORM_ALIASES = {"cowork": "claude_desktop"}
        client_key = _PLATFORM_ALIASES.get(client_key, client_key)
        matched = {k: v for k, v in ides.items() if k == client_key}
        if not matched:
            for k, v in ides.items():
                display = v.get("display_name", "").lower().replace(" ", "_").replace("-", "_")
                if display == client_key or display.replace("_", "") == client_key.replace("_", ""):
                    matched = {k: v}
                    break
        if not matched:
            print(f"Error: unknown client '{args.client}'. Use --list-ides to see available clients.")
            return 1
        ides = matched
        if not args.apply and not args.check:
            args.auto = True

    # Handle --list-ides
    if args.list_ides:
        print("Supported IDEs (from config/agents/ide_mcp_configs.yaml):\n")
        for ide_name, ide_config in ides.items():
            enabled = ide_config.get("enabled", False)
            display = ide_config.get("display_name", ide_name)
            cli_arg = ide_config.get("cli_arg", f"--{ide_name}-config")
            status = "enabled" if enabled else "disabled"
            print(f"  {ide_name:20} {display:25} [{status}]")
            print(f"    CLI: {cli_arg}")
            notes = ide_config.get("notes", "")
            if notes:
                print(f"    {notes}")
            print()
        return 0

    # Handle --list-external
    if args.list_external:
        ext_registry = _load_external_mcp_registry(repo_root)
        extra_env = _load_env_file(repo_root)
        required = _scan_plugin_mcp_requirements(repo_root)
        print("External MCP servers (from config/integrations/external_mcp_registry.yaml):\n")
        for sid, sdef in ext_registry.items():
            enabled = sdef.get("enabled", False)
            tier = sdef.get("tier", "?")
            cost = sdef.get("cost", "?")
            name = sdef.get("name", sid)
            desc = sdef.get("description", "")
            in_use = sid in required
            env_reqs = sdef.get("env_required", [])
            env_ok = (
                all((extra_env.get(e["name"]) or os.environ.get(e["name"])) for e in env_reqs) if env_reqs else True
            )
            status_parts = []
            if enabled:
                status_parts.append("enabled")
            if in_use:
                status_parts.append("required by plugin")
            if not env_ok:
                status_parts.append("missing env vars")
            status = ", ".join(status_parts) if status_parts else "available"
            print(f"  {sid:20} T{tier} ({cost:8}) [{status}]")
            print(f"    {name}: {desc}")
            if env_reqs:
                missing = [e["name"] for e in env_reqs if not (extra_env.get(e["name"]) or os.environ.get(e["name"]))]
                if missing:
                    print(f"    Missing: {', '.join(missing)}")
            print()
        return 0

    # Handle --validate
    if args.validate:
        ext_registry = _load_external_mcp_registry(repo_root)
        required = _scan_plugin_mcp_requirements(repo_root)
        errors = 0
        for sid in required:
            if sid not in ext_registry:
                print(f"ERROR: Plugin requires unknown MCP server '{sid}'")
                errors += 1
        for sid, sdef in ext_registry.items():
            service_type = sdef.get("type", "mcp")
            if service_type == "mcp" and not sdef.get("command"):
                print(f"ERROR: MCP server '{sid}' has no command defined")
                errors += 1
            elif service_type == "cli" and not sdef.get("check_command"):
                print(f"ERROR: CLI service '{sid}' has no check_command defined")
                errors += 1
        if errors:
            print(f"\n{errors} validation error(s) found.")
            return 1
        print(f"Validation passed. {len(ext_registry)} services in registry, {len(required)} required by plugins.")
        return 0

    # Resolve paths
    identity = resolve_runtime_identity(repo_root)
    main_checkout = identity.authority_root if identity.is_linked_worktree else None
    # Determine modes
    quiet_mode = (args.check or args.auto) and not args.verbose
    should_apply = args.apply or args.auto

    # Resolve external MCP servers
    ext_servers: dict[str, dict[str, Any]] = {}
    if not args.no_external:
        ext_registry = _load_external_mcp_registry(repo_root)
        extra_env = _load_env_file(repo_root)
        required = _scan_plugin_mcp_requirements(repo_root)
        ext_servers = _resolve_external_servers(ext_registry, required, extra_env)
        if ext_servers and not quiet_mode:
            print(f"External MCP servers: {', '.join(ext_servers.keys())}")

    # Collect CLI overrides
    cli_overrides = {}
    for ide_name, ide_config in ides.items():
        cli_arg = ide_config.get("cli_arg", f"--{ide_name.replace('_', '-')}-config")
        attr_name = cli_arg.lstrip("-").replace("-", "_")
        cli_overrides[attr_name] = getattr(args, attr_name, None)

    # Configure each enabled IDE
    changes_pending = False
    for ide_name, ide_config in ides.items():
        if not ide_config.get("enabled", False):
            continue

        config_format = ide_config.get("config_format", "json")
        try:
            ide_repo_root = _effective_repo_root_for_ide(
                repo_root,
                ide_config,
                main_checkout=main_checkout,
            )
            is_global_apply = should_apply and not _config_path_is_repo_local(ide_config)
            lock_context = (
                GlobalIdentityLock(default_global_identity_lock_path())
                if is_global_apply
                else contextlib.nullcontext()
            )
            guard_context = (
                GlobalMutationGuard(
                    identity,
                    target_root=ide_repo_root,
                    operation=f"configure_mcp:{ide_name}",
                    allow_delegated=True,
                )
                if is_global_apply
                else contextlib.nullcontext()
            )
            with lock_context:
                with guard_context:
                    python_path = _resolve_python(ide_repo_root, args.python_path)
                    ide_servers = dict(ext_servers)
                    existing_augur_server_ids = _existing_augur_server_ids_for_ide(
                        ide_name,
                        ide_config,
                        ide_repo_root,
                        cli_overrides,
                    )
                    augur_entries = _build_augur_server_entries_for_ide(
                        ide_name,
                        python_path,
                        ide_repo_root,
                        existing_server_ids=existing_augur_server_ids,
                    )
                    ide_servers.update(augur_entries)
                    if config_format == "dxt":
                        dxt_entry = augur_entries.get("augur-framework") or next(iter(augur_entries.values()))
                        mcp_args = dxt_entry["args"]
                        mcp_cwd = Path(dxt_entry.get("cwd", ide_repo_root))
                        had_changes = _configure_ide_dxt(
                            ide_name, ide_config, ide_repo_root, python_path,
                            mcp_args, mcp_cwd, cli_overrides, should_apply, quiet_mode,
                        )
                    else:
                        had_changes = _configure_ide(
                            ide_name, ide_config, ide_repo_root, ide_servers,
                            cli_overrides, should_apply, quiet_mode,
                        )
            if had_changes:
                changes_pending = True
        except GlobalIdentityError:
            raise
        except Exception as e:
            if not quiet_mode:
                print(f"Error configuring {ide_name}: {e}")

    # Handle different modes
    if args.check:
        if changes_pending:
            if args.verbose:
                print("\nMCP configuration needs update.")
            return 1
        if args.verbose:
            print("\nMCP configuration is up to date.")
        return 0

    if args.auto:
        if changes_pending:
            if args.verbose:
                print("\nMCP configuration auto-applied.")
            else:
                print("MCP configuration updated.")
        return 0

    # Normal mode
    if not changes_pending:
        print("\nAll configurations are up to date.")
        return 0

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to write changes.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

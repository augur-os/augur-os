"""`aug config sync` orchestrator.

Reads config/system/mcp_servers.yaml and applies it to user-tier
client configs (Claude / Codex / Gemini / Copilot).

Subcommand entry registered into the existing `aug` CLI via
register_config_subcommands(subparsers).
"""

from __future__ import annotations

import argparse

from src.cli_config.adapters import ALL_ADAPTERS, ClientConfigAdapter
from src.cli_config.manifest import Manifest, load_manifest
from src.config.paths import get_project_root
from src.lib.mcp_project_config import generate_project_mcp_json


def register_config_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Wire `aug config <subcommand>` into the parent CLI."""
    config = subparsers.add_parser("config", help="Manage Augur MCP server topology and client configs")
    sub = config.add_subparsers(dest="config_command", required=True)

    sync = sub.add_parser("sync", help="Sync user-tier AI client configs from manifest")
    sync.add_argument(
        "--dry-run",
        action="store_true",
        help="Show diffs without writing to client configs.",
    )
    sync.add_argument(
        "--client",
        choices=[a.name for a in ALL_ADAPTERS],
        help="Sync only one client; default syncs all clients.",
    )
    sync.set_defaults(func=_handle_sync)

    status = sub.add_parser("status", help="Show drift between manifest and client configs")
    status.add_argument(
        "--client",
        choices=[a.name for a in ALL_ADAPTERS],
        help="Show drift for one client; default shows all clients.",
    )
    status.set_defaults(func=_handle_status)

    reconcile = sub.add_parser(
        "reconcile-paths",
        help="Record moved Augur roots and auto-repair dangling client MCP config paths",
    )
    reconcile.set_defaults(func=_handle_reconcile_paths)


def _handle_sync(args: argparse.Namespace, remaining: list[str] | None = None) -> int:
    manifest = load_manifest()
    adapters = _select_adapters(args.client)

    if args.dry_run:
        return _print_diffs(manifest, adapters)

    rc = 0
    for adapter in adapters:
        diff = adapter.diff(manifest)
        if not diff.has_changes:
            print(f"[{adapter.name}] no changes")
            continue
        backup = adapter.apply(manifest)
        backup_msg = f"backup: {backup}" if backup else "no backup (no prior config)"
        print(f"[{adapter.name}] applied: +{len(diff.added)} ~{len(diff.updated)} -{len(diff.removed)} ({backup_msg})")
    if args.client is None:
        project_mcp = generate_project_mcp_json(manifest.all_augur_servers(), get_project_root() / ".mcp.json")
        print(f"[project-mcp] wrote {project_mcp}")
    return rc


def _handle_status(args: argparse.Namespace, remaining: list[str] | None = None) -> int:
    manifest = load_manifest()
    adapters = _select_adapters(args.client)
    return _print_diffs(manifest, adapters)


def _handle_reconcile_paths(args: argparse.Namespace, remaining: list[str] | None = None) -> int:
    """Record any moved canonical root, then detect + repair dangling client paths."""
    from src.lib.mcp_client_config_audit import reconcile_and_repair

    result = reconcile_and_repair()
    recorded = result["recorded"]
    findings = result["findings"]
    repaired = result["repaired"]

    if recorded:
        for r in recorded:
            print(f"[recorded] {r['root']}: {r['old']} -> {r['new']}")
    else:
        print("[recorded] no new root moves detected")

    print(f"[scanned] {result['sources_scanned']} client config(s)")

    if findings:
        for d in findings:
            print(f"[dangling] {d}")
    else:
        print("[dangling] none")

    if repaired:
        for a in repaired:
            print(f"[repaired] {a['client']}: {a['location']} {a['old']} -> {a['new']}")
        print(
            "\nNote: the client must respawn its MCP server to pick up the change "
            "(toggle the extension / restart the client)."
        )
    else:
        print("[repaired] nothing to repair")
    return 0


def _print_diffs(manifest: Manifest, adapters: tuple[ClientConfigAdapter, ...]) -> int:
    any_drift = False
    for adapter in adapters:
        diff = adapter.diff(manifest)
        if not diff.has_changes:
            print(f"[{adapter.name}] in sync")
            continue
        any_drift = True
        print(f"[{adapter.name}] drift:")
        for e in diff.added:
            print(f"  + {e.id}")
        for e in diff.updated:
            print(f"  ~ {e.id}")
        for sid in diff.removed:
            print(f"  - {sid}")
    return 1 if any_drift else 0


def _select_adapters(client: str | None) -> tuple[ClientConfigAdapter, ...]:
    if client is None:
        return ALL_ADAPTERS
    return tuple(a for a in ALL_ADAPTERS if a.name == client)

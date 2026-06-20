"""
_cli_commands — Project subcommand handlers for the Augur CLI.

Handles: _handle_project_status, _handle_project_init, _register_project_subcommands.
The ordering-critical _handle_init and _register_builtin_subcommands stay in cli.py.

Split from src/cli.py (WS5, behavior-preserving — no importer changes).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _project_output_format(args: argparse.Namespace) -> str:
    return str(getattr(args, "format", None) or ("json" if getattr(args, "json", False) else "text"))


def _project_registry_path(args: argparse.Namespace) -> Path | None:
    registry = getattr(args, "registry", None)
    return Path(registry).expanduser() if registry else None


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


def _handle_project_status(args: argparse.Namespace, remaining: list[str] | None = None) -> int:
    del remaining
    from src.lib.project_scope import inspect_project_scope

    status = inspect_project_scope(
        Path(args.project),
        registry_path=_project_registry_path(args),
    )
    _print_project_payload(status.to_dict(), _project_output_format(args))
    return 0 if status.can_init or status.initialized else 1


def _handle_project_init(args: argparse.Namespace, remaining: list[str] | None = None) -> int:
    del remaining
    from src.lib.brain_init import init_project_brain
    from src.lib.onboarding_journey import (
        activate_project_launch_context,
        build_project_init_launch_journey,
    )
    from src.lib.project_scope import inspect_project_scope

    registry_path = _project_registry_path(args)
    result = init_project_brain(
        Path(args.project),
        registry_path=registry_path,
        run_sync=bool(getattr(args, "sync", False)),
    )
    status = inspect_project_scope(
        result.project_root,
        registry_path=registry_path,
    )
    launch_context = activate_project_launch_context(
        result,
        registry_path=registry_path,
    )

    def _launch_context_payload(context_result: Any) -> dict[str, object]:
        from src.lib.onboarding_journey import serialize_project_launch_context

        return serialize_project_launch_context(context_result)

    payload = status.to_dict()
    payload.update(
        {
            "created": result.created,
            "sync_returncode": result.sync_returncode,
            "inventory_path": str(result.inventory_path) if result.inventory_path is not None else None,
            "inventory_count": result.inventory_count,
            "inventory_warning_count": result.inventory_warning_count,
            "launch_journey": build_project_init_launch_journey(result),
            "launch_context": _launch_context_payload(launch_context),
        }
    )
    _print_project_payload(payload, _project_output_format(args))
    if result.sync_returncode not in (None, 0):
        return result.sync_returncode
    return 0


def _register_project_subcommands(project_subparsers: Any) -> None:
    status = project_subparsers.add_parser("status", help="Inspect project-brain attachment for a folder")
    status.add_argument(
        "--project",
        default=".",
        help="Project root to inspect (default: current directory)",
    )
    status.add_argument(
        "--registry",
        default=None,
        help="Registry path override for tests and controlled runs",
    )
    status.add_argument("--format", choices=["json", "text"], default=None, help="Output format")
    status.set_defaults(func=_handle_project_status)

    init = project_subparsers.add_parser("init", help="Create or attach a project brain in a folder")
    init.add_argument("--project", default=".", help="Project root to initialize or attach")
    init.add_argument(
        "--registry",
        default=None,
        help="Registry path override for tests and controlled runs",
    )
    init.add_argument("--format", choices=["json", "text"], default=None, help="Output format")
    init.add_argument(
        "--sync",
        action="store_true",
        help="Also regenerate generated AI-client projections",
    )
    init.set_defaults(func=_handle_project_init)

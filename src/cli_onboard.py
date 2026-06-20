"""`aug onboard run` — drive the cross-OS onboard engine. See
docs/superpowers/specs/2026-06-16-onboard-engine-m3-design.md."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.lib.onboard.driver import is_hard_failure, run_onboard
from src.lib.onboard.result import OnboardContext


def register_onboard_subcommands(subparsers: argparse._SubParsersAction) -> None:
    onboard = subparsers.add_parser("onboard", help="Install/verify Augur (cross-OS onboard engine)")
    sub = onboard.add_subparsers(dest="onboard_command", required=True)
    run = sub.add_parser("run", help="Run the onboard steps to a verified system")
    run.add_argument(
        "--non-interactive", action="store_true", help="CI mode: treat a guide/blocked step as a hard failure."
    )
    run.add_argument("--project", default=None, help="Repo root (defaults to cwd).")
    run.set_defaults(func=_handle_onboard_run)


def _handle_onboard_run(args: argparse.Namespace, remaining: list[str] | None = None) -> int:
    repo_root = Path(args.project) if args.project else Path.cwd()
    ctx = OnboardContext(repo_root=repo_root, non_interactive=bool(args.non_interactive))
    results = run_onboard(ctx)
    return 1 if is_hard_failure(results, ctx) else 0

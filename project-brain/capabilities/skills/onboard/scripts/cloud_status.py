#!/usr/bin/env python3
"""Print read-only cloud execution readiness for onboarding."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys
from typing import Sequence

def _ensure_project_paths(start: Path) -> Path:
    for candidate in (start.parent, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "src" / "config" / "paths.py").is_file()
        ):
            for path in (candidate / "src" / "mcp", candidate, candidate / "project-brain"):
                text = str(path)
                if text not in sys.path:
                    sys.path.insert(0, text)
            return candidate
    raise RuntimeError(f"Unable to locate Augur project root from {start}")


PROJECT_ROOT = _ensure_project_paths(Path(__file__).resolve())

from src.lib.ai.cloud_execution import (  # noqa: E402
    CloudClientStatus,
    classify_cloud_status,
    load_cloud_profiles,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Show read-only cloud execution readiness for Augur clients.",
    )
    parser.add_argument("--repo-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--profiles", type=Path, default=None)
    parser.add_argument("--client", default=None, metavar="CLIENT")
    parser.add_argument("--mode", choices=("review", "write"), default="review")
    parser.add_argument("--no-env", action="store_true")
    parser.add_argument("--enable-mutation", action="append", default=[], metavar="CLIENT")
    args = parser.parse_args(argv)

    try:
        profiles = load_cloud_profiles(args.profiles)
    except Exception as exc:
        print(f"Cloud status error: {exc}", file=sys.stderr)
        return 1

    if args.client is not None and args.client not in profiles:
        available = ", ".join(sorted(profiles))
        print(
            f"Cloud status error: unknown cloud client: {args.client} "
            f"(available: {available})",
            file=sys.stderr,
        )
        return 2

    selected_profiles = (
        {args.client: profiles[args.client]} if args.client is not None else profiles
    )
    env = {} if args.no_env else os.environ
    enabled_mutation_clients = set(args.enable_mutation)
    if args.mode == "write":
        if args.client is not None:
            enabled_mutation_clients.add(args.client)
        else:
            enabled_mutation_clients.update(selected_profiles)

    statuses = [
        classify_cloud_status(
            profile,
            repo_root=args.repo_root,
            env=env,
            command_exists=shutil.which,
            enabled_mutation_clients=enabled_mutation_clients,
        )
        for profile in selected_profiles.values()
    ]
    print(_format_table(statuses))
    return 0


def _format_table(statuses: Sequence[CloudClientStatus]) -> str:
    headers = ("Client", "CLI", "Workflow", "Review", "Write", "Status", "Blockers")
    rows = [
        (
            status.display_name,
            "present" if status.local_cli_present else "missing",
            _workflow_label(status.workflow_present),
            "ready" if status.cloud_review_ready else "blocked",
            "enabled" if status.cloud_mutation_enabled else "disabled",
            status.status,
            _blockers_label((*status.blockers, *status.mutation_blockers)),
        )
        for status in statuses
    ]
    widths = [
        max(len(str(row[index])) for row in (headers, *rows))
        for index in range(len(headers))
    ]
    lines = [
        "  ".join(str(value).ljust(widths[index]) for index, value in enumerate(headers)),
        "  ".join("-" * width for width in widths),
    ]
    lines.extend(
        "  ".join(str(value).ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )
    return "\n".join(lines)


def _workflow_label(workflow_present: bool | None) -> str:
    if workflow_present is None:
        return "n/a"
    return "present" if workflow_present else "missing"


def _blockers_label(blockers: Sequence[str]) -> str:
    if not blockers:
        return "-"
    return "; ".join(blockers)


if __name__ == "__main__":
    raise SystemExit(main())

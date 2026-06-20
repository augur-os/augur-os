#!/usr/bin/env python3
"""Run the ADR-786 harness-layering family closeout."""

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

import argparse
import json
from pathlib import Path

from src.config.paths import get_client_skill_dirs, get_project_root
from src.lib.brain_closeout import (
    CloseoutReport,
    default_memory_targets,
    default_moved_path_fragments,
    enabled_clients_from_dirs,
    project_tier_skill_names,
    scan_orphan_references,
    verify_family_closeout,
)
from src.lib.brain_stack import resolve_active_stack


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run ADR-786 harness-layering closeout")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument(
        "--client",
        action="append",
        dest="clients",
        help="Client id to verify. May be repeated. Defaults to configured clients with skill dirs.",
    )
    args = parser.parse_args(argv)

    project_root = get_project_root()
    stack = resolve_active_stack(cwd=project_root)
    client_dirs = get_client_skill_dirs()
    clients = tuple(args.clients or enabled_clients_from_dirs(client_dirs))
    if not clients:
        clients = ("codex",)

    orphan_refs = scan_orphan_references(
        _default_scan_roots(project_root),
        default_moved_path_fragments(),
    )
    report = verify_family_closeout(
        stack,
        clients=clients,
        client_dirs=client_dirs,
        single_brain_skills=project_tier_skill_names(stack),
        orphan_refs=orphan_refs,
        project_root=project_root,
        memory_targets=default_memory_targets(project_root, clients),
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_report(report))
    return 0 if report.all_ok else 1


def _default_scan_roots(project_root: Path) -> list[Path]:
    candidates = [
        project_root / "src",
        project_root / "config",
        project_root / "scripts",
        project_root / "apps" / "dashboard",
        project_root / "project-brain" / "capabilities" / "skills",
    ]
    return [path for path in candidates if path.exists()]


def render_report(report: CloseoutReport) -> str:
    sections = report.sections
    lines = [
        "Harness Layering Closeout",
        f"generated_at: {report.generated_at}",
        f"all_ok: {str(report.all_ok).lower()}",
        "",
        "Tiers:",
    ]
    for tier in sections.get("tiers", {}).get("items", []):
        lines.append(f"- {tier['tier']} {tier['brain_id']} {tier['root']}")

    lines.extend(["", "Clients:"])
    harness = sections.get("harness", {})
    for client, result in sorted(harness.items()):
        if client == "all_ok" or not isinstance(result, dict):
            continue
        status = "OK" if result.get("ok") else "FAIL"
        missing = result.get("missing") or []
        suffix = f" missing={', '.join(missing[:8])}" if missing else ""
        lines.append(f"- {client}: {status}{suffix}")

    parity = sections.get("parity", {})
    lines.extend(
        [
            "",
            f"Parity: {'OK' if parity.get('ok') else 'FAIL'}",
            f"- added: {len(parity.get('added') or [])}",
            f"- dropped: {len(parity.get('dropped') or [])}",
        ]
    )

    orphan_refs = sections.get("orphan_refs", {})
    lines.extend(
        [
            "",
            f"Orphan references: {'OK' if orphan_refs.get('ok') else 'FAIL'}",
            f"- count: {orphan_refs.get('count', 0)}",
        ]
    )
    for ref in (orphan_refs.get("refs") or [])[:10]:
        lines.append(f"  - {ref}")

    memory = sections.get("memory_round_trip", {})
    lines.extend(
        [
            "",
            f"Memory round-trip: {'OK' if memory.get('ok') else 'FAIL'}",
            f"- entries: {memory.get('entry_count', 0)}",
            f"- samples: {', '.join(memory.get('sample_entries') or [])}",
        ]
    )
    targets = memory.get("client_targets") or {}
    for client, result in sorted(targets.items()):
        if not isinstance(result, dict):
            continue
        checked = "checked" if result.get("checked") else "not checked"
        status = "OK" if result.get("ok") else "FAIL"
        path = result.get("path")
        lines.append(f"  - {client}: {status} ({checked}) {path or ''}".rstrip())

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Incident runbook index for DevOps skill.

Outputs JSON describing available incident and rollout runbooks.
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
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_project_root
from src.lib.skill_paths import get_own_data_dir


def _slugify(name: str) -> str:
    return (
        name.lower()
        .replace(".md", "")
        .replace(" ", "-")
        .replace("_", "-")
    )


def _updated(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _collect_runbooks(root: Path) -> list[dict[str, str]]:
    skill_root = root / "plugins" / "dev" / "skills" / "platform-admin"
    skill_data_dir = get_own_data_dir(__file__)
    sources = [
        ("protocol", skill_root / "modules" / "rollback-protocol.md"),
        ("incident", skill_data_dir / "incidents"),
        ("rollout", skill_data_dir / "rollouts"),
    ]

    runbooks: list[dict[str, str]] = []
    for runbook_type, source in sources:
        if source.is_file():
            runbooks.append(
                {
                    "id": _slugify(source.name),
                    "type": runbook_type,
                    "title": source.stem.replace("-", " ").title(),
                    "path": str(source.relative_to(root)),
                    "updated": _updated(source),
                }
            )
            continue

        if not source.exists():
            continue

        for file_path in sorted(source.glob("*.md")):
            runbooks.append(
                {
                    "id": _slugify(file_path.name),
                    "type": runbook_type,
                    "title": file_path.stem.replace("-", " ").title(),
                    "path": str(file_path.relative_to(root)),
                    "updated": _updated(file_path),
                }
            )

    return runbooks


def _with_content_preview(root: Path, runbooks: list[dict[str, str]], query: str) -> list[dict[str, str]]:
    normalized = query.strip().lower()
    filtered: list[dict[str, str]] = []

    for runbook in runbooks:
        if normalized not in runbook["id"] and normalized not in runbook["title"].lower():
            continue

        file_path = root / runbook["path"]
        preview = ""
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
            preview = "\n".join(lines[:30]).strip()
        except Exception:
            preview = ""

        enriched = dict(runbook)
        enriched["preview"] = preview
        filtered.append(enriched)

    return filtered


def main() -> int:
    parser = argparse.ArgumentParser(description="List DevOps incident runbooks")
    parser.add_argument("--incident", help="Optional incident/runbook identifier to filter", default="")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    root = get_project_root()
    runbooks = _collect_runbooks(root)

    selected = runbooks
    if args.incident:
        selected = _with_content_preview(root, runbooks, args.incident)

    payload = {
        "success": True,
        "count": len(selected),
        "runbooks": selected,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for runbook in selected:
            print(f"- {runbook['title']} [{runbook['type']}] ({runbook['path']})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Simplify Code
Records a simplification pass with quick suggestions.
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
import os
import sys
from datetime import datetime
from typing import Any

# Keep direct CLI execution consistent with the other devops utilities.
sys.path.insert(0, ".")

from src.lib.skill_paths import get_own_data_dir


def _load_context(raw: str | None) -> dict[str, Any]:
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
    env = os.environ.get("CHAIN_CONTEXT")
    if env:
        try:
            return json.loads(env)
        except json.JSONDecodeError:
            return {}
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Simplify code")
    parser.add_argument("--context", help="Optional JSON context", default=None)
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    context = _load_context(args.context)
    suggestions = [
        "Remove unused imports",
        "Extract repeated logic into helpers",
        "Add small docstrings where missing",
    ]

    result = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "suggestions": suggestions,
        "context_present": bool(context),
    }

    data_dir = get_own_data_dir(__file__)
    output_path = data_dir / "reviews" / f"simplify_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(output_path)

    if args.json:
        sys.stdout.write(f"{json.dumps(result, indent=2)}\n")
    else:
        sys.stdout.write("Simplification suggestions recorded\n")
        for item in suggestions:
            sys.stdout.write(f"- {item}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

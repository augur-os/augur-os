#!/usr/bin/env python3
"""
DevOps Health Check
Runs a lightweight environment sanity check.
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
from datetime import datetime

from src.config.paths import get_project_root


import sys


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run health check")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    repo_root = get_project_root()
    checks = {
        "repo_root": repo_root.exists(),
        "dashboard": (repo_root / "apps" / "dashboard").exists(),
        "plugins": (repo_root / "plugins").exists(),
    }

    result = {
        "status": "ok" if all(checks.values()) else "warning",
        "timestamp": datetime.now().isoformat(),
        "checks": checks,
    }

    if args.json:
        _out(json.dumps(result, indent=2))
    else:
        _out("Health check")
        for key, value in checks.items():
            status = "pass" if value else "fail"
            _out(f"- {key}: {status}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

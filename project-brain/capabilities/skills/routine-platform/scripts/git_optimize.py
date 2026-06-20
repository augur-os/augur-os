#!/usr/bin/env python3
"""
Git Optimize Script
Runs aggressive git garbage collection to reduce repo size.
"""


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
import os
import argparse
from pathlib import Path
from subprocess import CalledProcessError, run as subprocess_run  # nosec B404
from src.config.paths import get_project_root


import sys


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def run_git_gc(repo_path: Path, dry_run: bool = False):
    """Run git gc --aggressive on the repo."""
    if not (repo_path / ".git").exists():
        _out(f"⚠️  Not a git repository: {repo_path}")
        return

    _out(f"🔧 Optimizing Git Repo: {repo_path}")

    if dry_run:
        _out("  [DRY RUN] Would run: git gc --aggressive --prune=now")
        return

    try:
        # Aggressive GC
        cmd = ["git", "gc", "--aggressive", "--prune=now"]
        _out(f"  Running: {' '.join(cmd)} (this may take a while)...")

        start_size = get_dir_size(repo_path / ".git")

        subprocess_run(  # nosec B603
            cmd,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True,
        )

        end_size = get_dir_size(repo_path / ".git")
        saved_mb = start_size - end_size

        _out("  ✅ Git GC Complete.")
        _out(f"     Size reduced by: {saved_mb:.2f} MB")

    except CalledProcessError as e:
        _out(f"  ❌ Git GC Failed: {e.stderr}")
    except Exception as e:
        _out(f"  ❌ Error: {e}")


def get_dir_size(path: Path) -> float:
    """Return directory size in MB."""
    total_size = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size / (1024 * 1024)


def main():
    parser = argparse.ArgumentParser(description="Optimize Git Repository.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate optimization")
    # Allow arbitrary args to be ignored (orchestrator compatibility)
    args, _ = parser.parse_known_args()

    # Project Root
    project_root = Path(os.getcwd())
    data_dir = os.environ.get("AUGUR_ROOT", str(get_project_root()))
    data_path = Path(data_dir)

    run_git_gc(project_root, args.dry_run)
    run_git_gc(data_path, args.dry_run)


if __name__ == "__main__":
    main()

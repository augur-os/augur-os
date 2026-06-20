"""Lightweight shared log archival helper for daemon and loop tasks."""
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
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from src.config.paths import get_archives_dir


def archive_logs(log_file: Path) -> None:
    """Compress and archive logs, then truncate the original file."""
    if not log_file.exists():
        return

    archive_dir = get_archives_dir() / "logs"
    archive_dir.mkdir(parents=True, exist_ok=True)

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    archive_name = f"llm_logs_{yesterday}.jsonl.gz"
    if (archive_dir / archive_name).exists():
        timestamp = datetime.now().strftime("%H%M%S")
        archive_name = f"llm_logs_{yesterday}_{timestamp}.jsonl.gz"

    archive_path = archive_dir / archive_name

    with open(log_file, "rb") as f_in:
        with gzip.open(archive_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    log_file.write_text("", encoding="utf-8")

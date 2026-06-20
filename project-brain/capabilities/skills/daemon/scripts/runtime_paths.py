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
import shutil
from pathlib import Path

from src.config.paths import get_runtime_dir
from src.lib.skill_paths import get_own_data_dir


DAEMON_DATA_DIR = get_own_data_dir(__file__)
DAEMON_RUNTIME_DIR = get_runtime_dir() / "daemon"
NOTIFICATIONS_DATA_DIR = DAEMON_DATA_DIR / "notifications"
NOTIFICATIONS_RUNTIME_DIR = DAEMON_RUNTIME_DIR / "notifications"
INSIGHTS_DATA_DIR = DAEMON_DATA_DIR / "insights"
INSIGHTS_RUNTIME_DIR = DAEMON_RUNTIME_DIR / "insights"


def _ensure_runtime_state(runtime_path: Path, legacy_path: Path, default_content: str | None = None) -> Path:
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    if runtime_path.exists():
        return runtime_path

    if legacy_path.exists():
        shutil.copy2(legacy_path, runtime_path)
        return runtime_path

    if default_content is not None:
        runtime_path.write_text(default_content, encoding="utf-8")

    return runtime_path


def get_notification_config_path() -> Path:
    return NOTIFICATIONS_DATA_DIR / "config.yaml"


def get_notification_preferences_path() -> Path:
    return NOTIFICATIONS_DATA_DIR / "preferences.yaml"


def get_notification_history_path() -> Path:
    return _ensure_runtime_state(
        NOTIFICATIONS_RUNTIME_DIR / "history.yaml",
        NOTIFICATIONS_DATA_DIR / "history.yaml",
        "history: []\n",
    )


def get_notification_pending_path() -> Path:
    return _ensure_runtime_state(
        NOTIFICATIONS_RUNTIME_DIR / "pending.yaml",
        NOTIFICATIONS_DATA_DIR / "pending.yaml",
        "pending: []\n",
    )


def get_notifications_runtime_dir() -> Path:
    NOTIFICATIONS_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return NOTIFICATIONS_RUNTIME_DIR


def get_insights_config_path() -> Path:
    return INSIGHTS_DATA_DIR / "config.yaml"


def get_insights_path() -> Path:
    return _ensure_runtime_state(
        INSIGHTS_RUNTIME_DIR / "insights.yaml",
        INSIGHTS_DATA_DIR / "insights.yaml",
        "insights: []\nlast_updated: null\n",
    )


def get_insights_archive_dir() -> Path:
    archive_dir = INSIGHTS_RUNTIME_DIR / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir

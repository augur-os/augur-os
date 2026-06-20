#!/usr/bin/env python3
"""
Daemon Mode Detection and Configuration.

Provides mode-aware behavior for production vs dev environments.
Production mode: auto-fix issues silently
Dev mode: notify only, preserve debugging context

Usage:
    from daemon_mode import get_daemon_mode, is_production_mode

    if is_production_mode():
        # Auto-fix the issue
        restart_service()
    else:
        # Just notify
        notify("Service is down")
"""

from __future__ import annotations

import os
import sys
import warnings
from typing import Literal


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Setup project root
from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_config_dir
from src.config.system_config import settings_config_raw
from src.config.schemas.settings_schema import validate_settings_config

DaemonMode = Literal["production", "dev"]


def get_daemon_mode() -> DaemonMode:
    """
    Detect current daemon mode from environment or settings.

    Priority:
    1. AUGUR_MODE env var (explicit override)
    2. config/system/settings.yaml → mode field
    3. Default: "production"

    Returns:
        "production" or "dev"
    """
    # 1. Check env var first
    env_mode = os.environ.get("AUGUR_MODE", "").lower()
    if env_mode in ("production", "prod"):
        return "production"
    if env_mode in ("dev", "development"):
        return "dev"

    # 2. Check settings file
    settings_file = get_config_dir() / "system" / "settings.yaml"
    if settings_file.exists():
        try:
            settings = validate_settings_config(settings_config_raw(settings_file))
            return settings.mode  # type: ignore[return-value]
        except Exception as e:
            warnings.warn(
                f"Failed to parse daemon mode settings from {settings_file}: {e}",
                RuntimeWarning,
                stacklevel=2,
            )

    # 3. Default to production
    return "production"


def is_production_mode() -> bool:
    """Check if daemon is running in production mode."""
    return get_daemon_mode() == "production"


def is_dev_mode() -> bool:
    """Check if daemon is running in dev mode."""
    return get_daemon_mode() == "dev"


def set_daemon_mode(mode: DaemonMode) -> None:
    """
    Set daemon mode in settings file.

    Args:
        mode: "production" or "dev"
    """
    settings_file = get_config_dir() / "system" / "settings.yaml"
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    settings: dict = {}
    if settings_file.exists():
        try:
            settings = settings_config_raw(settings_file)
        except Exception as e:
            warnings.warn(
                f"Failed to load existing daemon settings from {settings_file}: {e}",
                RuntimeWarning,
                stacklevel=2,
            )

    settings["mode"] = mode
    validate_settings_config(settings)
    import yaml

    settings_file.write_text(yaml.safe_dump(settings, default_flow_style=False), encoding="utf-8")


def is_worktree_context() -> bool:
    """Check if the current process is running in a git worktree."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        current = result.stdout.strip()

        list_result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
        )
        lines = list_result.stdout.strip().split("\n")
        if lines and lines[0].startswith("worktree "):
            main_repo = lines[0].split("worktree ", 1)[1]
            return current != main_repo
    except Exception:
        pass
    return False


def get_daemon_behavior() -> dict:
    """
    Get daemon behavior based on mode and worktree context.

    Returns:
        dict with keys: monitor_dashboard, auto_restart, notify_only, skip_monitoring
    """
    mode = get_daemon_mode()
    in_worktree = is_worktree_context()

    if in_worktree:
        return {
            "monitor_dashboard": False,
            "auto_restart": False,
            "notify_only": True,
            "skip_monitoring": True,
        }

    if mode == "production":
        return {
            "monitor_dashboard": True,
            "auto_restart": True,
            "notify_only": False,
            "skip_monitoring": False,
        }
    else:
        return {
            "monitor_dashboard": True,
            "auto_restart": False,
            "notify_only": True,
            "skip_monitoring": False,
        }


if __name__ == "__main__":
    _out(f"Current daemon mode: {get_daemon_mode()}")
    _out(f"Is production: {is_production_mode()}")
    _out(f"Is dev: {is_dev_mode()}")

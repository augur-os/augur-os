"""Augur-internal scheduled execution loader."""

from __future__ import annotations

from typing import Any

import yaml
from src.config.paths import get_project_brain_skills_dir, get_project_root


def load_augur_internal_schedules() -> list[dict[str, Any]]:
    """Return daemon-owned loop commands as internal schedule records."""

    project_root = get_project_root()
    config_path = get_project_brain_skills_dir(project_root) / "daemon" / "config.yaml"
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except OSError:
        return []

    commands = (payload.get("contributions") or {}).get("commands") or []
    rows: list[dict[str, Any]] = []
    for command in commands:
        if not isinstance(command, dict):
            continue
        loop_cfg = command.get("loop") or {}
        if not isinstance(loop_cfg, dict):
            continue
        if loop_cfg.get("scheduler", "daemon") != "daemon":
            continue
        trigger = str(loop_cfg.get("trigger", "")).strip()
        if not trigger:
            continue

        command_id = str(command.get("id", "")).strip()
        if not command_id:
            continue
        loop_name = str(loop_cfg.get("name") or command_id)
        rows.append(
            {
                "id": f"augur-internal:{command_id}",
                "title": command_id.replace("-", " ").title(),
                "source": "augur-internal",
                "kind": "internal-schedule",
                "status": "active",
                "workspace": str(project_root),
                "schedule_human": trigger,
                "raw_schedule": {"type": "trigger", "value": trigger},
                "prompt_summary": str(command.get("description", "")),
                "prompt_body": f"/a-loops run {loop_name}",
                "native_id": command_id,
                "source_path": str(config_path),
                "model": "",
                "last_run_at": None,
                "next_run_at": None,
                "managed_by": "augur",
                "drift_status": "in-sync",
                "warnings": [],
            }
        )

    return rows

"""Codex-native scheduled execution loader."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tomllib


def _normalize_timestamp(value: Any) -> str | None:
    """Normalize Codex runtime timestamps to ISO-8601 strings."""

    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        # Current Codex runtime schema stores unix milliseconds.
        seconds = float(value) / 1000 if value > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    return str(value)


def _load_runtime_state(db_path: Path) -> dict[str, dict[str, str | None]]:
    """Load per-automation runtime state from the Codex sqlite database."""

    if not db_path.is_file():
        return {}

    connection = sqlite3.connect(db_path)
    try:
        columns = {str(row[1]) for row in connection.execute("pragma table_info(automations)").fetchall()}
        id_column = "automation_id" if "automation_id" in columns else "id" if "id" in columns else ""
        if not id_column:
            return {}

        # Use literal queries per known column names to avoid dynamic SQL construction.
        if id_column == "automation_id":
            _select_q = "select automation_id, status, last_run_at, next_run_at from automations"
        else:
            _select_q = "select id, status, last_run_at, next_run_at from automations"
        rows = connection.execute(_select_q).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        connection.close()

    return {
        str(automation_id): {
            "status": status,
            "last_run_at": _normalize_timestamp(last_run_at),
            "next_run_at": _normalize_timestamp(next_run_at),
        }
        for automation_id, status, last_run_at, next_run_at in rows
    }


def _load_desired_seeds() -> list[dict[str, Any]]:
    """Load every per-skill routine-schedule.yaml seed Augur knows about."""
    try:
        from src.config.paths import (
            get_managed_skill_source_dirs,
            get_project_brain_skills_dir,
            get_project_root,
        )
        from src.lib.runtime.codex_automations import load_codex_schedule_seed
    except Exception:
        return []

    project_root = get_project_root()
    try:
        skill_roots = [Path(r) for r in get_managed_skill_source_dirs()]
    except Exception:
        skill_roots = []
    project_skills = get_project_brain_skills_dir(project_root)
    if project_skills.is_dir() and project_skills not in skill_roots:
        skill_roots.append(project_skills)

    seeds: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for root in skill_roots:
        if not root.is_dir():
            continue
        for seed_path in root.glob("*/assets/seeds/routine-schedule.yaml"):
            try:
                rows = load_codex_schedule_seed(seed_path, project_root=project_root)
            except Exception:
                continue
            for row in rows:
                schedule_id = str(row.get("id", ""))
                if not schedule_id or schedule_id in seen_ids:
                    continue
                seen_ids.add(schedule_id)
                seeds.append(row)
    return seeds


def load_codex_schedules() -> list[dict[str, Any]]:
    """Return normalized Codex automation records."""

    home = Path.home()
    runtime_state = _load_runtime_state(home / ".codex" / "sqlite" / "codex-dev.db")
    desired_seeds = _load_desired_seeds()

    try:
        from src.lib.runtime.codex_automations import read_automation_drift_status
    except Exception:
        read_automation_drift_status = None  # type: ignore[assignment]

    records: list[dict[str, Any]] = []
    for toml_path in sorted((home / ".codex" / "automations").glob("*/automation.toml")):
        try:
            data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        native_id = toml_path.parent.name
        state = runtime_state.get(native_id, {})
        prompt = str(data.get("prompt", ""))
        rrule = str(data.get("rrule", ""))
        cwds = data.get("cwds") or [""]
        workspace = str(cwds[0]) if cwds else ""
        status = state.get("status")
        if not status:
            status = str(data.get("status", "unknown"))
        execution_environment = str(data.get("execution_environment", "unknown")).lower()
        warnings: list[str] = []
        if execution_environment != "local":
            warnings.append("Codex schedule is not local; cutover is blocked until execution_environment = local.")
        if read_automation_drift_status is not None:
            managed_by, drift_status = read_automation_drift_status(toml_path, desired_schedules=desired_seeds)
        else:
            managed_by, drift_status = ("unknown", "unknown")
        records.append(
            {
                "id": f"codex:{native_id}",
                "title": str(data.get("name", native_id)),
                "source": "codex",
                "kind": "native-schedule",
                "status": str(status).lower(),
                "workspace": workspace,
                "execution_environment": execution_environment,
                "schedule_human": rrule,
                "raw_schedule": {"type": "rrule", "value": rrule},
                "prompt_summary": prompt,
                "prompt_body": prompt,
                "native_id": native_id,
                "source_path": str(toml_path),
                "model": str(data.get("model", "")),
                "last_run_at": state.get("last_run_at"),
                "next_run_at": state.get("next_run_at"),
                "managed_by": managed_by,
                "drift_status": drift_status,
                "warnings": warnings,
            }
        )

    return records

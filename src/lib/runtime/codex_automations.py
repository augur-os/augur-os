"""Sync the Codex migration inventory into local automation.toml files."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml

from src.config.paths import get_project_brain_skills_dir, get_project_root
from src.logging import get_entity_logger

logger = get_entity_logger("lib.runtime.codex_automations")

_WEEKDAY_INDEX = {
    "MO": 0,
    "TU": 1,
    "WE": 2,
    "TH": 3,
    "FR": 4,
    "SA": 5,
    "SU": 6,
}


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value type: {type(value).__name__}")


def compute_seed_hash(schedule: dict[str, Any]) -> str:
    """Deterministic hash over the fields that define a schedule's intent.

    Excludes created_at/updated_at and per-run metadata — only the declarative
    seed payload contributes. Used for drift detection: a tagged automation
    whose embedded seed_hash no longer matches the current seed hash has been
    edited manually since Augur wrote it.
    """
    digest_input = json.dumps(
        {
            "id": str(schedule["id"]),
            "prompt": str(schedule["prompt"]),
            "rrule": str(schedule["rrule"]),
            "model": str(schedule["model"]),
            "reasoning_effort": str(schedule["reasoning_effort"]),
            "workspace": str(schedule["workspace"]),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()[:16]


def _render_automation_toml(
    schedule: dict[str, Any],
    *,
    created_at: int,
    updated_at: int,
) -> str:
    name = str(schedule.get("title") or schedule.get("browse_title") or schedule["id"])
    runs_in = str(schedule.get("runs_in", ""))
    if runs_in != "local":
        raise ValueError(f"Schedule {schedule['id']} must run locally, got {runs_in!r}")

    payload = [
        ("version", 1),
        ("id", str(schedule["id"])),
        ("kind", "cron"),
        ("name", name),
        ("prompt", str(schedule["prompt"])),
        ("status", "ACTIVE"),
        ("rrule", str(schedule["rrule"])),
        ("model", str(schedule["model"])),
        ("reasoning_effort", str(schedule["reasoning_effort"])),
        ("execution_environment", "local"),
        ("managed_by", "augur"),
        ("augur_seed_hash", compute_seed_hash(schedule)),
        ("cwds", [str(schedule["workspace"])]),
        ("created_at", created_at),
        ("updated_at", updated_at),
    ]
    return "\n".join(f"{key} = {_toml_value(value)}" for key, value in payload) + "\n"


def _toml_fields_to_schedule_shape(data: dict[str, Any]) -> dict[str, Any]:
    """Project an installed automation.toml back into a hashable schedule dict.

    Uses the SAME field set as compute_seed_hash so that the hash recomputed
    from a TOML on disk can be directly compared against the embedded
    augur_seed_hash. Any user edit to one of these fields will change the
    recomputed hash → mismatch → drift detected.
    """
    cwds = data.get("cwds") or [""]
    workspace = str(cwds[0]) if isinstance(cwds, list) and cwds else ""
    return {
        "id": str(data.get("id", "")),
        "prompt": str(data.get("prompt", "")),
        "rrule": str(data.get("rrule", "")),
        "model": str(data.get("model", "")),
        "reasoning_effort": str(data.get("reasoning_effort", "")),
        "workspace": workspace,
    }


def read_automation_drift_status(
    automation_toml: Path,
    *,
    desired_schedules: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    """Classify an installed automation by ownership and drift.

    Returns (managed_by, drift_status). drift_status values:
      - "in-sync"       — augur-managed, file fields match embedded hash AND
                          embedded hash matches the current desired seed hash
      - "codex-edited"  — augur-managed, file fields no longer match the
                          embedded augur_seed_hash (user edited the TOML)
      - "seed-evolved"  — augur-managed, file matches its embedded hash but
                          the desired seed has changed since (Augur's intent
                          has moved on; sync would update the file)
      - "augur-managed-but-removed" — augur-managed, no longer in desired set
      - "external"      — not augur-managed; user-created in Codex directly
      - "unknown"       — could not parse TOML
    """
    try:
        data = tomllib.loads(automation_toml.read_text(encoding="utf-8"))
    except Exception:
        return ("unknown", "unknown")
    if not isinstance(data, dict):
        return ("unknown", "unknown")
    if str(data.get("managed_by", "")) != "augur":
        return ("manual", "external")

    embedded_hash = str(data.get("augur_seed_hash", ""))
    file_hash = compute_seed_hash(_toml_fields_to_schedule_shape(data))

    if embedded_hash and embedded_hash != file_hash:
        return ("augur", "codex-edited")

    if desired_schedules is None:
        return ("augur", "in-sync")

    automation_id = str(data.get("id", ""))
    desired_by_id = {str(s["id"]): s for s in desired_schedules}
    desired = desired_by_id.get(automation_id)
    if desired is None:
        return ("augur", "augur-managed-but-removed")

    if embedded_hash and embedded_hash != compute_seed_hash(desired):
        return ("augur", "seed-evolved")
    return ("augur", "in-sync")


def _resolve_workspace(value: Any, *, project_root: Path) -> str:
    raw = str(value or "").strip()
    if raw in {"", ".", "__PROJECT_ROOT__"}:
        return str(project_root)
    workspace = Path(raw).expanduser()
    if not workspace.is_absolute():
        workspace = (project_root / workspace).resolve()
    return str(workspace)


def _normalize_schedule_row(
    row: Any,
    *,
    path: Path,
    index: int,
    project_root: Path,
) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError(f"Invalid schedule entry at {path}:{index + 1}: expected mapping, got {type(row).__name__}")
    required = {"id", "rrule", "prompt", "model", "reasoning_effort", "runs_in"}
    missing = sorted(key for key in required if not row.get(key))
    if missing:
        raise ValueError(
            f"Invalid schedule entry '{row.get('id', f'#{index + 1}')}' in {path}: missing {', '.join(missing)}"
        )

    normalized = dict(row)
    normalized["workspace"] = _resolve_workspace(
        normalized.get("workspace"),
        project_root=project_root,
    )
    return normalized


def load_codex_schedule_seed(
    seed_path: Path | None = None,
    *,
    project_root: Path | None = None,
) -> list[dict[str, Any]]:
    if seed_path is None:
        raise ValueError(
            "seed_path is required; ADR-758 moved Codex automation seeds to "
            "skill-local assets/seeds/routine-schedule.yaml files"
        )
    path = seed_path
    root = project_root or get_project_root()
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    schedules = payload.get("schedules", [])
    if not isinstance(schedules, list):
        raise ValueError(f"Expected a schedules list in {path}")
    return [
        _normalize_schedule_row(row, path=path, index=index, project_root=root) for index, row in enumerate(schedules)
    ]


def discover_codex_schedule_seeds(*, project_root: Path | None = None) -> list[Path]:
    """Return every skill-local ADR-758 routine schedule seed."""
    root = project_root or get_project_root()
    candidates: list[Path] = []
    try:
        from src.config.paths import get_managed_skill_source_dirs

        candidates.extend(Path(path) for path in get_managed_skill_source_dirs())
    except Exception:
        pass
    candidates.append(get_project_brain_skills_dir(root))

    seeds: list[Path] = []
    seen: set[Path] = set()
    for skills_root in candidates:
        if not skills_root.is_dir():
            continue
        for seed in sorted(skills_root.glob("*/assets/seeds/routine-schedule.yaml")):
            resolved = seed.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            seeds.append(seed)
    return seeds


def load_codex_schedule_seeds(
    seed_paths: list[Path] | tuple[Path, ...],
    *,
    project_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Load and normalize multiple skill-local Codex schedule seeds."""
    schedules: list[dict[str, Any]] = []
    for seed_path in seed_paths:
        schedules.extend(load_codex_schedule_seed(seed_path, project_root=project_root))
    return schedules


def _is_augur_managed_automation(automation_toml: Path) -> bool:
    try:
        data = tomllib.loads(automation_toml.read_text(encoding="utf-8"))
    except Exception:
        return False
    return isinstance(data, dict) and str(data.get("managed_by", "")) == "augur"


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _parse_rrule_parts(rrule_value: str) -> dict[str, str]:
    raw = str(rrule_value).removeprefix("RRULE:")
    parts: dict[str, str] = {}
    for item in raw.split(";"):
        if not item:
            continue
        key, sep, value = item.partition("=")
        if sep:
            parts[key.upper()] = value
    return parts


def _rrule_int(parts: dict[str, str], key: str, default: int) -> int:
    value = parts.get(key)
    if value in {None, ""}:
        return default
    return int(value)


def _fallback_next_run_at_ms(rrule_value: str) -> int | None:
    parts = _parse_rrule_parts(rrule_value)
    freq = parts.get("FREQ", "").upper()
    interval = _rrule_int(parts, "INTERVAL", 1)
    local_tz = datetime.now().astimezone().tzinfo or timezone.utc
    now_local = datetime.now(local_tz)

    if freq == "MINUTELY":
        candidate = now_local.replace(second=0, microsecond=0)
        while candidate <= now_local:
            candidate += timedelta(minutes=interval)
        return int(candidate.astimezone(timezone.utc).timestamp() * 1000)

    if freq == "HOURLY":
        minute = _rrule_int(parts, "BYMINUTE", now_local.minute)
        candidate = now_local.replace(minute=minute, second=0, microsecond=0)
        while candidate <= now_local:
            candidate += timedelta(hours=interval)
        return int(candidate.astimezone(timezone.utc).timestamp() * 1000)

    if freq == "DAILY":
        hour = _rrule_int(parts, "BYHOUR", now_local.hour)
        minute = _rrule_int(parts, "BYMINUTE", now_local.minute)
        candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        while candidate <= now_local:
            candidate += timedelta(days=interval)
        return int(candidate.astimezone(timezone.utc).timestamp() * 1000)

    if freq == "WEEKLY":
        hour = _rrule_int(parts, "BYHOUR", now_local.hour)
        minute = _rrule_int(parts, "BYMINUTE", now_local.minute)
        byday = parts.get("BYDAY") or list(_WEEKDAY_INDEX)[now_local.weekday()]
        weekdays = [_WEEKDAY_INDEX[day.strip().upper()] for day in byday.split(",") if day.strip()]
        candidates = []
        for days_ahead in range(0, 7 * max(interval, 1) + 7):
            day = now_local + timedelta(days=days_ahead)
            if day.weekday() not in weekdays:
                continue
            candidate = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate > now_local:
                candidates.append(candidate)
        if not candidates:
            return None
        return int(min(candidates).astimezone(timezone.utc).timestamp() * 1000)

    raise ValueError(f"Unsupported RRULE frequency without python-dateutil: {freq or '<missing>'}")


def _compute_next_run_at_ms(rrule_value: str) -> int | None:
    local_tz = datetime.now().astimezone().tzinfo or timezone.utc
    now_local = datetime.now(local_tz)
    try:
        from dateutil.rrule import rrulestr
    except ModuleNotFoundError:
        return _fallback_next_run_at_ms(rrule_value)

    rule = rrulestr(str(rrule_value).removeprefix("RRULE:"), dtstart=now_local.replace(second=0, microsecond=0))
    next_local = rule.after(now_local, inc=False)
    if next_local is None:
        return None
    return int(next_local.astimezone(timezone.utc).timestamp() * 1000)


def _connect_automation_db(codex_home: Path) -> sqlite3.Connection:
    sqlite_dir = codex_home / ".codex" / "sqlite"
    sqlite_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(sqlite_dir / "codex-dev.db")
    connection.execute("""
        create table if not exists automations (
            id text primary key,
            name text not null,
            prompt text not null,
            status text not null default 'ACTIVE',
            next_run_at integer,
            last_run_at integer,
            cwds text not null default '[]',
            rrule text not null default 'FREQ=HOURLY;INTERVAL=24;BYMINUTE=0',
            created_at integer not null,
            updated_at integer not null,
            model text,
            reasoning_effort text
        )
        """)
    return connection


def _load_existing_automation_metadata(
    connection: sqlite3.Connection,
    automation_id: str,
) -> tuple[int | None, int | None, str]:
    row = connection.execute(
        "select created_at, last_run_at, status from automations where id = ?",
        (automation_id,),
    ).fetchone()
    if not row:
        return None, None, "ACTIVE"
    created_at, last_run_at, status = row
    return (
        int(created_at) if created_at is not None else None,
        int(last_run_at) if last_run_at is not None else None,
        str(status or "ACTIVE"),
    )


def _upsert_automation_row(
    connection: sqlite3.Connection,
    schedule: dict[str, Any],
    *,
    created_at: int,
    updated_at: int,
    last_run_at: int | None,
    status: str,
) -> None:
    connection.execute(
        """
        insert into automations (
            id, name, prompt, status, next_run_at, last_run_at, cwds, rrule,
            created_at, updated_at, model, reasoning_effort
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(id) do update set
            name = excluded.name,
            prompt = excluded.prompt,
            status = excluded.status,
            next_run_at = excluded.next_run_at,
            last_run_at = coalesce(automations.last_run_at, excluded.last_run_at),
            cwds = excluded.cwds,
            rrule = excluded.rrule,
            created_at = automations.created_at,
            updated_at = excluded.updated_at,
            model = excluded.model,
            reasoning_effort = excluded.reasoning_effort
        """,
        (
            str(schedule["id"]),
            str(schedule.get("title") or schedule.get("browse_title") or schedule["id"]),
            str(schedule["prompt"]),
            status,
            _compute_next_run_at_ms(str(schedule["rrule"])),
            last_run_at,
            json.dumps([str(schedule["workspace"])]),
            str(schedule["rrule"]),
            created_at,
            updated_at,
            str(schedule["model"]),
            str(schedule["reasoning_effort"]),
        ),
    )


def sync_codex_automations(
    schedules: list[dict[str, Any]],
    *,
    apply: bool,
    home: Path | None = None,
    prune: bool = True,
    force: bool = False,
) -> list[Path]:
    """Write Codex automation.toml files for the provided schedules.

    Default behavior is non-destructive:
      - Untagged entries (managed_by != "augur") are always skipped — they are
        manual user creations that Augur must not touch.
      - Tagged entries whose embedded augur_seed_hash no longer matches the
        current desired seed (the user manually edited the TOML) are skipped
        with a warning, unless force=True.
    """
    codex_home = home or Path.home()
    automations_root = codex_home / ".codex" / "automations"
    written: list[Path] = []
    skipped_drift: list[str] = []
    desired_ids = {str(schedule["id"]) for schedule in schedules}
    connection = _connect_automation_db(codex_home) if apply else None

    try:
        for schedule in schedules:
            automation_dir = automations_root / str(schedule["id"])
            automation_toml = automation_dir / "automation.toml"

            if apply and not force and automation_toml.is_file():
                managed_by, drift_status = read_automation_drift_status(
                    automation_toml,
                    desired_schedules=schedules,
                )
                if managed_by == "manual":
                    logger.warning(
                        "[codex-sync] skip %s: managed by user (no augur marker); not overwriting",
                        schedule["id"],
                    )
                    skipped_drift.append(str(schedule["id"]))
                    continue
                if drift_status == "codex-edited":
                    logger.warning(
                        "[codex-sync] skip %s: drift detected (seed_hash mismatch); "
                        "preserve user edit. Re-run with force=True to overwrite.",
                        schedule["id"],
                    )
                    skipped_drift.append(str(schedule["id"]))
                    continue

            written.append(automation_toml)
            if not apply:
                continue

            assert connection is not None
            existing_created_at, last_run_at, status = _load_existing_automation_metadata(
                connection,
                str(schedule["id"]),
            )
            now_ms = _now_ms()
            created_at = existing_created_at or now_ms

            automation_dir.mkdir(parents=True, exist_ok=True)
            automation_toml.write_text(
                _render_automation_toml(
                    schedule,
                    created_at=created_at,
                    updated_at=now_ms,
                ),
                encoding="utf-8",
            )
            _upsert_automation_row(
                connection,
                schedule,
                created_at=created_at,
                updated_at=now_ms,
                last_run_at=last_run_at,
                status=status,
            )

        if apply and prune and automations_root.exists():
            for automation_toml in automations_root.glob("*/automation.toml"):
                automation_id = automation_toml.parent.name
                if automation_id in desired_ids:
                    continue
                if not _is_augur_managed_automation(automation_toml):
                    continue
                shutil.rmtree(automation_toml.parent)
                assert connection is not None
                connection.execute("delete from automations where id = ?", (automation_id,))

        if connection is not None:
            connection.commit()
    finally:
        if connection is not None:
            connection.close()

    return written


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed",
        type=Path,
        default=None,
        help=(
            "Path to one skill-local routine-schedule.yaml. Defaults to all "
            "discovered skill-local routine schedules."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List target files without writing them",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    project_root = get_project_root()
    schedules = (
        load_codex_schedule_seed(args.seed, project_root=project_root)
        if args.seed
        else load_codex_schedule_seeds(
            discover_codex_schedule_seeds(project_root=project_root),
            project_root=project_root,
        )
    )
    written = sync_codex_automations(schedules, apply=not args.dry_run)
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

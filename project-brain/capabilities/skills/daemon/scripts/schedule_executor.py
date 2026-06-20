#!/usr/bin/env python3
"""
Schedule Executor (ADR-130, ADR-807 Fork 4).

Discovers scheduled actions, executes due ones, and logs results.

A scheduled action is an action in ``{skill}/augur/actions.yaml`` that carries a
``schedule:`` cadence block. The DEFINITION (cadence + what to run) lives in the
version-controlled action file; the COMPUTED runtime state
(``next_run``/``last_run``/``run_count``/``last_result``) lives in
``state/schedules/{skill}__{action_id}.yaml`` and is NEVER written back into
``augur/actions.yaml``.

Discovery scans every enabled skill's ``augur/actions.yaml`` via
``src.lib.actions.action_schema.load_actions_yaml`` and keeps actions whose
``schedule`` block is truthy (the schema already enforces such actions are
``dispatch: fire`` + ``kind: mcp`` + ``mcp_tool``).

Execution: POST /api/mcp/tool with ``{tool: action.mcp_tool, args: {...}}`` for
fire actions. A scheduled action without an ``mcp_tool`` is logged and skipped
(no generic action-runner fallback).
Logging: Append JSON lines to the configured logs directory as schedules.jsonl.

Usage:
    python3 schedule_executor.py          # Run one tick and exit
    python3 schedule_executor.py --loop   # Continuous 60s loop (used by unified daemon)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

# ─── project root & sys.path ──────────────────────────────────────────────────
try:
    from bootstrap_paths import ensure_project_paths
except ImportError:
    _SCRIPTS_DIR = Path(__file__).resolve().parent
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    from bootstrap_paths import ensure_project_paths

PROJECT_ROOT = ensure_project_paths(__file__)
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from src.config.paths import (
        get_logs_dir,
        get_project_port,
        get_project_root,
        get_runtime_dir,
        get_managed_skill_source_dirs,
    )
    from src.plugins.skill_ui_state import is_skill_enabled
    from src.logging import get_entity_logger
except ImportError:
    import logging as _stdlib_logging

    def get_project_root() -> Path:  # type: ignore[misc]
        return PROJECT_ROOT

    def get_runtime_dir() -> Path:  # type: ignore[misc]
        runtime_dir = os.environ.get("AUGUR_STATE") or os.environ.get("AUGUR_RUNTIME")
        if runtime_dir:
            return Path(runtime_dir)
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "Augur" / "state"
        return Path.home() / ".local" / "state" / "augur"

    def get_logs_dir() -> Path:  # type: ignore[misc]
        return get_runtime_dir() / "logs"

    def get_managed_skill_source_dirs(project_root: Path | None = None) -> list[Path]:  # type: ignore[misc]
        root = project_root or get_project_root()
        candidates = [
            root / "project-brain" / "capabilities" / "skills",
        ]
        return [candidate for candidate in candidates if candidate.is_dir()]

    def is_skill_enabled(skill: str, *, runtime_dir: Path | None = None) -> bool:  # type: ignore[misc]
        try:
            config_file = _fallback_skill_root(skill) / ".config"
        except FileNotFoundError:
            return True
        if not config_file.exists():
            return True
        try:
            raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
            return raw.get("enabled", True) is not False
        except Exception:
            return True

    def get_entity_logger(name: str):  # type: ignore[misc]
        _log = _stdlib_logging.getLogger(name)
        if not _log.handlers:
            handler = _stdlib_logging.StreamHandler()
            handler.setFormatter(_stdlib_logging.Formatter("%(asctime)s %(levelname)s - %(message)s"))
            _log.addHandler(handler)
            _log.setLevel(_stdlib_logging.INFO)
        return _log


logger = get_entity_logger("schedule_executor")


@contextmanager
def _job_ledger_run(**kwargs: Any):
    """Best-effort ledger wrapper. A ledger failure never blocks schedules."""
    try:
        from job_ledger.ledger import run as ledger_run
    except Exception as exc:  # noqa: BLE001
        logger.warning("job ledger unavailable: %s", exc)
        yield None
        return
    with ledger_run(**kwargs) as job:
        yield job

# ─── constants ────────────────────────────────────────────────────────────────
POLL_INTERVAL = 60  # seconds between ticks
DASHBOARD_URL = f"http://localhost:{get_project_port()}"
REQUEST_TIMEOUT = 90  # seconds per action execution

SCHEDULES_LOG = get_logs_dir() / "schedules.jsonl"


def _state_schedules_dir() -> Path:
    """Per-action runtime state directory: ``state/schedules/`` (ADR-807 Fork 4)."""
    return get_runtime_dir() / "schedules"


def read_schedule_state(state_path: str | Path) -> dict[str, Any]:
    """Read the per-action runtime state file. Returns {} if missing/unreadable."""
    path = Path(state_path)
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return raw if isinstance(raw, dict) else {}
    except Exception as exc:
        logger.warning("Could not read schedule state %s: %s", path, exc)
        return {}


def write_schedule_state(state_path: str | Path, state: dict[str, Any]) -> None:
    """Atomically write the per-action runtime state file under state/schedules/."""
    path = Path(state_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".yaml.tmp")
        tmp.write_text(
            yaml.dump(state, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        tmp.replace(path)
    except Exception as exc:
        logger.error("Failed to write schedule state %s: %s", path, exc)
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _get_skill_source_dirs() -> list[Path]:
    """Return managed skill source roots in authority order."""
    return [root for root in get_managed_skill_source_dirs(PROJECT_ROOT) if root.is_dir()]


def _iter_skill_dirs() -> list[Path]:
    """Return enabled skill dirs from all managed roots, deduped by authority."""
    result: list[Path] = []
    seen: set[str] = set()
    for skills_dir in _get_skill_source_dirs():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            if skill_dir.name.startswith(".") or skill_dir.name.startswith("__"):
                continue
            if skill_dir.name in seen:
                continue
            seen.add(skill_dir.name)
            result.append(skill_dir)
    return result


def _find_skill_dir(skill_name: str) -> Path | None:
    """Find a skill dir across managed roots in authority order."""
    for skills_dir in _get_skill_source_dirs():
        candidate = skills_dir / skill_name
        if candidate.is_dir():
            return candidate
    return None


def _fallback_skill_root(skill_name: str) -> Path:
    """Resolve a skill root from managed skill source dirs."""
    candidate = _find_skill_dir(skill_name)
    if candidate is None:
        raise FileNotFoundError(f"Skill root not found for {skill_name}")
    return candidate


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULE DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════


def discover_schedules() -> list[dict[str, Any]]:
    """
    Discover scheduled actions across every enabled skill's ``augur/actions.yaml``.

    A scheduled action is an :class:`Action` whose ``schedule`` block is truthy.
    For each one this returns a schedule dict::

        {
          "skill": <skill name>,
          "action_id": <action id>,
          "schedule": <cadence dict>,
          "action": <the Action>,
          "_state_path": "<state/schedules/{skill}__{id}.yaml>",
        }

    Disabled skills are skipped. The DEFINITION lives in the action file; the
    runtime state lives under ``state/schedules/`` keyed by ``{skill}__{id}``.
    """
    from src.lib.actions.action_schema import load_actions_yaml

    schedules: list[dict[str, Any]] = []

    skill_dirs = _iter_skill_dirs()
    if not skill_dirs:
        logger.warning("No managed skill source directories found")
        return schedules

    state_dir = _state_schedules_dir()

    for skill_dir in skill_dirs:
        if not is_skill_enabled(skill_dir.name):
            logger.debug("Skipping disabled skill: %s", skill_dir.name)
            continue

        actions_yaml = skill_dir / "augur" / "actions.yaml"
        if not actions_yaml.exists():
            continue

        try:
            actions = load_actions_yaml(actions_yaml)
        except Exception as exc:
            logger.warning("Failed to load actions for %s: %s", skill_dir.name, exc)
            continue

        for action in actions:
            if not action.schedule:
                continue
            schedules.append(
                {
                    "skill": skill_dir.name,
                    "action_id": action.id,
                    "schedule": action.schedule,
                    "action": action,
                    "_state_path": str(state_dir / f"{skill_dir.name}__{action.id}.yaml"),
                }
            )

    return schedules


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULE TIMING
# ═══════════════════════════════════════════════════════════════════════════════


_DAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def calculate_next_run(schedule_config: dict[str, Any], from_dt: datetime | None = None) -> datetime:
    """
    Calculate the next run datetime from schedule configuration.

    schedule_config keys: frequency, day, time, timezone
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    tz_name = schedule_config.get("timezone", "UTC")
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, Exception):
        logger.warning("Unknown timezone %r, falling back to UTC", tz_name)
        tz = timezone.utc

    now = from_dt or datetime.now(tz=tz)
    frequency = str(schedule_config.get("frequency", "daily")).lower()
    time_str = str(schedule_config.get("time", "09:00"))
    day_str = str(schedule_config.get("day", "monday")).lower()

    # Parse the target time
    try:
        target_hour, target_minute = (int(x) for x in time_str.split(":"))
    except (ValueError, AttributeError):
        target_hour, target_minute = 9, 0

    if frequency == "once":
        # One-off: the `time` field is interpreted as YYYY-MM-DDTHH:MM or HH:MM
        # If it's just HH:MM, use today
        run_dt = datetime(
            now.year, now.month, now.day, target_hour, target_minute, tzinfo=tz
        )
        if run_dt <= now:
            # Already past — push to next day (edge case)
            run_dt += timedelta(days=1)
        return run_dt

    elif frequency == "daily":
        run_dt = datetime(
            now.year, now.month, now.day, target_hour, target_minute, tzinfo=tz
        )
        if run_dt <= now:
            run_dt += timedelta(days=1)
        return run_dt

    elif frequency == "weekly":
        target_weekday = _DAY_MAP.get(day_str, 0)
        run_dt = datetime(
            now.year, now.month, now.day, target_hour, target_minute, tzinfo=tz
        )
        days_ahead = (target_weekday - now.weekday()) % 7
        if days_ahead == 0 and run_dt <= now:
            days_ahead = 7
        run_dt += timedelta(days=days_ahead)
        return run_dt

    elif frequency == "monthly":
        day_of_month = _DAY_MAP.get(day_str, None)
        # If day_str is a weekday name, treat as "day number" (1-28 range)
        # Otherwise try to use it as integer day-of-month
        if day_of_month is None:
            try:
                day_of_month = int(day_str)
            except (ValueError, TypeError):
                day_of_month = 1
        else:
            day_of_month = day_of_month + 1  # 0-indexed weekday → 1-indexed day

        # Clamp to 28 to avoid issues with Feb
        day_of_month = max(1, min(28, day_of_month))

        run_dt = datetime(
            now.year, now.month, day_of_month, target_hour, target_minute, tzinfo=tz
        )
        if run_dt <= now:
            # Next month
            if now.month == 12:
                run_dt = datetime(now.year + 1, 1, day_of_month, target_hour, target_minute, tzinfo=tz)
            else:
                run_dt = datetime(now.year, now.month + 1, day_of_month, target_hour, target_minute, tzinfo=tz)
        return run_dt

    else:
        # Unknown frequency: default to daily
        logger.warning("Unknown schedule frequency %r, defaulting to daily", frequency)
        run_dt = datetime(
            now.year, now.month, now.day, target_hour, target_minute, tzinfo=tz
        ) + timedelta(days=1)
        return run_dt


def is_due(schedule: dict[str, Any]) -> bool:
    """
    Return True if the schedule is enabled and ``next_run`` (read from the per-
    action STATE file) is now or in the past.

    When the state file has no ``next_run`` yet, compute an initial one from the
    cadence via :func:`calculate_next_run`, persist it, and treat the schedule as
    not-yet-due so the first run fires at the scheduled time rather than now.
    """
    if not schedule.get("enabled", True):
        return False

    state_path = schedule.get("_state_path")
    if not state_path:
        return False

    state = read_schedule_state(state_path)
    next_run_str = state.get("next_run")

    if not next_run_str:
        # First sighting: seed next_run from the cadence and persist it.
        schedule_config = schedule.get("schedule") or {}
        try:
            next_run_dt = calculate_next_run(schedule_config)
            state["next_run"] = next_run_dt.isoformat()
            write_schedule_state(state_path, state)
            next_run_str = state["next_run"]
        except Exception as exc:
            logger.warning("Failed to seed next_run for %s: %s", state_path, exc)
            return False

    try:
        next_run = datetime.fromisoformat(str(next_run_str))
        # Make timezone-aware if not already
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=timezone.utc)
        return datetime.now(tz=timezone.utc) >= next_run
    except (ValueError, TypeError) as exc:
        logger.warning("Invalid next_run value %r in state %s: %s", next_run_str, state_path, exc)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# ACTION RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════════


def resolve_action(schedule: dict[str, Any]) -> Any | None:
    """
    Return the :class:`Action` carried by the schedule (ADR-807 Fork 4).

    Discovery already loads the action from ``augur/actions.yaml`` and attaches
    it under the ``action`` key — there is no separate ``actions/{id}.yaml``
    lookup. Logs an orphan guard and returns None if the action is missing.
    """
    action = schedule.get("action")
    if action is None:
        logger.warning(
            "Orphan schedule: action '%s' missing for skill '%s'",
            schedule.get("action_id", ""),
            schedule.get("skill", ""),
        )
        return None
    return action


# ═══════════════════════════════════════════════════════════════════════════════
# ACTION EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════


def _http_post(url: str, payload: dict[str, Any], timeout: int = REQUEST_TIMEOUT) -> dict[str, Any]:
    """Simple HTTP POST using stdlib urllib. Returns parsed JSON response."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(  # nosec B310
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"error": f"HTTP {exc.code}: {body[:200]}"}
    except urllib.error.URLError as exc:
        return {"error": f"URL error: {exc.reason}"}
    except TimeoutError:
        return {"error": f"Request timed out after {timeout}s"}


def _action_attr(action: Any, name: str, default: Any = None) -> Any:
    """Read a field from an Action dataclass or a plain dict uniformly."""
    if isinstance(action, dict):
        return action.get(name, default)
    return getattr(action, name, default)


def execute_action(
    schedule: dict[str, Any],
    action: Any,
) -> dict[str, Any]:
    """
    Execute the scheduled action via the dashboard MCP API (ADR-807 Fork 4).

    fire   → POST /api/mcp/tool with ``{tool: action.mcp_tool, args: {...}}``.
    A ``fire`` action without an ``mcp_tool`` is logged and skipped — there is
    NO generic action-runner fallback. Non-``fire`` dispatches are user-reviewed
    dashboard interactions and are not schedulable.

    Returns a result dict: {status, message, duration_ms}.
    """
    dispatch = str(_action_attr(action, "dispatch", "fire")).lower()
    action_id = _action_attr(action, "id") or schedule.get("action_id", "")

    start_ms = time.monotonic()

    if dispatch != "fire":
        # AI handoffs and modal flows are user-reviewed dashboard interactions.
        logger.warning(
            "Action '%s' has dispatch=%r which is not schedulable. Skipping.",
            action_id,
            dispatch,
        )
        return {
            "status": "skipped",
            "message": f"dispatch={dispatch!r} is not supported for scheduled execution",
            "duration_ms": 0,
        }

    mcp_tool = _action_attr(action, "mcp_tool")
    if not mcp_tool:
        logger.error(
            "Scheduled action '%s' has dispatch=fire but no mcp_tool. Skipping "
            "(generic action-runner fallback removed, ADR-807 Fork 4).",
            action_id,
        )
        return {
            "status": "error",
            "message": "scheduled fire action requires mcp_tool",
            "duration_ms": 0,
        }

    args = _action_attr(action, "args", {})
    if not isinstance(args, dict):
        args = {}

    url = f"{DASHBOARD_URL}/api/mcp/tool"
    payload = {
        "tool": mcp_tool,
        "args": {
            **args,
            "context": {"source": "schedule_executor", "action_id": action_id},
        },
    }

    logger.info("Executing scheduled action '%s' via %s", action_id, url)
    response = _http_post(url, payload)

    duration_ms = int((time.monotonic() - start_ms) * 1000)

    if response.get("success") or (
        "error" not in response and "message" in response
    ):
        msg = response.get("message", "OK")
        return {
            "status": "success",
            "message": str(msg)[:500],
            "duration_ms": duration_ms,
        }
    else:
        error = response.get("error", "Unknown error")
        details = response.get("details", "")
        msg = f"{error}: {details}" if details else str(error)
        return {
            "status": "error",
            "message": str(msg)[:500],
            "duration_ms": duration_ms,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# RUNTIME STATE UPDATE
# ═══════════════════════════════════════════════════════════════════════════════


def update_schedule_file(schedule: dict[str, Any], result: dict[str, Any]) -> None:
    """
    Persist runtime state to the per-action STATE file (``_state_path``), NOT the
    action yaml (ADR-807 Fork 4). Writes:
    - last_run (ISO timestamp)
    - next_run (computed from frequency/day/time/timezone)
    - run_count (incremented)
    - last_result (status, message, duration_ms)

    The DEFINITION in ``augur/actions.yaml`` is never mutated.
    """
    state_path = schedule.get("_state_path")
    if not state_path:
        logger.warning("Schedule has no _state_path; cannot persist runtime state")
        return

    state = read_schedule_state(state_path)

    now = datetime.now(tz=timezone.utc)

    state["last_run"] = now.isoformat()
    state["run_count"] = int(state.get("run_count", 0)) + 1
    state["last_result"] = {
        "status": result["status"],
        "message": result["message"],
        "duration_ms": result["duration_ms"],
    }

    # Calculate next_run from the cadence carried on the schedule dict.
    schedule_config = schedule.get("schedule", {}) or {}
    try:
        next_run_dt = calculate_next_run(schedule_config, from_dt=now)
        state["next_run"] = next_run_dt.isoformat()
    except Exception as exc:
        logger.warning("Failed to calculate next_run for %s: %s", state_path, exc)
        # Leave next_run unchanged to avoid loops

    write_schedule_state(state_path, state)
    logger.debug("Updated schedule state: %s", state_path)


# ═══════════════════════════════════════════════════════════════════════════════
# JSONL LOGGING
# ═══════════════════════════════════════════════════════════════════════════════


def log_execution(
    schedule: dict[str, Any],
    action: Any | None,
    result: dict[str, Any],
) -> None:
    """Append a JSON line to logs/schedules.jsonl."""
    SCHEDULES_LOG.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "action_id": schedule.get("action_id", ""),
        "skill": schedule.get("_skill", "") or schedule.get("skill", ""),
        "frequency": (schedule.get("schedule") or {}).get("frequency", ""),
        "dispatch": _action_attr(action, "dispatch", "") if action is not None else "unknown",
        "status": result["status"],
        "message": result["message"],
        "duration_ms": result["duration_ms"],
    }

    try:
        with SCHEDULES_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as exc:
        logger.warning("Failed to write to schedules.jsonl: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════════
# TICK
# ═══════════════════════════════════════════════════════════════════════════════


def tick() -> int:
    """
    Run one schedule check cycle.
    Returns the number of schedules that were executed.
    """
    schedules = discover_schedules()
    if not schedules:
        logger.debug("No schedules found")
        return 0

    executed = 0
    for schedule in schedules:
        if not is_due(schedule):
            continue

        action_id = schedule.get("action_id", "<unknown>")
        skill = schedule.get("skill", "")

        logger.info(
            "Schedule due: action=%s skill=%s",
            action_id, skill,
        )

        action = resolve_action(schedule)
        if action is None:
            result = {
                "status": "error",
                "message": f"Action '{action_id}' not found for skill {skill}",
                "duration_ms": 0,
            }
        else:
            try:
                with _job_ledger_run(
                    kind="schedule",
                    name=f"{skill}/{action_id}",
                    args={
                        "action_id": action_id,
                        "skill": skill,
                        "dispatch": _action_attr(action, "dispatch"),
                    },
                    timeout_s=REQUEST_TIMEOUT,
                ) as _job:
                    if _job is not None:
                        _job.phase("dispatch")
                    result = execute_action(schedule, action)
            except Exception as exc:
                logger.error("Unexpected error executing action '%s': %s", action_id, exc, exc_info=True)
                result = {
                    "status": "error",
                    "message": f"Unexpected error: {exc}",
                    "duration_ms": 0,
                }

        log_execution(schedule, action, result)
        update_schedule_file(schedule, result)
        executed += 1

        log_level = logger.info if result["status"] == "success" else logger.warning
        log_level(
            "Schedule result: action=%s status=%s message=%s duration_ms=%d",
            action_id,
            result["status"],
            result["message"],
            result["duration_ms"],
        )

    return executed


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINTS
# ═══════════════════════════════════════════════════════════════════════════════


def run_loop() -> None:
    """Continuous 60-second loop — registered as a daemon service (ADR-130)."""
    logger.info(
        "Schedule executor starting (interval=%ds, skill_roots=%s)",
        POLL_INTERVAL,
        [str(root) for root in _get_skill_source_dirs()],
    )

    while True:
        try:
            count = tick()
            if count:
                logger.info("Tick complete: executed %d schedule(s)", count)
        except Exception as exc:
            logger.error("Tick failed: %s", exc, exc_info=True)
        time.sleep(POLL_INTERVAL)


def main() -> int:
    parser = argparse.ArgumentParser(description="Augur schedule executor (ADR-130)")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously every 60s (default: run once and exit)",
    )
    args = parser.parse_args()

    if args.loop:
        run_loop()
        return 0
    else:
        count = tick()
        logger.info("Single tick complete: executed %d schedule(s)", count)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

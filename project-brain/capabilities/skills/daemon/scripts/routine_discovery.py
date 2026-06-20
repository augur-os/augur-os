"""Background routine discovery across autonomous trigger sources.

ADR-727 replaces the narrow scheduled-executions view with a unified
background-routines inventory. This module owns the machine-local discovery
contract and intentionally fails soft per source kind: one bad plist or YAML
file must not hide every other routine from the user.
"""

from __future__ import annotations

import logging
import plistlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

import yaml

logger = logging.getLogger(__name__)

SOURCE_KINDS = frozenset(
    {
        "per-skill-schedule",
        "daemon-service",
        "daemon-script",
        "launchd-agent",
        "github-action",
        "mcp-background",
        "declared-routine",
    }
)
CADENCE_TYPES = frozenset({"interval", "cron", "event", "manual", "logon"})
STATUSES = frozenset({"enabled", "disabled", "erroring", "paused"})
SPAWN_KINDS = frozenset(
    {"bash", "python", "llm-via-router", "ai-cli-spawn", "http-action", "tiered", "inline-session"}
)
AI_CLIS = frozenset({"claude", "codex", "gemini"})

CANONICAL_TOKENS_PER_CLAUDE_PRINT_RUN = 10_000

_AI_CLI_SPAWN_PATTERN = re.compile(
    r"resolve_cli\(.*?\).*?subprocess\.run\(",
    re.DOTALL,
)
_KNOWN_SPAWN_RATIOS = {
    "insight_scanner": 39,
    "adaptive_loop_executor": 1,
    "ai_monitor_sidecar": 1,
}


@dataclass(frozen=True)
class Routine:
    """Unified background routine record."""

    id: str
    display_name: str
    source_kind: str
    source_path: str
    cadence: dict[str, Any]
    status: str
    spawn_kind: str
    config_path: str | None = None
    ai_cost: dict[str, Any] | None = None
    last_run_at: str | None = None
    last_run_status: str | None = None
    last_run_log: str | None = None
    recent_runs_24h: int | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)


class RoutineDiscoverer(Protocol):
    source_kind: str

    def discover(self) -> list[Routine]: ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def compute_next_run(
    cadence: dict[str, Any],
    last_run_at: str | None = None,
    now: datetime | None = None,
) -> str | None:
    """Compute a lightweight next-run estimate for interval cadences."""

    cadence_type = cadence.get("type")
    if cadence_type in {"event", "manual", "cron", "logon"}:
        return None
    if cadence_type != "interval":
        return None

    interval_seconds = cadence.get("interval_seconds")
    if not interval_seconds:
        return None

    base = now or _utc_now()
    if last_run_at:
        try:
            base = datetime.fromisoformat(last_run_at.replace("Z", "+00:00"))
        except ValueError:
            pass
    try:
        next_run = base + timedelta(seconds=int(interval_seconds))
    except (TypeError, ValueError):
        return None
    return _iso_utc(next_run)


def derive_ai_cost(
    *,
    routine_id: str,
    cli: str,
    logs_dir: Path,
    spawns_per_run: int,
) -> dict[str, Any] | None:
    """Estimate AI CLI token cost from recent routine logs."""

    del routine_id
    if cli not in AI_CLIS:
        return None
    if not logs_dir.exists() or not logs_dir.is_dir():
        return None

    one_day_ago = _utc_now() - timedelta(days=1)
    recent_runs = 0
    for log_path in logs_dir.rglob("*.log"):
        try:
            mtime = datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime >= one_day_ago:
            recent_runs += 1

    if recent_runs == 0:
        return None

    estimated_tokens_per_run = CANONICAL_TOKENS_PER_CLAUDE_PRINT_RUN * max(1, int(spawns_per_run))
    return {
        "cli": cli,
        "estimated_tokens_per_run": estimated_tokens_per_run,
        "estimated_runs_per_day": recent_runs,
        "estimated_tokens_per_day": estimated_tokens_per_run * recent_runs,
    }


def _display_name(identifier: str) -> str:
    return identifier.replace("_", " ").replace("-", " ").title()


def _last_log_info(logs_dir: Path) -> tuple[str | None, str | None, int | None]:
    if not logs_dir.exists() or not logs_dir.is_dir():
        return None, None, None

    one_day_ago = _utc_now() - timedelta(days=1)
    recent_count = 0
    newest_path: Path | None = None
    newest_mtime: datetime | None = None
    for log_path in logs_dir.rglob("*.log"):
        try:
            mtime = datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime >= one_day_ago:
            recent_count += 1
        if newest_mtime is None or mtime > newest_mtime:
            newest_mtime = mtime
            newest_path = log_path

    return (
        _iso_utc(newest_mtime) if newest_mtime else None,
        str(newest_path) if newest_path else None,
        recent_count,
    )


def _call_discover_schedules() -> list[dict[str, Any]]:
    from skills.daemon.scripts.schedule_executor import discover_schedules

    return discover_schedules()


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field from a dataclass-like object or a plain dict uniformly."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _frequency_to_cadence(schedule_cfg: dict[str, Any]) -> dict[str, Any]:
    frequency = str(schedule_cfg.get("frequency", "daily")).lower()
    spec_raw = yaml.safe_dump(schedule_cfg, default_flow_style=True).strip()
    if frequency in {"hourly", "daily", "weekly", "monthly"}:
        seconds = {
            "hourly": 3600,
            "daily": 86400,
            "weekly": 604800,
            "monthly": 2592000,
        }[frequency]
        time_part = str(schedule_cfg.get("time") or "").strip()
        spec = f"{frequency} at {time_part}" if time_part else frequency
        return {
            "type": "interval",
            "spec": spec,
            "spec_raw": spec_raw,
            "interval_seconds": seconds,
        }
    if frequency == "cron":
        value = str(schedule_cfg.get("cron") or schedule_cfg.get("value") or "").strip()
        return {"type": "cron", "spec": value or "cron", "spec_raw": spec_raw}
    if frequency in {"once", "manual"}:
        return {"type": "manual", "spec": frequency, "spec_raw": spec_raw}
    return {"type": "event", "spec": frequency or "event", "spec_raw": spec_raw}


class PerSkillScheduleDiscoverer:
    source_kind = "per-skill-schedule"

    def discover(self) -> list[Routine]:
        try:
            schedules = _call_discover_schedules()
        except Exception as exc:
            logger.warning("PerSkillScheduleDiscoverer failed: %s", exc)
            return []

        routines: list[Routine] = []
        for schedule in schedules:
            if not isinstance(schedule, dict):
                continue
            # ADR-807 Fork 4: schedules carry the Action (dataclass or dict) under
            # "action"; the definition lives in augur/actions.yaml and the runtime
            # state under "_state_path".
            action = schedule.get("action")
            routine_id = str(
                schedule.get("action_id")
                or schedule.get("id")
                or _attr(action, "id")
                or "unknown"
            )
            skill = str(schedule.get("skill") or schedule.get("_skill") or "")
            cadence = _frequency_to_cadence(schedule.get("schedule") if isinstance(schedule.get("schedule"), dict) else {})
            cadence["next_run_estimated"] = compute_next_run(cadence)
            dispatch = str(_attr(action, "dispatch") or "fire")
            source_path = str(schedule.get("_state_path") or schedule.get("_path") or "")
            routines.append(
                Routine(
                    id=routine_id,
                    display_name=_display_name(routine_id),
                    source_kind=self.source_kind,
                    source_path=source_path,
                    config_path=source_path or None,
                    cadence=cadence,
                    status="enabled" if schedule.get("enabled", True) is not False else "disabled",
                    spawn_kind="http-action",
                    description=f"Per-skill schedule{f' for {skill}' if skill else ''}; dispatch={dispatch}.",
                    tags=[tag for tag in ("per-skill", skill) if tag],
                )
            )
        return routines


# A service interval >= 10 years is the documented "soft-disable" sentinel: it keeps
# the config entry + discovery row while preventing execution (see adaptive_loops.yaml).
# Such a routine is surfaced as status="disabled" with a "Disabled" cadence rather than
# a misleading "every 100yr".
_DISABLED_INTERVAL_THRESHOLD_SECONDS = 87600 * 3600


class DaemonServiceDiscoverer:
    source_kind = "daemon-service"

    def __init__(self, config_path: Path | None = None, logs_base_dir: Path | None = None):
        if config_path is None:
            from src.config.paths import get_project_root

            config_path = get_project_root() / "config" / "system" / "adaptive_loops.yaml"
        if logs_base_dir is None:
            from src.config.paths import get_logs_dir

            logs_base_dir = get_logs_dir()
        self.config_path = config_path
        self.logs_base_dir = logs_base_dir

    def discover(self) -> list[Routine]:
        if not self.config_path.exists():
            return []

        try:
            data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            logger.warning("DaemonServiceDiscoverer failed to parse %s: %s", self.config_path, exc)
            return []

        services = data.get("services", {}) if isinstance(data, dict) else {}
        if not isinstance(services, dict):
            return []

        routines: list[Routine] = []
        for service_id, raw_config in sorted(services.items()):
            if not isinstance(raw_config, dict):
                continue
            interval_seconds = self._extract_interval_seconds(raw_config)
            if interval_seconds is None:
                continue
            disabled = (
                raw_config.get("enabled", True) is False
                or interval_seconds >= _DISABLED_INTERVAL_THRESHOLD_SECONDS
            )
            cadence = {
                "type": "interval",
                "spec": "Disabled" if disabled else self._humanize_interval(interval_seconds),
                "spec_raw": yaml.safe_dump(raw_config, default_flow_style=False).strip(),
                "interval_seconds": interval_seconds,
            }
            last_run_at, last_run_log, recent_runs = _last_log_info(self.logs_base_dir / str(service_id))
            cadence["next_run_estimated"] = compute_next_run(cadence, last_run_at=last_run_at)
            service_path = self._service_source_path(str(service_id))
            routines.append(
                Routine(
                    id=str(service_id),
                    display_name=_display_name(str(service_id)),
                    source_kind=self.source_kind,
                    source_path=service_path,
                    config_path=f"{self.config_path}#services.{service_id}",
                    cadence=cadence,
                    status="disabled" if disabled else "enabled",
                    spawn_kind="python",
                    last_run_at=last_run_at,
                    last_run_status="observed" if last_run_at else None,
                    last_run_log=last_run_log,
                    recent_runs_24h=recent_runs,
                    description=f"Daemon service from adaptive_loops.yaml ({cadence['spec']}).",
                    tags=["daemon", "adaptive-loop"],
                )
            )
        return routines

    @staticmethod
    def _extract_interval_seconds(service_config: dict[str, Any]) -> int | None:
        if "interval_hours" in service_config:
            return int(service_config["interval_hours"]) * 3600
        if "poll_interval_seconds" in service_config:
            return int(service_config["poll_interval_seconds"])
        if "interval_seconds" in service_config:
            return int(service_config["interval_seconds"])
        return None

    @staticmethod
    def _humanize_interval(seconds: int) -> str:
        if seconds >= 8760 * 3600 and seconds % (8760 * 3600) == 0:
            return f"every {seconds // (8760 * 3600)}yr"
        if seconds >= 3600 and seconds % 3600 == 0:
            return f"every {seconds // 3600}h"
        if seconds >= 60 and seconds % 60 == 0:
            return f"every {seconds // 60}m"
        return f"every {seconds}s"

    @staticmethod
    def _service_source_path(service_id: str) -> str:
        try:
            from src.config.paths import get_project_root

            scripts_dir = get_project_root() / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts"
            candidate = scripts_dir / f"{service_id}.py"
            if candidate.exists():
                return str(candidate)
        except Exception:
            pass
        return f"project-brain/capabilities/skills/daemon/scripts/{service_id}.py"


class DaemonScriptDiscoverer:
    source_kind = "daemon-script"

    def __init__(self, scripts_dir: Path | None = None, logs_base_dir: Path | None = None):
        if scripts_dir is None:
            from src.config.paths import get_project_root

            scripts_dir = get_project_root() / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts"
        if logs_base_dir is None:
            from src.config.paths import get_logs_dir

            logs_base_dir = get_logs_dir()
        self.scripts_dir = scripts_dir
        self.logs_base_dir = logs_base_dir

    def discover(self) -> list[Routine]:
        if not self.scripts_dir.exists() or not self.scripts_dir.is_dir():
            return []

        routines: list[Routine] = []
        for script_path in sorted(self.scripts_dir.glob("*.py")):
            if script_path.name.startswith("_"):
                continue
            try:
                content = script_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if not _AI_CLI_SPAWN_PATTERN.search(content):
                continue

            script_id = script_path.stem
            routine_id = f"daemon-script:{script_id}"
            spawns_per_run = _KNOWN_SPAWN_RATIOS.get(script_id, 1)
            logs_dir = self.logs_base_dir / script_id
            ai_cost = derive_ai_cost(
                routine_id=routine_id,
                cli="claude",
                logs_dir=logs_dir,
                spawns_per_run=spawns_per_run,
            )
            last_run_at, last_run_log, recent_runs = _last_log_info(logs_dir)
            routines.append(
                Routine(
                    id=routine_id,
                    display_name=_display_name(script_id),
                    source_kind=self.source_kind,
                    source_path=str(script_path),
                    cadence={"type": "event", "spec": "triggered by daemon-service or other", "spec_raw": ""},
                    status="enabled",
                    spawn_kind="ai-cli-spawn",
                    ai_cost=ai_cost,
                    last_run_at=last_run_at,
                    last_run_status="observed" if last_run_at else None,
                    last_run_log=last_run_log,
                    recent_runs_24h=recent_runs,
                    description=(
                        "Script that spawns an AI CLI through subprocess.run "
                        f"(estimated {spawns_per_run} spawn(s) per fire)."
                    ),
                    tags=["daemon", "ai-cli-spawn"],
                )
            )
        return routines


class LaunchdAgentDiscoverer:
    source_kind = "launchd-agent"

    def __init__(self, plist_glob_root: Path | None = None, glob_pattern: str = "com.augur.*.plist"):
        self.plist_glob_root = plist_glob_root or Path.home() / "Library" / "LaunchAgents"
        self.glob_pattern = glob_pattern

    def discover(self) -> list[Routine]:
        if not self.plist_glob_root.exists() or not self.plist_glob_root.is_dir():
            return []

        routines: list[Routine] = []
        for plist_path in sorted(self.plist_glob_root.glob(self.glob_pattern)):
            try:
                with plist_path.open("rb") as handle:
                    payload = plistlib.load(handle)
            except Exception as exc:
                logger.warning("LaunchdAgentDiscoverer skipping malformed %s: %s", plist_path, exc)
                continue

            label = str(payload.get("Label") or plist_path.stem)
            program = payload.get("Program") or (payload.get("ProgramArguments") or [""])[0]
            cadence = self._extract_cadence(payload)
            cadence["next_run_estimated"] = compute_next_run(cadence)
            routines.append(
                Routine(
                    id=label,
                    display_name=label,
                    source_kind=self.source_kind,
                    source_path=str(plist_path),
                    config_path=str(plist_path),
                    cadence=cadence,
                    status="enabled",
                    spawn_kind="python" if "python" in str(program).lower() else "bash",
                    description=f"macOS launchd agent (Program: {program}).",
                    tags=["launchd"],
                )
            )
        return routines

    @staticmethod
    def _extract_cadence(payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("RunAtLoad"):
            return {"type": "logon", "spec": "on logon", "spec_raw": "RunAtLoad: true"}
        if "StartInterval" in payload:
            seconds = int(payload["StartInterval"])
            return {
                "type": "interval",
                "spec": DaemonServiceDiscoverer._humanize_interval(seconds),
                "spec_raw": f"StartInterval: {seconds}",
                "interval_seconds": seconds,
            }
        if "StartCalendarInterval" in payload:
            value = payload["StartCalendarInterval"]
            return {"type": "cron", "spec": str(value), "spec_raw": str(value)}
        return {"type": "event", "spec": "no trigger specified", "spec_raw": ""}


class GitHubActionsDiscoverer:
    source_kind = "github-action"

    def __init__(self, workflows_dir: Path | None = None):
        if workflows_dir is None:
            from src.config.paths import get_project_root

            workflows_dir = get_project_root() / ".github" / "workflows"
        self.workflows_dir = workflows_dir

    def discover(self) -> list[Routine]:
        if not self.workflows_dir.exists() or not self.workflows_dir.is_dir():
            return []

        routines: list[Routine] = []
        for workflow_path in sorted([*self.workflows_dir.glob("*.yml"), *self.workflows_dir.glob("*.yaml")]):
            try:
                payload = yaml.safe_load(workflow_path.read_text(encoding="utf-8")) or {}
            except Exception as exc:
                logger.warning("GitHubActionsDiscoverer skipping malformed %s: %s", workflow_path, exc)
                continue
            if not isinstance(payload, dict):
                continue
            on_config = payload.get("on") or payload.get(True)
            if not isinstance(on_config, dict):
                continue
            schedules = on_config.get("schedule") or []
            if not isinstance(schedules, list):
                continue
            for schedule in schedules:
                if not isinstance(schedule, dict):
                    continue
                cron_expr = str(schedule.get("cron") or "").strip()
                if not cron_expr:
                    continue
                cadence = {
                    "type": "cron",
                    "spec": cron_expr,
                    "spec_raw": f"cron: '{cron_expr}'",
                    "next_run_estimated": None,
                }
                routine_id = f"{workflow_path.stem}-{cron_expr.replace(' ', '_')}"
                routines.append(
                    Routine(
                        id=routine_id,
                        display_name=str(payload.get("name") or _display_name(workflow_path.stem)),
                        source_kind=self.source_kind,
                        source_path=str(workflow_path),
                        config_path=str(workflow_path),
                        cadence=cadence,
                        status="enabled",
                        spawn_kind="http-action",
                        description=f"GitHub Actions scheduled workflow ({cron_expr}).",
                        tags=["github-actions", "ci"],
                    )
                )
        return routines


class McpBackgroundDiscoverer:
    """Reserved source kind for registered MCP background tasks."""

    source_kind = "mcp-background"

    def discover(self) -> list[Routine]:
        return []


def _call_list_declared_routines() -> list[Any]:
    try:
        from skills.daemon.scripts.routine_orchestrator.registry import list_routines
    except ImportError:
        from routine_orchestrator.registry import list_routines  # type: ignore[no-redef]

    return list_routines()


class DeclaredRoutineDiscoverer:
    """ADR-758 declared routines from SKILL.md ``x-augur-routine(s)`` frontmatter.

    Surfaces user-invocable declared routines (e.g. inline-session command wrappers
    like ``desktop-ingest``) that have no other autonomous trigger source, so the
    Routines tab fully answers "what runs without me" (ADR-813).
    """

    source_kind = "declared-routine"

    def discover(self) -> list[Routine]:
        try:
            declared = _call_list_declared_routines()
        except Exception as exc:
            # The registry raises RoutineIdCollision on duplicate SKILL.md ids;
            # one bad declaration must not hide every other routine from the tab.
            logger.warning("DeclaredRoutineDiscoverer failed: %s", exc)
            return []

        routines: list[Routine] = []
        for entry in declared:
            routine_id = str(_attr(entry, "id") or "")
            if not routine_id:
                continue
            skill_name = str(_attr(entry, "skill_name") or "")
            skill_root = _attr(entry, "skill_root")
            callable_path = _attr(entry, "callable_path")
            description = _attr(entry, "description") or f"Declared routine from {skill_name}"
            routines.append(
                Routine(
                    id=routine_id,
                    display_name=_display_name(routine_id),
                    source_kind=self.source_kind,
                    source_path=str(callable_path) if callable_path else "",
                    config_path=str(Path(skill_root) / "SKILL.md") if skill_root else None,
                    cadence={"type": "manual", "spec": "On demand", "spec_raw": ""},
                    status="enabled",
                    spawn_kind=str(_attr(entry, "execution") or ""),
                    description=str(description),
                    tags=[tag for tag in ("declared", skill_name) if tag],
                )
            )
        return routines


DISCOVERERS: list[RoutineDiscoverer] = [
    PerSkillScheduleDiscoverer(),
    DaemonServiceDiscoverer(),
    DaemonScriptDiscoverer(),
    LaunchdAgentDiscoverer(),
    GitHubActionsDiscoverer(),
    McpBackgroundDiscoverer(),
    DeclaredRoutineDiscoverer(),
]


def discover_all_routines() -> list[Routine]:
    """Discover routines from every source kind with fail-soft isolation."""

    routines: list[Routine] = []
    for discoverer in DISCOVERERS:
        try:
            routines.extend(discoverer.discover())
        except Exception as exc:
            logger.warning("discoverer %s failed: %s", discoverer.source_kind, exc, exc_info=True)

    # Dedupe: a daemon-script discovered by filesystem scan that is already registered as
    # a daemon-service (same script file) is the SAME routine surfaced twice. Keep the
    # config-driven service entry (richer cadence/status) and drop the script-scan twin.
    service_paths = {
        r.source_path
        for r in routines
        if r.source_kind == "daemon-service" and r.source_path
    }
    deduped = [
        r
        for r in routines
        if not (r.source_kind == "daemon-script" and r.source_path in service_paths)
    ]

    # Dedupe: an ADR-758 declared routine whose id is already surfaced by a runtime
    # discoverer (e.g. an adaptive-loop daemon-service) is the SAME routine declared
    # twice. Keep the richer runtime entry and drop the declared twin.
    runtime_ids = {r.id for r in deduped if r.source_kind != "declared-routine"}
    return [
        r
        for r in deduped
        if not (r.source_kind == "declared-routine" and r.id in runtime_ids)
    ]

#!/usr/bin/env python3
"""
Nightly backlog executor for agent-tasks.

Runs during a configured time window and only when the Mac is idle.
Optionally claims tasks and runs a command per task.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from subprocess import DEVNULL, CompletedProcess, TimeoutExpired, check_output, run as subprocess_run  # nosec B404
from typing import Any

import yaml


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# This file is at: project-brain/capabilities/skills/platform-admin/scripts/nightly_executor.py
from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_logs_dir  # noqa: E402
from task_utils import (  # noqa: E402
    all_backlog_dirs,
    is_task_available,
    parse_created,
    priority_score,
    read_task,
    resolve_user_data_base,
    task_title,
    write_task,
)

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "window": {"start": "02:00", "end": "08:00"},
    "idle_minutes": 15,
    "stale_claim_hours": 2,
    "agent": "codex",
    "max_tasks": 0,  # 0 = no limit
    "claim_tasks": False,
    "mark_in_progress": False,
    "runner_command": "",
    "runner_command_execute": "",
    "runner_command_breakdown": "",
    "runner_shell": False,
    "runner_timeout_seconds": 3600,
    "allow_claim_without_runner": False,
    "release_on_fail": True,
    "log_dir": str(get_logs_dir() / "nightly"),
    "roi": {
        "enabled": True,
        "priority_weight": 3,
        "type_weight": 2,
        "scope_weight": 1,
        "dependency_penalty": 2,
        "epic_penalty": 1,
        "phase_penalty": 1,
        "scope_items_per_point": 5,
        "scope_max_score": 3,
        "feature_breakdown": True,
        "feature_breakdown_bonus": 1,
        "feature_breakdown_requires_checklist": False,
        "type_weights": {
            "bugfix": 0,
            "refactor": 1,
            "skill-update": 1,
            "feature": 3,
            "research": 4,
        },
    },
}


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve command executable path when available."""
    if not command:
        return command
    resolved = shutil.which(command[0])
    if resolved:
        return [resolved, *command[1:]]
    return command


def _run_command(command: list[str], **kwargs: Any) -> CompletedProcess[str]:
    """Run subprocess command with resolved executable path."""
    return subprocess_run(_resolve_command(command), **kwargs)  # nosec B603


@dataclass
class TaskCandidate:
    path: Path
    frontmatter: dict[str, Any]
    body: str
    priority: int
    created_at: datetime
    title: str
    task_type: str
    execution_mode: str
    scope_items: int
    risk_score: int
    roi_score: int
    roi_components: dict[str, int]


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return DEFAULT_CONFIG
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return DEFAULT_CONFIG
    return deep_merge(DEFAULT_CONFIG, raw)


def parse_time(value: str) -> time:
    return datetime.strptime(value.strip(), "%H:%M").time()


def within_window(now: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def get_idle_seconds() -> float | None:
    if sys.platform != "darwin":
        return None
    try:
        output = check_output(
            _resolve_command(["ioreg", "-c", "IOHIDSystem", "-r", "-d", "1", "-k", "HIDIdleTime"]),
            text=True,
            stderr=DEVNULL,
        )  # nosec B603
    except Exception:
        return None

    match = re.search(r"HIDIdleTime\" = (\d+)", output)
    if not match:
        return None
    return int(match.group(1)) / 1_000_000_000.0


def count_checklist_items(body: str) -> int:
    pattern = re.compile(r"^\s*[-*]\s+\[[ xX]\]\s+")
    return sum(1 for line in body.splitlines() if pattern.match(line))


def execution_mode(task_type: str, body: str, roi_config: dict[str, Any]) -> str:
    if task_type != "feature":
        return "execute"
    if not roi_config.get("feature_breakdown", True):
        return "execute"
    if roi_config.get("feature_breakdown_requires_checklist"):
        lowered = body.lower()
        if "- [ ] user-stories" in lowered or "- [ ] user stories" in lowered:
            return "breakdown"
        return "execute"
    return "breakdown"


def scope_score(scope_items: int, roi_config: dict[str, Any]) -> int:
    per_point = int(roi_config.get("scope_items_per_point", 5))
    max_score = int(roi_config.get("scope_max_score", 3))
    if per_point <= 0:
        return 0
    return min(max_score, scope_items // per_point)


def risk_score(frontmatter: dict[str, Any], body: str, roi_config: dict[str, Any]) -> int:
    score = 0
    if frontmatter.get("depends_on"):
        score += int(roi_config.get("dependency_penalty", 2))
    if frontmatter.get("parent_epic") or frontmatter.get("epic"):
        score += int(roi_config.get("epic_penalty", 1))
    lowered = body.lower()
    if "phased implementation" in lowered or "\n## phase" in lowered or "\n### phase" in lowered:
        score += int(roi_config.get("phase_penalty", 1))
    return score


def roi_score(
    priority: int,
    task_type: str,
    execution: str,
    scope_items: int,
    risk: int,
    roi_config: dict[str, Any],
) -> tuple[int, dict[str, int]]:
    type_weights = roi_config.get("type_weights", {}) or {}
    type_score = int(type_weights.get(task_type, 4))
    if execution == "breakdown":
        bonus = int(roi_config.get("feature_breakdown_bonus", 0))
        type_score = max(0, type_score - bonus)
    scope_component = scope_score(scope_items, roi_config)
    score = (
        priority * int(roi_config.get("priority_weight", 3))
        + type_score * int(roi_config.get("type_weight", 2))
        + scope_component * int(roi_config.get("scope_weight", 1))
        + risk
    )
    return score, {
        "priority": priority,
        "type": type_score,
        "scope": scope_component,
        "risk": risk,
    }


def select_tasks(stale_hours: int, roi_config: dict[str, Any]) -> list[TaskCandidate]:
    candidates: list[TaskCandidate] = []

    seen_paths: set[str] = set()
    for bdir in all_backlog_dirs():
        for path in bdir.rglob("*.md"):
            # Deduplicate and skip non-task files
            resolved = str(path.resolve())
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            if path.name in ("EPIC.md", "README.md"):
                continue
        frontmatter, body = read_task(path)
        if not is_task_available(frontmatter, stale_hours=stale_hours):
            continue
        priority_value = frontmatter.get("priority", "")
        priority_value_score = priority_score(str(priority_value))
        created_value = str(frontmatter.get("created", ""))
        title = task_title(body, path.stem)
        task_type = str(frontmatter.get("type", "") or "").strip().lower()
        scope_items = count_checklist_items(body)
        execution = execution_mode(task_type, body, roi_config)
        risk = risk_score(frontmatter, body, roi_config)
        roi_value, roi_components = roi_score(
            priority_value_score,
            task_type or "unknown",
            execution,
            scope_items,
            risk,
            roi_config,
        )
        candidates.append(
            TaskCandidate(
                path=path,
                frontmatter=frontmatter,
                body=body,
                priority=priority_value_score,
                created_at=parse_created(created_value),
                title=title,
                task_type=task_type or "unknown",
                execution_mode=execution,
                scope_items=scope_items,
                risk_score=risk,
                roi_score=roi_value,
                roi_components=roi_components,
            )
        )
    if roi_config.get("enabled", True):
        candidates.sort(key=lambda item: (item.roi_score, item.priority, item.created_at))
    else:
        candidates.sort(key=lambda item: (item.priority, item.created_at))
    return candidates


def claim_task(task: TaskCandidate, agent: str, in_progress: bool) -> None:
    frontmatter = dict(task.frontmatter)
    execution = dict(frontmatter.get("execution") or {})
    now = datetime.now().isoformat()
    execution["agent"] = agent
    execution["status"] = "in-progress" if in_progress else "claimed"
    execution["claimed_at"] = execution.get("claimed_at") or now
    if in_progress:
        execution["started_at"] = execution.get("started_at") or now
    frontmatter["execution"] = execution
    write_task(task.path, frontmatter, task.body)


def release_task(task: TaskCandidate) -> None:
    content = task.path.read_text(encoding="utf-8")
    content = re.sub(r"execution:.*?(?=\n[a-z]|\n---|\n#|\Z)", "", content, flags=re.DOTALL)
    content = content.replace("\n\n\n", "\n\n")
    task.path.write_text(content, encoding="utf-8")


def truncate(text: str, max_len: int = 2000) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def run_runner(command: str, shell_mode: bool, context: dict[str, str], timeout: int) -> dict[str, Any]:
    formatted = command.format(**context)
    if shell_mode:
        proc = subprocess_run(formatted, shell=True, capture_output=True, text=True, timeout=timeout)  # nosec B602
    else:
        proc = _run_command(shlex.split(formatted), capture_output=True, text=True, timeout=timeout)
    return {
        "command": formatted,
        "exit_code": proc.returncode,
        "stdout": truncate(proc.stdout),
        "stderr": truncate(proc.stderr),
    }


def _check_preconditions(config: dict[str, Any]) -> str | None:
    """Check all preconditions for execution. Returns error message or None if OK."""
    if not config.get("enabled", True):
        return "disabled by config"

    start = parse_time(str(config["window"]["start"]))
    end = parse_time(str(config["window"]["end"]))
    now = datetime.now().time()
    if not within_window(now, start, end):
        return "outside window"

    idle_seconds = get_idle_seconds()
    idle_minutes_required = int(config.get("idle_minutes", 0))
    if idle_seconds is None:
        return "unable to detect idle time"
    if idle_seconds < idle_minutes_required * 60:
        return f"idle {idle_seconds:.0f}s < {idle_minutes_required}m"

    return None


def _select_runner_command(task: TaskCandidate, config: dict[str, Any]) -> str:
    """Select the appropriate runner command based on task execution mode."""
    runner_command = str(config.get("runner_command") or "").strip()
    runner_command_execute = str(config.get("runner_command_execute") or "").strip()
    runner_command_breakdown = str(config.get("runner_command_breakdown") or "").strip()

    if task.execution_mode == "breakdown" and runner_command_breakdown:
        return runner_command_breakdown
    if task.execution_mode == "execute" and runner_command_execute:
        return runner_command_execute
    return runner_command


def _build_task_context(task: TaskCandidate, entry: dict[str, Any]) -> dict[str, str]:
    """Build context dict for runner command substitution."""
    return {
        "task_path": str(task.path),
        "task_id": str(entry["id"]),
        "task_title": task.title,
        "workspace": str(task.frontmatter.get("workspace", "")),
        "repo_root": str(PROJECT_ROOT),
        "task_type": task.task_type,
        "task_priority": str(task.frontmatter.get("priority", "")),
        "task_execution_mode": task.execution_mode,
        "task_roi_score": task.roi_score,
        "task_scope_items": task.scope_items,
    }


def _process_task(
    task: TaskCandidate,
    config: dict[str, Any],
    dry_run: bool,
) -> dict[str, Any]:
    """Process a single task and return the log entry."""
    agent = str(config.get("agent", "codex"))
    mark_in_progress = bool(config.get("mark_in_progress", False))
    release_on_fail = bool(config.get("release_on_fail", True))
    runner_shell = bool(config.get("runner_shell", False))
    timeout = int(config.get("runner_timeout_seconds", 3600))
    claim_tasks = bool(config.get("claim_tasks", False))

    entry: dict[str, Any] = {
        "id": task.frontmatter.get("id", task.path.stem),
        "title": task.title,
        "path": str(task.path),
        "claimed": False,
        "type": task.task_type,
        "execution_mode": task.execution_mode,
        "roi_score": task.roi_score,
        "roi_components": task.roi_components,
    }

    if claim_tasks and not dry_run:
        claim_task(task, agent, mark_in_progress)
        entry["claimed"] = True

    command = _select_runner_command(task, config)
    if command and not dry_run:
        context = _build_task_context(task, entry)
        try:
            entry["runner"] = run_runner(command, runner_shell, context, timeout)
        except TimeoutExpired:
            entry["runner"] = {"command": command, "exit_code": None, "stdout": "", "stderr": "timeout"}

        if entry["runner"].get("exit_code") not in (0, None) and release_on_fail and entry["claimed"]:
            release_task(task)
            entry["released"] = True

    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description="Nightly backlog executor")
    parser.add_argument("--config", type=str, default="", help="Path to config YAML")
    parser.add_argument("--dry-run", action="store_true", help="List tasks without claiming or running")
    args = parser.parse_args()

    base_dir = resolve_user_data_base()
    config_path = (
        Path(args.config)
        if args.config
        else base_dir
        / "plugins"
        / "core"
        / "skills"
        / "executor"
        / "data"
        / "agent-tasks"
        / "config"
        / "nightly-execution.yaml"
    )
    config = load_config(config_path)

    # Check preconditions
    error = _check_preconditions(config)
    if error:
        _out(f"nightly_executor: {error}")
        return 0

    # Select tasks
    roi_config = config.get("roi", {}) or {}
    tasks = select_tasks(int(config.get("stale_claim_hours", 2)), roi_config)
    max_tasks = int(config.get("max_tasks", 0))
    if max_tasks > 0:
        tasks = tasks[:max_tasks]

    if not tasks:
        _out("nightly_executor: no available tasks")
        return 0

    # Validate runner configuration
    runner_command = str(config.get("runner_command") or "").strip()
    runner_command_execute = str(config.get("runner_command_execute") or "").strip()
    runner_command_breakdown = str(config.get("runner_command_breakdown") or "").strip()
    claim_tasks = bool(config.get("claim_tasks", False))
    allow_claim_without_runner = bool(config.get("allow_claim_without_runner", False))
    has_runner_command = bool(runner_command or runner_command_execute or runner_command_breakdown)

    if claim_tasks and not has_runner_command and not allow_claim_without_runner:
        _out("nightly_executor: runner_command is empty; refusing to claim tasks")
        return 1

    # Setup logging
    log_dir_raw = Path(str(config.get("log_dir", DEFAULT_CONFIG["log_dir"])))
    log_dir = log_dir_raw if log_dir_raw.is_absolute() else PROJECT_ROOT / log_dir_raw
    log_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = log_dir / f"nightly-run-{run_id}.json"

    start = parse_time(str(config["window"]["start"]))
    end = parse_time(str(config["window"]["end"]))
    idle_seconds = get_idle_seconds()

    run_log: dict[str, Any] = {
        "run_id": run_id,
        "started_at": datetime.now().isoformat(),
        "config_path": str(config_path),
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "idle_seconds": idle_seconds,
        "roi": {"enabled": roi_config.get("enabled", True)},
        "tasks": [],
    }

    # Process tasks
    for task in tasks:
        entry = _process_task(task, config, args.dry_run)
        run_log["tasks"].append(entry)

    log_path.write_text(json.dumps(run_log, indent=2), encoding="utf-8")
    _out(f"nightly_executor: wrote {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

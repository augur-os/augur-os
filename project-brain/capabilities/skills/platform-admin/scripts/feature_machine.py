"""
Feature Execution Machine - MCP Script for Agent Tasks

Automates the safe feature execution loop:
breakdown -> design -> UI -> test plan -> implementation -> testing -> integration -> docs -> marketing -> PR.

Usage via MCP:
    augur_agent-tasks_feature_machine(params={"action": "next_task", "agent": "codex"})
"""

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
# TODO_CLEANUP: This file is 871 lines — consider splitting into smaller modules

import json
import logging
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CompletedProcess, run as subprocess_run  # nosec B404
from typing import Any, Iterable

import yaml

logger = logging.getLogger(__name__)

CHECKLIST_HEADER = "## Feature Machine Checklist"
LOG_HEADER = "## Execution Log"
DEFAULT_PHASES = [
    "user-stories",
    "design",
    "ui-design",
    "test-plan",
    "implementation",
    "testing",
    "integration",
    "docs",
    "marketing",
    "pr-opened",
]


class TaskEncoder(json.JSONEncoder):
    """Custom JSON encoder for task data (handles dates from YAML)."""

    def default(self, obj):
        if isinstance(obj, (datetime, Path)):
            return str(obj)
        return super().default(obj)


@dataclass
class MachineConfig:
    base_branch: str
    branch_prefix: str
    marketing_dir: Path
    docs_dir: Path
    stale_claim_hours: int
    pr_draft: bool
    squash: bool
    phase_order: list[str]
    test_commands: list[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _resolve_user_data_base() -> Path:
    env = os.environ.get("AUGUR_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    try:
        repo_root = _project_root()
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from src.config.paths import get_project_root  # type: ignore

        return get_project_root()
    except Exception as e:
        logger.warning("Failed to import get_project_root: %s", e)
        return get_project_root()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _data_dir() -> Path:
    return _resolve_user_data_base() / "plugins" / "core" / "skills" / "platform-admin" / "data" / "agent-tasks"


def _backlog_dir() -> Path:
    return _data_dir() / "backlog"


def _completed_dir() -> Path:
    return _data_dir() / "completed"


def _config_path() -> Path:
    return _data_dir() / "config" / "feature-machine.yaml"


def _load_config(overrides: dict | None = None) -> MachineConfig:
    base = _resolve_user_data_base()
    repo_root = _project_root()

    raw: dict[str, Any] = {}
    config_path = _config_path()
    if config_path.exists():
        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            logger.warning("Failed to load feature machine config from %s: %s", config_path, e)
            raw = {}

    if overrides:
        raw.update({k: v for k, v in overrides.items() if v is not None})

    marketing_dir = Path(raw.get("marketing_dir") or (base / "vertical" / "marketing" / "augur-venture")).expanduser()
    docs_dir = Path(raw.get("docs_dir") or (repo_root / "docs")).expanduser()

    phase_order = raw.get("phase_order") or DEFAULT_PHASES
    if not isinstance(phase_order, list) or not all(isinstance(p, str) for p in phase_order):
        phase_order = DEFAULT_PHASES

    test_commands = raw.get("test_commands") or []
    if not isinstance(test_commands, list):
        test_commands = []

    return MachineConfig(
        base_branch=str(raw.get("base_branch") or "main"),
        branch_prefix=str(raw.get("branch_prefix") or "feat"),
        marketing_dir=marketing_dir,
        docs_dir=docs_dir,
        stale_claim_hours=int(raw.get("stale_claim_hours") or 2),
        pr_draft=bool(raw.get("pr_draft", False)),
        squash=bool(raw.get("squash", True)),
        phase_order=[p.strip() for p in phase_order if str(p).strip()],
        test_commands=[str(cmd) for cmd in test_commands if str(cmd).strip()],
    )


def _read_task(path: Path) -> tuple[dict[str, Any], str]:
    content = path.read_text(encoding="utf-8")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = yaml.safe_load(parts[1]) or {}
            body = parts[2].lstrip("\n")
            return frontmatter, body
    return {}, content


def _write_task(path: Path, frontmatter: dict[str, Any], body: str) -> None:
    yaml_block = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    content = f"---\n{yaml_block}\n---\n\n{body.lstrip()}"
    path.write_text(content, encoding="utf-8")


def _task_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _priority_score(value: str) -> int:
    raw = (value or "").strip().lower()
    if raw in {"p0", "critical"}:
        return 0
    if raw in {"p1", "high"}:
        return 1
    if raw in {"p2", "medium"}:
        return 2
    if raw in {"p3", "low"}:
        return 3
    return 4


def _parse_created(raw: str | None) -> datetime:
    if not raw:
        return datetime.min

    def _parse_fmt(value: str, fmt: str) -> datetime | None:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            return None

    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        parsed = _parse_fmt(raw, fmt)
        if parsed is not None:
            return parsed
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception as e:
        logger.debug("Failed to parse date string '%s': %s", raw, e)
        return datetime.min


def _is_task_available(frontmatter: dict[str, Any], stale_hours: int) -> bool:
    status = str(frontmatter.get("status", "")).strip().lower()
    if status != "ready":
        return False

    execution = frontmatter.get("execution") or {}
    exec_status = str(execution.get("status", "")).strip().lower()
    if exec_status in {"claimed", "in-progress", "blocked"}:
        claimed_at = execution.get("claimed_at")
        if not claimed_at:
            return False
        try:
            claimed_time = datetime.fromisoformat(str(claimed_at).replace("Z", "+00:00"))
            elapsed = datetime.now(tz=claimed_time.tzinfo) - claimed_time
            if elapsed.total_seconds() < stale_hours * 3600:
                return False
        except Exception as e:
            logger.warning("Failed to parse claimed_at timestamp for stale check: %s", e)
            return False
    return True


def _iter_backlog_tasks() -> Iterable[Path]:
    backlog_dir = _backlog_dir()
    if not backlog_dir.exists():
        return []
    return [p for p in backlog_dir.rglob("*.md") if p.name != "EPIC.md"]


def _resolve_task_path(
    task_path: str | None,
    task_id: str | None,
) -> tuple[Path | None, dict[str, Any] | None]:
    if task_path:
        return Path(task_path), None
    if not task_id:
        return None, {"error": "Missing task path or id"}

    backlog_dir = _backlog_dir()
    direct = backlog_dir / f"{task_id}.md"
    if direct.exists():
        return direct, None
    direct = backlog_dir / task_id
    if direct.exists():
        return direct, None

    matches = list(backlog_dir.rglob(f"*{task_id}*.md"))
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        return None, {"error": f"Task not found: {task_id}"}
    return None, {"error": f"Ambiguous task id: {task_id}", "matches": [str(path) for path in matches]}


def _select_next_task(
    task_type: str | None,
    status: str,
    stale_hours: int,
) -> dict[str, Any] | None:
    candidates = []
    for path in _iter_backlog_tasks():
        frontmatter, body = _read_task(path)
        t_type = str(frontmatter.get("type") or "").strip().lower()
        if task_type and t_type != task_type.lower():
            if task_type.lower() == "feature" and not path.name.startswith("feat-"):
                continue
            if task_type.lower() != "feature":
                continue
        task_status = str(frontmatter.get("status") or "").strip().lower()
        if status != "any" and task_status != status.lower():
            continue
        if status.lower() == "ready" and not _is_task_available(frontmatter, stale_hours):
            continue

        title = _task_title(body, path.stem)
        priority = _priority_score(str(frontmatter.get("priority") or ""))
        created = _parse_created(str(frontmatter.get("created") or ""))
        candidates.append((priority, created, path, frontmatter, body, title))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]))
    _, _, path, frontmatter, body, title = candidates[0]
    return {
        "path": str(path),
        "title": title,
        "frontmatter": frontmatter,
        "body": body,
    }


def _ensure_checklist(body: str, phases: list[str]) -> str:
    lines = body.splitlines()
    header_idx = None
    for idx, line in enumerate(lines):
        if line.strip() == CHECKLIST_HEADER:
            header_idx = idx
            break

    if header_idx is None:
        checklist_lines = [CHECKLIST_HEADER] + [f"- [ ] {phase}" for phase in phases]
        if body.strip():
            return body.rstrip() + "\n\n" + "\n".join(checklist_lines) + "\n"
        return "\n".join(checklist_lines) + "\n"

    end_idx = len(lines)
    for idx in range(header_idx + 1, len(lines)):
        if lines[idx].startswith("## ") and lines[idx].strip() != CHECKLIST_HEADER:
            end_idx = idx
            break

    existing = lines[header_idx + 1 : end_idx]
    existing_phases = set()
    for line in existing:
        match = re.match(r"^- \[[ xX]\] (.+)$", line.strip())
        if match:
            existing_phases.add(match.group(1).strip())

    extra = [f"- [ ] {phase}" for phase in phases if phase not in existing_phases]
    if extra:
        lines[end_idx:end_idx] = extra

    return "\n".join(lines).rstrip() + "\n"


def _set_checklist_phase(body: str, phase: str, done: bool) -> str:
    body = _ensure_checklist(body, [phase])
    lines = body.splitlines()
    updated = False
    for idx, line in enumerate(lines):
        match = re.match(r"^- \[[ xX]\] (.+)$", line.strip())
        if not match:
            continue
        label = match.group(1).strip()
        if label == phase:
            lines[idx] = f"- [{'x' if done else ' '}] {phase}"
            updated = True
            break
    if not updated:
        lines.append(f"- [{'x' if done else ' '}] {phase}")
    return "\n".join(lines).rstrip() + "\n"


def _append_log(body: str, phase: str, note: str | None) -> str:
    lines = body.splitlines()
    header_idx = None
    for idx, line in enumerate(lines):
        if line.strip() == LOG_HEADER:
            header_idx = idx
            break

    entry = f"- {_utc_now()} | {phase}"
    if note:
        entry += f" | {note}"

    if header_idx is None:
        if body.strip():
            return body.rstrip() + f"\n\n{LOG_HEADER}\n{entry}\n"
        return f"{LOG_HEADER}\n{entry}\n"

    insert_idx = header_idx + 1
    lines.insert(insert_idx, entry)
    return "\n".join(lines).rstrip() + "\n"


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    cleaned = cleaned.strip("-")
    return cleaned or "feature"


def _resolve_command(command: list[str]) -> list[str]:
    if not command:
        return command
    executable = command[0]
    if os.path.isabs(executable):
        return command
    resolved = shutil.which(executable)
    if resolved:
        return [resolved, *command[1:]]
    return command


def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc: CompletedProcess[str] = subprocess_run(
        _resolve_command(cmd),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )  # nosec B603
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _run_shell(command: str, cwd: Path) -> tuple[int, str, str]:
    proc = subprocess_run(command, cwd=str(cwd), capture_output=True, text=True, shell=True)  # nosec B602
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _git_repo_root() -> Path:
    return _project_root()


def _ensure_clean_worktree(repo_root: Path) -> tuple[bool, str]:
    code, out, err = _run(["git", "status", "--porcelain"], repo_root)
    if code != 0:
        return False, err or out or "git status failed"
    if out.strip():
        return False, "Working tree is dirty"
    return True, ""


def _extract_section(body: str, header: str) -> str:
    lines = body.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == f"## {header}":
            start = idx + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for idx in range(start, len(lines)):
        if lines[idx].startswith("## "):
            end = idx
            break
    section = "\n".join(lines[start:end]).strip()
    return section


def _extract_test_commands(body: str) -> list[str]:
    commands = []
    for match in re.findall(r"`([^`]+)`", body):
        candidate = match.strip()
        if not candidate:
            continue
        if any(
            candidate.startswith(prefix)
            for prefix in ("pytest", "uv ", "npm ", "pnpm ", "yarn ", "go test", "cargo ", "python ", "./")
        ):
            commands.append(candidate)
    return list(dict.fromkeys(commands))


def list_tasks(params: dict) -> str:
    task_type = params.get("type", "feature")
    status = params.get("status", "ready")
    config = _load_config()

    tasks = []
    for path in _iter_backlog_tasks():
        frontmatter, body = _read_task(path)
        t_type = str(frontmatter.get("type") or "").strip().lower()
        if task_type and t_type != task_type.lower():
            if task_type.lower() == "feature" and not path.name.startswith("feat-"):
                continue
            if task_type.lower() != "feature":
                continue
        task_status = str(frontmatter.get("status") or "").strip().lower()
        if status != "any" and task_status != status.lower():
            continue
        if status.lower() == "ready" and not _is_task_available(frontmatter, config.stale_claim_hours):
            continue
        tasks.append(
            {
                "id": frontmatter.get("id") or path.stem,
                "title": _task_title(body, path.stem),
                "status": task_status,
                "priority": frontmatter.get("priority"),
                "path": str(path),
            }
        )

    return json.dumps({"count": len(tasks), "tasks": tasks}, indent=2, cls=TaskEncoder)


def next_task(params: dict) -> str:
    agent = params.get("agent", "unknown")
    task_type = params.get("type", "feature")
    status = params.get("status", "ready")
    config = _load_config()
    selected = _select_next_task(task_type, status, config.stale_claim_hours)
    if not selected:
        return json.dumps({"message": "No available tasks matching criteria", "tasks": []}, indent=2, cls=TaskEncoder)

    path = Path(selected["path"])
    frontmatter = selected["frontmatter"]
    body = _ensure_checklist(selected["body"], config.phase_order)
    execution = frontmatter.get("execution") or {}
    execution.update({"agent": agent, "status": "claimed", "claimed_at": _utc_now()})
    frontmatter["execution"] = execution
    _write_task(path, frontmatter, body)

    return json.dumps(
        {
            "message": f"Task claimed for {agent}",
            "task": {
                "id": frontmatter.get("id") or path.stem,
                "title": _task_title(body, path.stem),
                "path": str(path),
            },
        },
        indent=2,
        cls=TaskEncoder,
    )


def start_task(params: dict) -> str:
    agent = params.get("agent", "unknown")
    task_path = params.get("path")
    task_id = params.get("id")
    config = _load_config()

    if task_path or task_id:
        path, error = _resolve_task_path(task_path, task_id)
        if error:
            return json.dumps(error, indent=2, cls=TaskEncoder)
    else:
        selected = _select_next_task(
            params.get("type", "feature"), params.get("status", "ready"), config.stale_claim_hours
        )
        if not selected:
            return json.dumps({"error": "No task available to start"}, indent=2, cls=TaskEncoder)
        path = Path(selected["path"])

    if not path or not path.exists():
        return json.dumps({"error": f"Task not found: {path}"}, indent=2, cls=TaskEncoder)

    frontmatter, body = _read_task(path)
    body = _ensure_checklist(body, config.phase_order)
    execution = frontmatter.get("execution") or {}
    if execution.get("status") not in {"claimed", "in-progress"}:
        execution["agent"] = agent
        execution["claimed_at"] = execution.get("claimed_at") or _utc_now()
    execution["status"] = "in-progress"
    execution["started_at"] = execution.get("started_at") or _utc_now()

    task_title = _task_title(body, path.stem)
    slug = _slugify(task_title)[:40]
    task_id = frontmatter.get("id") or path.stem
    branch_name = execution.get("branch") or f"{config.branch_prefix}-{task_id}-{slug}"
    execution["branch"] = branch_name
    frontmatter["execution"] = execution
    frontmatter["status"] = "in-progress"

    _write_task(path, frontmatter, body)

    repo_root = _git_repo_root()
    code, out, err = _run(["git", "rev-parse", "--verify", branch_name], repo_root)
    if code != 0:
        code, out, err = _run(["git", "checkout", "-b", branch_name], repo_root)
    else:
        code, out, err = _run(["git", "checkout", branch_name], repo_root)
    if code != 0:
        return json.dumps({"error": err or out or "Failed to checkout branch"}, indent=2, cls=TaskEncoder)

    return json.dumps(
        {
            "message": "Task started",
            "task": {"id": task_id, "title": task_title, "path": str(path)},
            "branch": branch_name,
        },
        indent=2,
        cls=TaskEncoder,
    )


def update_phase(params: dict) -> str:
    task_path = params.get("path")
    task_id = params.get("id")
    phase = params.get("phase")
    done = bool(params.get("done", True))
    note = params.get("note")
    config = _load_config()

    if not phase:
        return json.dumps({"error": "Missing phase"}, indent=2, cls=TaskEncoder)

    # Validate phase against configured phase order
    if phase not in config.phase_order:
        return json.dumps(
            {
                "error": f"Unknown phase: {phase}",
                "valid_phases": config.phase_order,
            },
            indent=2,
            cls=TaskEncoder,
        )

    path, error = _resolve_task_path(task_path, task_id)
    if error:
        return json.dumps(error, indent=2, cls=TaskEncoder)
    if not path or not path.exists():
        return json.dumps({"error": f"Task not found: {path}"}, indent=2, cls=TaskEncoder)

    frontmatter, body = _read_task(path)
    execution = frontmatter.get("execution") or {}
    execution["phase"] = phase
    frontmatter["execution"] = execution
    body = _set_checklist_phase(body, phase, done)
    if note:
        body = _append_log(body, phase, note)
    _write_task(path, frontmatter, body)

    return json.dumps({"message": "Phase updated", "phase": phase, "done": done}, indent=2, cls=TaskEncoder)


def run_tests(params: dict) -> str:
    task_path = params.get("path")
    task_id = params.get("id")
    path, error = _resolve_task_path(task_path, task_id)
    if error:
        return json.dumps(error, indent=2, cls=TaskEncoder)
    if not path or not path.exists():
        return json.dumps({"error": f"Task not found: {path}"}, indent=2, cls=TaskEncoder)

    frontmatter, body = _read_task(path)
    config = _load_config()

    commands = params.get("commands") or []
    if isinstance(commands, str):
        commands = [commands]
    if not commands:
        commands = config.test_commands or _extract_test_commands(body)
    if not commands:
        return json.dumps({"error": "No test commands provided"}, indent=2, cls=TaskEncoder)

    workspace = frontmatter.get("workspace")
    cwd = Path(os.path.expanduser(workspace)).resolve() if workspace else _git_repo_root()

    results = []
    for command in commands:
        code, out, err = _run_shell(command, cwd)
        results.append({"command": command, "exit_code": code, "stdout": out, "stderr": err})
        if code != 0:
            return json.dumps({"error": "Test command failed", "results": results}, indent=2, cls=TaskEncoder)

    return json.dumps({"message": "Tests passed", "results": results}, indent=2, cls=TaskEncoder)


def rebase_branch(params: dict) -> str:
    config = _load_config()
    repo_root = _git_repo_root()
    base_branch = params.get("base_branch") or config.base_branch

    code, branch, err = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    if code != 0:
        return json.dumps({"error": err or "Failed to detect current branch"}, indent=2, cls=TaskEncoder)
    if branch == base_branch:
        return json.dumps({"error": "Refusing to rebase main branch"}, indent=2, cls=TaskEncoder)

    code, out, err = _run(["git", "fetch", "origin", base_branch], repo_root)
    if code != 0:
        return json.dumps({"error": err or out or "git fetch failed"}, indent=2, cls=TaskEncoder)

    code, out, err = _run(["git", "rebase", f"origin/{base_branch}"], repo_root)
    if code != 0:
        has_conflicts = "conflict" in (err or out or "").lower()
        return json.dumps(
            {
                "error": err or out or "git rebase failed",
                "has_conflicts": has_conflicts,
                "recovery": "Run 'git rebase --abort' to recover, then resolve conflicts manually",
            },
            indent=2,
            cls=TaskEncoder,
        )

    return json.dumps({"message": "Branch rebased", "base_branch": base_branch}, indent=2, cls=TaskEncoder)


def squash_commits(params: dict) -> str:
    config = _load_config()
    repo_root = _git_repo_root()
    base_branch = params.get("base_branch") or config.base_branch
    title = params.get("title") or "Feature update"

    clean, reason = _ensure_clean_worktree(repo_root)
    if not clean:
        return json.dumps({"error": reason}, indent=2, cls=TaskEncoder)

    code, branch, err = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    if code != 0:
        return json.dumps({"error": err or "Failed to detect branch"}, indent=2, cls=TaskEncoder)
    if branch == base_branch:
        return json.dumps({"error": "Refusing to squash main branch"}, indent=2, cls=TaskEncoder)

    code, out, err = _run(["git", "fetch", "origin", base_branch], repo_root)
    if code != 0:
        return json.dumps({"error": err or out or "git fetch failed"}, indent=2, cls=TaskEncoder)

    code, base, err = _run(["git", "merge-base", "HEAD", f"origin/{base_branch}"], repo_root)
    if code != 0:
        return json.dumps({"error": err or "Failed to find merge base"}, indent=2, cls=TaskEncoder)

    code, out, err = _run(["git", "reset", "--soft", base], repo_root)
    if code != 0:
        return json.dumps(
            {
                "error": err or out or "git reset failed",
                "recovery": f"Run 'git reset --hard origin/{branch}' to recover the original branch state",
            },
            indent=2,
            cls=TaskEncoder,
        )

    code, out, err = _run(["git", "commit", "-m", title], repo_root)
    if code != 0:
        return json.dumps(
            {
                "error": err or out or "git commit failed",
                "recovery": "Working tree may be in an inconsistent state. Check 'git status'.",
            },
            indent=2,
            cls=TaskEncoder,
        )

    return json.dumps({"message": "Squashed to one commit", "commit_title": title}, indent=2, cls=TaskEncoder)


def open_pr(params: dict) -> str:
    config = _load_config()
    repo_root = _git_repo_root()
    base_branch = params.get("base_branch") or config.base_branch
    task_path = params.get("path")
    task_id = params.get("id")

    path, error = _resolve_task_path(task_path, task_id)
    if error:
        return json.dumps(error, indent=2, cls=TaskEncoder)
    if not path or not path.exists():
        return json.dumps({"error": f"Task not found: {path}"}, indent=2, cls=TaskEncoder)
    frontmatter, body = _read_task(path)

    clean, reason = _ensure_clean_worktree(repo_root)
    if not clean:
        return json.dumps({"error": reason}, indent=2, cls=TaskEncoder)

    if not shutil.which("gh"):
        return json.dumps({"error": "gh CLI not found in PATH"}, indent=2, cls=TaskEncoder)

    code, branch, err = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    if code != 0:
        return json.dumps({"error": err or "Failed to detect branch"}, indent=2, cls=TaskEncoder)
    if branch == base_branch:
        return json.dumps({"error": "Refusing to open PR from main branch"}, indent=2, cls=TaskEncoder)

    title = _task_title(body, str(frontmatter.get("id") or path.stem))
    objective = _extract_section(body, "Objective")
    acceptance = _extract_section(body, "Acceptance Criteria")
    test_cmds = config.test_commands or _extract_test_commands(body)
    test_block = "\n".join(f"- `{cmd}`" for cmd in test_cmds) if test_cmds else "- (not specified)"

    body_lines = [
        "## Summary",
        objective or "- (add summary)",
        "",
        "## Acceptance Criteria",
        acceptance or "- (add criteria)",
        "",
        "## Testing",
        test_block,
        "",
        "## Docs",
        f"- Update `/docs` as needed (target: {config.docs_dir})",
        "",
        "## Marketing",
        f"- Update marketing content (target: {config.marketing_dir})",
    ]
    pr_body = "\n".join(body_lines).strip()

    args = ["gh", "pr", "create", "--title", title, "--body", pr_body, "--base", base_branch, "--head", branch]
    if config.pr_draft:
        args.append("--draft")

    code, out, err = _run(args, repo_root)
    if code != 0:
        return json.dumps({"error": err or out or "gh pr create failed"}, indent=2, cls=TaskEncoder)

    pr_url = out.splitlines()[-1].strip() if out else ""
    execution = frontmatter.get("execution") or {}
    execution["pr_url"] = pr_url
    frontmatter["execution"] = execution
    _write_task(path, frontmatter, body)

    return json.dumps({"message": "PR created", "pr_url": pr_url}, indent=2, cls=TaskEncoder)


def complete_task(params: dict) -> str:
    task_path = params.get("path")
    task_id = params.get("id")
    path, error = _resolve_task_path(task_path, task_id)
    if error:
        return json.dumps(error, indent=2, cls=TaskEncoder)

    if not path or not path.exists():
        return json.dumps({"error": f"Task not found: {path}"}, indent=2, cls=TaskEncoder)

    frontmatter, body = _read_task(path)
    execution = frontmatter.get("execution") or {}
    execution["status"] = "completed"
    execution["completed_at"] = _utc_now()
    frontmatter["execution"] = execution
    frontmatter["status"] = "done"

    body = _ensure_checklist(body, DEFAULT_PHASES)
    body = _set_checklist_phase(body, "pr-opened", True)
    _write_task(path, frontmatter, body)

    backlog_dir = _backlog_dir()
    completed_dir = _completed_dir()
    try:
        rel = path.relative_to(backlog_dir)
    except Exception as e:
        logger.warning("Could not compute relative path for %s from %s: %s", path, backlog_dir, e)
        rel = Path(path.name)
    dest = completed_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dest))

    return json.dumps({"message": "Task completed", "path": str(dest)}, indent=2, cls=TaskEncoder)


def main(params: dict = {}) -> str:
    action = params.get("action", "list")

    actions = {
        "list": lambda: list_tasks(params),
        "next_task": lambda: next_task(params),
        "start_task": lambda: start_task(params),
        "update_phase": lambda: update_phase(params),
        "run_tests": lambda: run_tests(params),
        "rebase": lambda: rebase_branch(params),
        "squash": lambda: squash_commits(params),
        "open_pr": lambda: open_pr(params),
        "complete_task": lambda: complete_task(params),
    }

    if action not in actions:
        return json.dumps(
            {
                "error": f"Unknown action: {action}",
                "available_actions": list(actions.keys()),
            },
            indent=2,
            cls=TaskEncoder,
        )

    return actions[action]()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        action = sys.argv[1]
        params = {"action": action}
        for arg in sys.argv[2:]:
            if "=" in arg:
                key, value = arg.split("=", 1)
                params[key] = value
        sys.stdout.write(f"{main(params)}\n")
    else:
        sys.stdout.write(f"{main({'action': 'list'})}\n")

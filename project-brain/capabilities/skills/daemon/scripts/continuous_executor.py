#!/usr/bin/env python3
"""
Continuous Executor Daemon for Augur.

Persistent background daemon that continuously polls the backlog
for autonomous tasks and executes them in parallel using the
headless_runner.

Designed to run as a launchd KeepAlive service (24/7).

Usage:
    python continuous_executor.py                    # Normal daemon mode
    python continuous_executor.py --once             # Single poll cycle
    python continuous_executor.py --config /path.yaml # Custom config
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor, Future
from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired, run  # nosec B404
from typing import Any

import yaml

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

# Add platform-admin scripts dir for task_utils and headless_runner imports.
from src.config.paths import get_logs_dir, get_python_executable, get_project_brain_skills_dir, get_skill_root  # noqa: E402

def _resolve_platform_admin_scripts() -> Path:
    try:
        return get_skill_root("platform-admin") / "scripts"
    except ValueError:
        return get_project_brain_skills_dir(PROJECT_ROOT) / "platform-admin" / "scripts"


DEVOPS_SCRIPTS = _resolve_platform_admin_scripts()
if str(DEVOPS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DEVOPS_SCRIPTS))

from src.logging import get_entity_logger  # noqa: E402
from task_utils import all_backlog_dirs, is_task_available, read_task, resolve_user_data_base  # noqa: E402

logger = get_entity_logger("continuous_executor")


@contextmanager
def _job_ledger_run(**kwargs: Any):
    """Best-effort ledger wrapper. A ledger failure never blocks task polling."""
    try:
        from job_ledger.ledger import run as ledger_run
    except Exception as exc:  # noqa: BLE001
        logger.warning("job ledger unavailable: %s", exc)
        yield None
        return
    with ledger_run(**kwargs) as job:
        yield job


def _job_ledger_cycle_timeout_s(config: dict[str, Any]) -> int:
    max_parallel = int(config.get("max_parallel", 3))
    timeout = int(config.get("runner_timeout_seconds", 3600))
    return max_parallel * (timeout + 300)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "max_parallel": 3,
    "poll_interval_seconds": 300,
    "backoff_multiplier": 2.0,
    "max_backoff_seconds": 1800,
    "stale_claim_hours": 2,
    "runner_timeout_seconds": 3600,
    "max_budget_per_task": 5.0,
    "model": "sonnet",
    "task_filter": {
        "autonomous": True,
    },
    "log_dir": str(get_logs_dir() / "continuous"),
}

# Shutdown flag
_shutdown = False


def _signal_handler(signum: int, _frame: Any) -> None:
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    global _shutdown
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    _shutdown = True


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG LOADING
# ═══════════════════════════════════════════════════════════════════════════════


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base, preserving nested defaults."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_services_config() -> dict[str, Any]:
    """Read continuous_executor overrides from adaptive_loops.yaml (ADR-216)."""
    try:
        from src.config.paths import get_config_dir
        cfg_path = get_config_dir() / "system" / "adaptive_loops.yaml"
        if cfg_path.exists():
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            return data.get("services", {}).get("continuous_executor", {})
    except Exception:
        pass
    return {}


def load_config(path: Path) -> dict[str, Any]:
    """Load config from YAML file, deep-merged with defaults and services config."""
    if not path.exists():
        base = dict(DEFAULT_CONFIG)
    else:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw, dict):
                base = dict(DEFAULT_CONFIG)
            else:
                base = _deep_merge(DEFAULT_CONFIG, raw)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            base = dict(DEFAULT_CONFIG)
    # ADR-216: overlay services config from adaptive_loops.yaml
    services_overrides = _load_services_config()
    if services_overrides:
        base = _deep_merge(base, services_overrides)
    return base


# ═══════════════════════════════════════════════════════════════════════════════
# TASK SELECTION
# ═══════════════════════════════════════════════════════════════════════════════


def find_autonomous_tasks(
    stale_hours: int = 2,
    max_tasks: int = 10,
) -> list[Path]:
    """Find tasks in the backlog that are tagged autonomous and available."""
    candidates: list[tuple[Path, int]] = []

    for bdir in all_backlog_dirs():
        for path in bdir.rglob("*.md"):
            if path.name in ("EPIC.md", "README.md"):
                continue
            frontmatter: dict[str, Any] | None = None
            try:
                frontmatter, _body = read_task(path)
            except Exception as exc:
                logger.debug("Skipping unreadable task file %s: %s", path, exc)
            if frontmatter is None:
                continue

            if not is_task_available(frontmatter, stale_hours=stale_hours):
                continue

            # Check autonomous tag
            tags = frontmatter.get("tags", []) or []
            autonomous = frontmatter.get("autonomous", False)
            if not autonomous and "autonomous" not in tags:
                continue

            # Simple priority scoring (lower = higher priority)
            priority_map = {"critical": 0, "high": 1, "p1": 1, "medium": 2, "p2": 2, "low": 3, "p3": 3}
            priority = str(frontmatter.get("priority", "medium")).lower().strip()
            score = priority_map.get(priority, 4)

            candidates.append((path, score))

    # Sort by priority (lower score = higher priority)
    candidates.sort(key=lambda x: x[1])
    return [path for path, _ in candidates[:max_tasks]]


# ═══════════════════════════════════════════════════════════════════════════════
# TASK EXECUTION (runs in subprocess via ProcessPoolExecutor)
# ═══════════════════════════════════════════════════════════════════════════════


def _run_headless_task(
    task_path: str,
    model: str,
    timeout: int,
    max_budget: float,
) -> dict[str, Any]:
    """Execute a single task via headless_runner. Runs in a child process."""
    runner_script = str(DEVOPS_SCRIPTS / "headless_runner.py")

    creationflags = 0x08000000 if sys.platform == "win32" else 0
    try:
        result: CompletedProcess[str] = run(
            [
                str(get_python_executable()),
                runner_script,
                "--task",
                task_path,
                "--model",
                model,
                "--timeout",
                str(timeout),
                "--max-budget",
                str(max_budget),
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 120,  # Extra buffer for git operations
            cwd=str(PROJECT_ROOT),
            check=False,
            creationflags=creationflags,
        )  # nosec B603

        return {
            "task_path": task_path,
            "exit_code": result.returncode,
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-1000:] if result.stderr else "",
            "success": result.returncode == 0,
        }
    except TimeoutExpired:
        return {
            "task_path": task_path,
            "exit_code": -1,
            "stdout": "",
            "stderr": "Timeout",
            "success": False,
        }
    except Exception as e:
        return {
            "task_path": task_path,
            "exit_code": -2,
            "stdout": "",
            "stderr": str(e),
            "success": False,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════


def write_cycle_log(
    cycle: int,
    tasks_found: int,
    tasks_started: int,
    results: list[dict[str, Any]],
    log_dir: Path,
) -> None:
    """Write a log entry for this poll cycle."""
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    succeeded = sum(1 for r in results if r.get("success"))
    failed = sum(1 for r in results if not r.get("success"))

    entry = {
        "cycle": cycle,
        "timestamp": datetime.now().isoformat(),
        "tasks_found": tasks_found,
        "tasks_started": tasks_started,
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }

    log_path = log_dir / f"cycle-{timestamp}.json"
    log_path.write_text(json.dumps(entry, indent=2), encoding="utf-8")

    logger.info(f"Cycle {cycle}: found={tasks_found} started={tasks_started} " f"succeeded={succeeded} failed={failed}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN DAEMON LOOP
# ═══════════════════════════════════════════════════════════════════════════════


def run_cycle(
    config: dict[str, Any],
    active_tasks: set[str],
) -> tuple[int, list[dict[str, Any]]]:
    """Run a single poll-and-execute cycle.

    Returns (tasks_found, results) where tasks_found is the total discovered
    before filtering and results is the list of completed task outcomes.
    """
    max_parallel = int(config.get("max_parallel", 3))
    stale_hours = int(config.get("stale_claim_hours", 2))
    model = str(config.get("model", "sonnet"))
    timeout = int(config.get("runner_timeout_seconds", 3600))
    max_budget = float(config.get("max_budget_per_task", 5.0))

    # How many slots available?
    available_slots = max_parallel - len(active_tasks)
    if available_slots <= 0:
        return 0, []

    # Find tasks
    all_tasks = find_autonomous_tasks(
        stale_hours=stale_hours,
        max_tasks=available_slots + len(active_tasks),
    )
    tasks_found = len(all_tasks)

    # Filter out already-running tasks and limit to available slots
    tasks = [t for t in all_tasks if str(t) not in active_tasks][:available_slots]

    if not tasks:
        return tasks_found, []

    # Execute in parallel
    results: list[dict[str, Any]] = []

    with ProcessPoolExecutor(max_workers=min(len(tasks), available_slots)) as executor:
        futures: dict[Future, Path] = {}
        for task_path in tasks:
            active_tasks.add(str(task_path))
            future = executor.submit(
                _run_headless_task,
                str(task_path),
                model,
                timeout,
                max_budget,
            )
            futures[future] = task_path

        for future in futures:
            try:
                result = future.result(timeout=timeout + 300)
                results.append(result)
            except Exception as e:
                task_path = futures[future]
                results.append(
                    {
                        "task_path": str(task_path),
                        "exit_code": -3,
                        "stdout": "",
                        "stderr": str(e),
                        "success": False,
                    }
                )
            finally:
                task_path = futures[future]
                active_tasks.discard(str(task_path))

    return tasks_found, results


def daemon_loop(config: dict[str, Any], once: bool = False) -> None:
    """Main daemon loop: poll → execute → sleep → repeat."""
    poll_interval = int(config.get("poll_interval_seconds", 300))
    backoff_multiplier = float(config.get("backoff_multiplier", 2.0))
    max_backoff = int(config.get("max_backoff_seconds", 1800))
    log_dir_raw = Path(str(config.get("log_dir", DEFAULT_CONFIG["log_dir"])))
    log_dir = log_dir_raw if log_dir_raw.is_absolute() else PROJECT_ROOT / log_dir_raw

    current_interval = poll_interval
    cycle = 0
    active_tasks: set[str] = set()

    logger.info(
        f"Continuous executor starting: max_parallel={config.get('max_parallel')}, "
        f"poll_interval={poll_interval}s, model={config.get('model')}"
    )

    while not _shutdown:
        cycle += 1

        try:
            # Reload config each cycle (allows hot-reconfiguration)
            config_path = (
                resolve_user_data_base()
                / "plugins"
                / "core"
                / "skills"
                / "executor"
                / "data"
                / "tasks"
                / "config"
                / "continuous-execution.yaml"
            )
            if config_path.exists():
                config = load_config(config_path)

            # Re-read runtime tunables so service config changes apply next cycle.
            poll_interval = int(config.get("poll_interval_seconds", 300))
            backoff_multiplier = float(config.get("backoff_multiplier", 2.0))
            max_backoff = int(config.get("max_backoff_seconds", 1800))
            log_dir_raw = Path(str(config.get("log_dir", DEFAULT_CONFIG["log_dir"])))
            log_dir = log_dir_raw if log_dir_raw.is_absolute() else PROJECT_ROOT / log_dir_raw
            current_interval = max(poll_interval, min(current_interval, max_backoff))

            if not config.get("enabled", True):
                logger.info("Continuous executor disabled by config, sleeping...")
                time.sleep(60)
                continue

            with _job_ledger_run(
                kind="continuous",
                name="continuous-executor-cycle",
                args={
                    "cycle": cycle,
                    "max_parallel": config.get("max_parallel"),
                    "model": config.get("model"),
                },
                timeout_s=_job_ledger_cycle_timeout_s(config),
            ) as _job:
                if _job is not None:
                    _job.phase("dispatch")
                tasks_found, results = run_cycle(config, active_tasks)

            if results:
                write_cycle_log(cycle, tasks_found, len(results), results, log_dir)
                any_success = any(r.get("success", False) for r in results)
                if any_success:
                    current_interval = poll_interval  # Reset backoff on success
                else:
                    # All tasks failed — continue backing off
                    current_interval = min(
                        int(current_interval * backoff_multiplier),
                        max_backoff,
                    )
            else:
                # No tasks executed — back off
                current_interval = min(
                    int(current_interval * backoff_multiplier),
                    max_backoff,
                )

        except Exception as e:
            logger.error(f"Cycle {cycle} error: {e}")
            current_interval = min(int(current_interval * backoff_multiplier), max_backoff)

        if once:
            break

        # Sleep with shutdown check
        sleep_until = time.time() + current_interval
        while time.time() < sleep_until and not _shutdown:
            time.sleep(5)


def run_loop() -> None:
    """Zero-arg continuous loop entry for daemon_supervisor (ADR-787 Part B).

    Mirrors main()'s default (no --config) path: resolve the config, honor the
    enabled flag, then run the daemon loop.
    """
    config_path = (
        resolve_user_data_base()
        / "plugins" / "core" / "skills" / "executor" / "data" / "tasks" / "config"
        / "continuous-execution.yaml"
    )
    config = load_config(config_path)
    if not config.get("enabled", True):
        logger.info("Continuous executor is disabled")
        return
    daemon_loop(config)


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuous executor daemon for Augur")
    parser.add_argument("--config", type=str, default="", help="Path to config YAML")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    args = parser.parse_args()

    # Load config
    if args.config:
        config_path = Path(args.config)
    else:
        config_path = (
            resolve_user_data_base()
            / "plugins"
            / "core"
            / "skills"
            / "executor"
            / "data"
            / "tasks"
            / "config"
            / "continuous-execution.yaml"
        )

    config = load_config(config_path)

    if not config.get("enabled", True):
        logger.info("Continuous executor is disabled")
        return 0

    daemon_loop(config, once=args.once)
    logger.info("Continuous executor stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

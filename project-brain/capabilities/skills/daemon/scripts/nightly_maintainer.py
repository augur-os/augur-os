
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
import os
import json
import shutil
import sys
import time
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, TimeoutExpired, run  # nosec B404


def _ensure_pythonpath(project_root: Path) -> None:
    """Match the repo MCP runtime contract for standalone script imports."""
    for candidate in (project_root, project_root / "src" / "mcp"):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)


# Add project root to sys.path
try:
    from src.config.paths import get_logs_dir, get_project_root, get_python_executable, get_runtime_dir, get_skill_root
    project_root = get_project_root()
    skill_root = get_skill_root("daemon")
except ImportError:
    # Fallback for standalone execution outside monorepo
    # This file is at: project-brain/capabilities/skills/daemon/scripts/nightly_maintainer.py
    skill_root = Path(__file__).resolve().parent.parent
    project_root = skill_root.parent.parent.parent  # fallback
    _ensure_pythonpath(project_root)
    from src.config.paths import get_logs_dir, get_project_root, get_python_executable, get_runtime_dir, get_skill_root

_ensure_pythonpath(project_root)

# Self-healing is handled by the unified daemon (unified_daemon.py)
# which manages this script as a child subprocess.
from src.logging import get_entity_logger  # noqa: E402
from src.mcp.augur_framework.tools.domain.sessions import prune_stale_sessions  # noqa: E402
from log_archive import archive_logs  # noqa: E402

logger = get_entity_logger("nightly_maintainer")


def _resolve_command(command: list[str]) -> list[str]:
    """Resolve executable to absolute path where possible."""
    if not command:
        raise ValueError("Command must not be empty")

    executable = command[0]
    if Path(executable).is_absolute():
        return command

    resolved = shutil.which(executable)
    if not resolved:
        return command

    return [resolved, *command[1:]]


def _run_command(command: list[str], **kwargs: object) -> CompletedProcess:
    """Run subprocess command with resolved executable path."""
    return run(_resolve_command(command), **kwargs)  # nosec B603


def write_health_check(start_time: float, success: bool, error: str = None):
    """Write operational health status."""
    stats_dir = get_runtime_dir() / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)

    status_file = stats_dir / "maintenance_status.json"
    duration = (time.time() - start_time) * 1000

    status = {
        "timestamp": datetime.now().isoformat(),
        "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "success": success,
        "duration_ms": int(duration),
        "error": error,
    }

    with open(status_file, "w") as f:
        json.dump(status, f, indent=2)


def generate_analytics(log_file: Path):
    """Generate aggregated usage stats for the day."""
    if not log_file.exists():
        return

    logger.info("Generating Analytics...")

    stats = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_requests": 0,
        "total_cost": 0.0,
        "total_tokens": 0,
        "errors": 0,
        "by_provider": defaultdict(lambda: {"cost": 0.0, "tokens": 0, "requests": 0}),
        "by_model": defaultdict(lambda: {"cost": 0.0, "tokens": 0, "requests": 0}),
    }

    try:
        with open(log_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)

                    cost = entry.get("cost", 0.0)
                    tokens = entry.get("total_tokens", 0)
                    provider = entry.get("provider", "unknown")
                    model = entry.get("model", "unknown")

                    stats["total_requests"] += 1
                    stats["total_cost"] += cost
                    stats["total_tokens"] += tokens

                    if not entry.get("success", True):
                        stats["errors"] += 1

                    # Provider Stats
                    stats["by_provider"][provider]["cost"] += cost
                    stats["by_provider"][provider]["tokens"] += tokens
                    stats["by_provider"][provider]["requests"] += 1

                    # Model Stats
                    stats["by_model"][model]["cost"] += cost
                    stats["by_model"][model]["tokens"] += tokens
                    stats["by_model"][model]["requests"] += 1

                except (json.JSONDecodeError, TypeError, ValueError):
                    continue

        # Write Summary
        stats_dir = get_runtime_dir() / "stats"
        stats_dir.mkdir(parents=True, exist_ok=True)
        summary_file = stats_dir / "usage_summary.json"

        with open(summary_file, "w") as f:
            json.dump(stats, f, indent=2)

        logger.info(f"Analytics Generated: ${stats['total_cost']:.4f} / {stats['total_tokens']} tokens")

    except Exception as e:
        logger.error(f"Analytics Failed: {e}")
        raise e


def run_ingestion_pipelines(project_root_path: Path) -> None:
    """Run backlog ingestion pipelines for self-improvement and analyst logs."""
    logger.info(
        "Skipping advisor ingestion pipelines: advisor is staged/draft-only and has no active project-brain runner"
    )


def run_memory_sync(project_root_path: Path) -> None:
    """Run memory sync to curate session memory and propose learned rules (ADR-029)."""

    memory_sync_script = project_root_path / ".github/scripts/memory_sync.py"

    if not memory_sync_script.exists():
        logger.warning(f"Skipping memory sync: script not found at {memory_sync_script}")
        return

    logger.info("Running memory sync (cleanup + curate + analyze)...")

    try:
        result = _run_command(
            [str(get_python_executable()), str(memory_sync_script), "--ci"],
            cwd=project_root_path,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info("Memory sync completed successfully")
            # Log summary if available
            for line in result.stdout.split("\n"):
                if "rule" in line.lower() or "pattern" in line.lower() or "✓" in line:
                    logger.info(f"  {line.strip()}")
        else:
            logger.warning(f"Memory sync returned non-zero: {result.returncode}")
            if result.stderr:
                logger.warning(f"  stderr: {result.stderr[:500]}")

    except Exception as e:
        logger.error(f"Memory sync failed: {e}")


def run_nightly_executor(project_root_path: Path) -> None:
    """Run the nightly backlog executor to process autonomous tasks."""

    executor_script = project_root_path / "project-brain" / "capabilities" / "skills" / "platform-admin" / "scripts" / "nightly_executor.py"
    config_path = get_runtime_dir() / "agent-tasks" / "tasks" / "config" / "nightly-execution.yaml"

    if not executor_script.exists():
        logger.warning(f"Skipping nightly executor: script not found at {executor_script}")
        return

    if not config_path.exists():
        logger.warning(f"Skipping nightly executor: config not found at {config_path}")
        return

    logger.info("Running nightly backlog executor...")

    try:
        # Add the scripts directory to PYTHONPATH so task_utils can be imported
        env = os.environ.copy()
        scripts_dir = str(executor_script.parent)
        env["PYTHONPATH"] = f"{scripts_dir}:{env.get('PYTHONPATH', '')}"

        result = _run_command(
            [str(get_python_executable()), str(executor_script), "--config", str(config_path)],
            cwd=project_root_path,
            capture_output=True,
            text=True,
            env=env,
            timeout=7200,  # 2 hour timeout for task execution
        )

        if result.returncode == 0:
            logger.info("Nightly executor completed successfully")
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    logger.info(f"  {line.strip()}")
        else:
            logger.warning(f"Nightly executor returned non-zero: {result.returncode}")
            if result.stderr:
                logger.warning(f"  stderr: {result.stderr[:500]}")

    except TimeoutExpired:
        logger.warning("Nightly executor timed out after 2 hours")
    except Exception as e:
        logger.error(f"Nightly executor failed: {e}")


def compact_performance_ledger():
    """Roll old agent performance records into aggregates (ADR-460)."""
    try:
        from src.lib.runtime.performance_ledger import compact
        removed = compact(max_age_days=30)
        logger.info("Performance ledger: compacted %d old records", removed)
    except Exception as e:
        logger.warning("Performance ledger compaction failed: %s", e)


def check_external_repo_updates():
    """Check GitHub repos in install registry for updates."""
    import yaml

    # Add import skill's lib to path
    lib_dir = str(Path(__file__).resolve().parent.parent.parent / "import" / "augur" / "lib")
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)

    from update_checker import check_github_update

    # Read registry
    registry_path = Path(__file__).resolve().parent.parent.parent / "import" / "scripts" / "data" / "registry.yaml"
    if not registry_path.is_file():
        return {"checked": 0, "updates_available": 0}

    with open(registry_path) as f:
        registry = yaml.safe_load(f) or {}

    entries = registry.get("entries", [])
    if not isinstance(entries, list):
        return {"checked": 0, "updates_available": 0}

    checked = 0
    updates = 0
    for entry in entries:
        source_url = entry.get("source_url", "")
        commit = entry.get("installed_commit", "")
        if not source_url or not commit or "github.com" not in source_url:
            continue

        result = check_github_update(source_url, commit)
        checked += 1
        if result.get("update_available"):
            updates += 1
            # Update the registry entry with latest check
            entry["latest_upstream_commit"] = result.get("latest_commit", "")
            entry["update_available"] = True

    # Write back if any updates found
    if updates > 0:
        with open(registry_path, "w") as f:
            yaml.dump(registry, f, default_flow_style=False, sort_keys=False)

    return {"checked": checked, "updates_available": updates}


# regenerate_indexes() removed — absorbed into reindex-project
# (scripts/ops/project_index.py) which runs as a nightly auto-command.
# See ADR-180 consolidation.


def main():
    start_time = time.time()
    logger.info("Starting Nightly Maintenance...")

    try:
        logs_dir = get_logs_dir()
        llm_logs = logs_dir / "llm_logs.jsonl"

        # 1. Generate Analytics (Read)
        generate_analytics(llm_logs)

        # 2. Archive & Rotate (Write/Delete)
        archive_logs(llm_logs)

        # 3. Backlog ingestion pipelines
        run_ingestion_pipelines(project_root)

        # 4. Memory sync (ADR-029: curate daily logs, propose rules)
        run_memory_sync(project_root)

        # 5. Execute backlog tasks (nightly autonomous execution)
        run_nightly_executor(project_root)

        # 6. Prune stale MCP session files (ADR-254 safety net)
        sessions_dir = get_runtime_dir() / "sessions"
        pruned = prune_stale_sessions(sessions_dir)
        if pruned:
            logger.info(f"Pruned {pruned} stale session file(s)")

        # 7. Compact performance ledger (ADR-460)
        compact_performance_ledger()

        # 8. Reference index regeneration moved to reindex-project (ADR-180)

        # 9. Check external skill repos for upstream updates
        try:
            update_result = check_external_repo_updates()
            if update_result["checked"] > 0:
                logger.info(
                    "External repo update check: %d checked, %d updates available",
                    update_result["checked"],
                    update_result["updates_available"],
                )
        except Exception as e:
            logger.warning("External repo update check failed: %s", e)

        # 10. Success Health Check
        write_health_check(start_time, True)
        logger.info("Maintenance Complete.")

    except Exception as e:
        logger.error(f"Critical Failure: {e}")
        write_health_check(start_time, False, str(e))
        sys.exit(1)


def sync_to_cloud():
    """Commit and push generated stats to the data repository."""
    from src.config import paths

    # We use paths.get_project_root() to locate the repo root
    repo_root = paths.get_project_root()
    runtime_stats_dir = get_runtime_dir() / "stats"
    stats_dir = str(runtime_stats_dir.relative_to(repo_root))

    logger.info("Syncing stats to cloud...")

    try:
        # Check if there are changes
        _run_command(["git", "add", stats_dir], cwd=repo_root, check=True, capture_output=True)

        status = _run_command(["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True)

        if not status.stdout.strip():
            logger.info("No changes to sync.")
            return

        # Commit
        _run_command(
            ["git", "commit", "-m", "chore(stats): update nightly intelligence summary"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )

        # Push
        _run_command(["git", "push"], cwd=repo_root, check=True, capture_output=True)
        logger.info("Successfully pushed stats to cloud.")

    except CalledProcessError as e:
        logger.error(f"Failed to sync to cloud: {e}")
        if e.stderr:
            logger.error(f"Git error: {e.stderr.decode()}")
    except Exception as e:
        logger.error(f"Sync failed: {e}")


if __name__ == "__main__":
    main()
    sync_to_cloud()

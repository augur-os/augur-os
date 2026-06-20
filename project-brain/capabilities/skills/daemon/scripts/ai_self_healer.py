#!/usr/bin/env python3
"""
AI Self-Healing Service for Augur (ADR-076).

Monitors runtime logs for errors, classifies severity via LLM,
and auto-fixes critical/high/medium issues using the /debug protocol.
Only low-severity issues are deferred to TODO markers.

Pipeline:
  scan (ripgrep) -> dedup (registry) -> classify (LLM) -> route -> fix | TODO

Usage:
    python3 ai_self_healer.py --loop      # Daemon mode (continuous)
    python3 ai_self_healer.py --scan      # One-shot scan
    python3 ai_self_healer.py --status    # Show registry stats
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    fobj = kwargs.get("file", sys.stdout)
    fobj.write(sep.join(str(arg) for arg in args) + str(end))


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT SETUP
# ═══════════════════════════════════════════════════════════════════════════════

from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

# Ensure self_heal package is importable from the scripts directory
_scripts_dir = str(Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

try:
    from src.logging import get_entity_logger
except ImportError:
    import logging as _logging

    def get_entity_logger(name: str) -> _logging.Logger:
        lg = _logging.getLogger(name)
        if not lg.handlers:
            h = _logging.StreamHandler()
            h.setFormatter(_logging.Formatter("%(levelname)s - %(message)s"))
            lg.addHandler(h)
            lg.setLevel(_logging.INFO)
        return lg


from src.config.paths import get_config_dir, get_logs_dir, get_runtime_dir

try:
    from notification_service import NotificationService
except ImportError:
    try:
        _ns_path = str(Path(__file__).resolve().parent)
        if _ns_path not in sys.path:
            sys.path.insert(0, _ns_path)
        from notification_service import NotificationService
    except ImportError:
        NotificationService = None  # type: ignore[assignment,misc]


logger = get_entity_logger("ai_self_healer")


@contextmanager
def _job_ledger_run(**kwargs: Any):
    """Best-effort ledger wrapper. A ledger failure never blocks self-heal."""
    try:
        from job_ledger.ledger import run as ledger_run
    except Exception as exc:  # noqa: BLE001
        logger.warning("job ledger unavailable: %s", exc)
        yield None
        return
    with ledger_run(**kwargs) as job:
        yield job


def _job_ledger_timeout_s(config: dict[str, Any]) -> int:
    fix_cfg = config.get("fix", {}) if isinstance(config.get("fix"), dict) else {}
    profiles = fix_cfg.get("severity_profiles", {})
    timeouts: list[int] = []
    if isinstance(profiles, dict):
        for profile in profiles.values():
            if isinstance(profile, dict):
                try:
                    timeouts.append(int(profile.get("timeout_s", 0)))
                except (TypeError, ValueError):
                    pass
    max_timeout = max(timeouts) if timeouts else 600
    try:
        attempts = max(1, int(fix_cfg.get("max_fix_attempts", 3)))
    except (TypeError, ValueError):
        attempts = 3
    return max(1800, max_timeout * attempts)

# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════

RUNTIME_DIR = get_runtime_dir()
LOGS_DIR = get_logs_dir()
REGISTRY_FILE = RUNTIME_DIR / "self_heal_registry.json"
TECH_DEBT_FILE = RUNTIME_DIR / "tech_debt.md"
FIX_LOCK_FILE = RUNTIME_DIR / "locks" / "self_heal_fix.lock"

CRITICAL_DIR = RUNTIME_DIR / "self_heal" / "critical"
SCAN_TARGETS_STATE = RUNTIME_DIR / "self_heal" / "scan_targets.yaml"

PLUGIN_CONFIG_CANDIDATES = (
    Path(__file__).resolve().parent.parent / "config" / "self_heal.yaml",
    Path(__file__).resolve().parent.parent / "augur" / "config" / "self_heal.yaml",
)
PLUGIN_CONFIG = next(
    (candidate for candidate in PLUGIN_CONFIG_CANDIDATES if candidate.exists()),
    PLUGIN_CONFIG_CANDIDATES[0],
)
USER_CONFIG = get_config_dir() / "system" / "self_heal.yaml"
LLM_CONFIG = get_config_dir() / "system" / "llm.yaml"

DEFAULT_SCAN_INTERVAL = 300  # 5 minutes


def _is_test_mode() -> bool:
    """Return True when running under test mode."""
    return os.environ.get("AUGUR_TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ErrorFinding:
    """A single error found during scanning."""

    dedup_key: str
    message: str
    file: str
    line: Optional[int] = None
    stack_trace: Optional[str] = None
    timestamp: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RegistryEntry:
    """Tracked issue in the self-heal registry."""

    dedup_key: str
    message: str
    file: str
    severity: str = "unclassified"
    category: str = "integration"
    status: str = "new"  # new|classifying|fixing|fixed|failed|abandoned
    first_seen: str = ""
    last_seen: str = ""
    occurrences: int = 1
    fix_attempts: int = 0
    fix_result: Optional[str] = None
    fix_commit: Optional[str] = None
    suggested_approach: Optional[str] = None
    stack_trace: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RegistryEntry":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        # Ensure required positional fields have values (guard against
        # corrupt / legacy registry JSON missing these keys).
        filtered.setdefault("dedup_key", "unknown")
        filtered.setdefault("message", "")
        filtered.setdefault("file", "unknown")
        return cls(**filtered)


# ═══════════════════════════════════════════════════════════════════════════════
# SUB-MODULE IMPORTS (delegated logic)
# ═══════════════════════════════════════════════════════════════════════════════

from self_heal.classifier import (  # noqa: E402
    match_shell_action,
    pre_classify,
    classify_issue,
    resolve_cli,
    _parse_llm_json,  # noqa: F401 -- re-exported for tests
)

from self_heal.router import (  # noqa: E402
    route_issue,
)

from self_heal.escalation import (  # noqa: E402
    deduplicate_findings,
    create_todo_marker,
    create_critical_item,
    format_fix_prompt,
    _format_marker,  # noqa: F401 -- re-exported for tests
)

from self_heal.fixers import (  # noqa: E402
    acquire_fix_lock,
    release_fix_lock,
    invoke_headless_fix,
    execute_shell_action,
    _gather_log_context,  # noqa: F401 -- re-exported for tests
    _get_severity_profile,  # noqa: F401 -- re-exported for tests
    _get_head_hash,  # noqa: F401 -- re-exported for tests
    _check_for_fix_commit,  # noqa: F401 -- re-exported for tests
)

# Scanner, registry, and pipeline sub-modules
from self_heal.scanner import (  # noqa: E402
    _filter_self_poison,
    _filter_stale_logs,
    _load_watermarks,  # noqa: F401 -- re-exported for tests and module callers
    _save_watermarks_atomic,  # noqa: F401 -- re-exported for tests and module callers
    _resolve_scan_target_path,
    _to_state_label,
    _extract_message,
    _is_info_level_log,
    _is_mock_client_line,
    _generate_dedup_key,
    _normalize_message_for_dedup,
    _canonical_source_for_dedup,
    scan_logs,
    check_resource_health,
    discover_untracked_logs,
    persist_discovered_targets,
)

from self_heal.registry import (  # noqa: E402
    load_registry,
    save_registry,
    compact_dismissed_registry_entries,
)

from self_heal.pipeline import (  # noqa: E402
    _notify,  # noqa: F401 -- re-exported for tests and module callers
    run_pipeline,
)

from self_heal.patterns import MAX_NEW_LINES_PER_FILE, MAX_MESSAGE_LENGTH, WATERMARK_FILENAME  # noqa: E402,F401

_WATERMARK_FILE = RUNTIME_DIR / WATERMARK_FILENAME


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════


def load_config() -> dict:
    """Load self-heal config with user overrides.

    discovered_scan_targets live in the state dir (ADR-466), not in config.
    """
    import yaml

    config: dict = {}

    # Load plugin defaults
    if PLUGIN_CONFIG.exists():
        try:
            config = yaml.safe_load(PLUGIN_CONFIG.read_text()) or {}
        except Exception as e:
            logger.warning(f"Failed to load plugin config: {e}")

    # Overlay user config
    if USER_CONFIG.exists():
        try:
            user = yaml.safe_load(USER_CONFIG.read_text()) or {}
            # Strip discovered_scan_targets from user config — they belong in state (ADR-466)
            user.pop("discovered_scan_targets", None)
            config = _deep_merge(config, user)
        except Exception as e:
            logger.warning(f"Failed to load user config: {e}")

    # Load discovered scan targets from state dir (ADR-466)
    if SCAN_TARGETS_STATE.exists():
        try:
            state = yaml.safe_load(SCAN_TARGETS_STATE.read_text()) or {}
            targets = state.get("discovered_scan_targets", [])
            if targets:
                config["discovered_scan_targets"] = targets
        except Exception as e:
            logger.warning(f"Failed to load scan targets state: {e}")

    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge override into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def check_mcp_config_health() -> list[ErrorFinding]:
    """Return self-heal findings for stale or broken MCP client configs."""
    from ai_self_healer import ErrorFinding

    try:
        mcp_src = PROJECT_ROOT / "src" / "mcp"
        if str(mcp_src) not in sys.path:
            sys.path.insert(0, str(mcp_src))

        from src.mcp.augur_framework.tools.infrastructure.mcp_diagnostics import (
            collect_mcp_config_issues,
        )

        _, issues = collect_mcp_config_issues(project_root=PROJECT_ROOT)
    except Exception as exc:
        logger.debug(f"Skipping MCP config health scan: {exc}")
        return []

    findings: list[ErrorFinding] = []
    now = datetime.now().isoformat()

    for issue in issues:
        client_label = issue.get("clientLabel", issue.get("clientKey", "unknown client"))
        config_path = issue.get("configPath", "unknown config")
        if issue.get("kind") == "stale":
            message = (
                f"mcp_config:stale_client_config -- {client_label} points to a missing Augur root "
                f"in {config_path}. Run scripts/configure_mcp.py --auto."
            )
        else:
            error = issue.get("error", "parse error")
            message = (
                f"mcp_config:parse_error -- {client_label} config at {config_path} is invalid: "
                f"{error}"
            )

        finding = ErrorFinding(
            dedup_key=_generate_dedup_key(message, config_path),
            message=message,
            file=f"mcp-config:{issue.get('clientKey', 'unknown')}",
            timestamp=now,
        )
        finding.severity = "high"
        finding.category = "infrastructure"
        findings.append(finding)

    return findings


def _project_python_path(project_root: Path) -> Path:
    if sys.platform == "win32":
        return project_root / ".venv" / "Scripts" / "python.exe"
    return project_root / ".venv" / "bin" / "python3"


def check_runtime_prerequisite_health() -> list[ErrorFinding]:
    """Return findings for generated runtime prerequisites self-heal can recreate."""
    from ai_self_healer import ErrorFinding

    findings: list[ErrorFinding] = []
    now = datetime.now().isoformat()

    if (PROJECT_ROOT / "pyproject.toml").is_file():
        python_path = _project_python_path(PROJECT_ROOT)
        if not python_path.is_file():
            message = (
                "mcp_runtime:project_python_missing -- "
                f"No such file or directory: {python_path}"
            )
            finding = ErrorFinding(
                dedup_key=_generate_dedup_key(message, "runtime-prereq:mcp-python"),
                message=message,
                file="runtime-prereq:mcp-python",
                timestamp=now,
            )
            finding.severity = "high"
            finding.category = "infrastructure"
            findings.append(finding)

    dashboard_root = PROJECT_ROOT / "apps" / "dashboard"
    esbuild_path = dashboard_root / "node_modules" / "esbuild"
    if (dashboard_root / "package.json").is_file() and not esbuild_path.exists():
        message = (
            "dashboard_runtime:dependency_missing -- "
            "Cannot find package 'esbuild' imported from apps/dashboard/scripts/build-scripts.mjs"
        )
        finding = ErrorFinding(
            dedup_key=_generate_dedup_key(message, "runtime-prereq:dashboard"),
            message=message,
            file="runtime-prereq:dashboard",
            timestamp=now,
        )
        finding.severity = "high"
        finding.category = "infrastructure"
        findings.append(finding)

    return findings


def scan_runtime(config: dict) -> list:
    """Top-level runtime scan wrapper.

    Preserves the public ai_self_healer module contract so callers and tests can
    patch `ai_self_healer.scan_logs` without reaching into scanner internals.
    """
    targets = list(config.get("scan_targets", []))
    discovered = config.get("discovered_scan_targets", [])
    if discovered:
        targets.extend(discovered)
    if not targets:
        return []

    max_age = config.get("max_log_age_hours", 24)
    if max_age > 0:
        targets = _filter_stale_logs(targets, max_age)
        if not targets:
            return []

    findings, watermarks = scan_logs(targets)
    findings = _filter_self_poison(findings)
    _save_watermarks_atomic(watermarks)
    findings.extend(check_mcp_config_health())
    findings.extend(check_runtime_prerequisite_health())
    return findings


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════


def cmd_scan() -> int:
    """One-shot scan and process."""
    config = load_config()
    with _job_ledger_run(
        kind="heal",
        name="ai-self-healer",
        args={"mode": "scan"},
        timeout_s=_job_ledger_timeout_s(config),
    ) as _job:
        if _job is not None:
            _job.phase("dispatch")
        summary = run_pipeline(config)

    _out("AI Self-Healer -- Scan Complete")
    _out("=" * 40)
    for key, value in summary.items():
        _out(f"  {key}: {value}")
    return 0


def cmd_status() -> int:
    """Show registry statistics."""
    registry = load_registry()

    if not registry:
        _out("No issues in registry.")
        return 0

    by_status: dict[str, int] = {}
    by_severity: dict[str, int] = {}

    for entry in registry.values():
        by_status[entry.status] = by_status.get(entry.status, 0) + 1
        by_severity[entry.severity] = by_severity.get(entry.severity, 0) + 1

    _out("AI Self-Healer Registry")
    _out("=" * 40)
    _out(f"  Total issues: {len(registry)}")
    _out()
    _out("  By status:")
    for status, count in sorted(by_status.items()):
        _out(f"    {status}: {count}")
    _out()
    _out("  By severity:")
    for severity, count in sorted(by_severity.items()):
        _out(f"    {severity}: {count}")

    return 0


def cmd_discover() -> int:
    """CLI: discover untracked log files and persist them."""
    config = load_config()
    new_targets = discover_untracked_logs(config)
    if not new_targets:
        _out("No untracked log files with errors found.")
        return 0
    added = persist_discovered_targets(new_targets, config)
    _out(f"Discovered {added} new log file(s) for tracking:")
    for t in new_targets:
        _out(f"  {t['path']}  ({len(t['patterns'])} patterns)")
    return 0


def monitor_loop(config: dict) -> None:
    """Continuous monitoring loop."""
    interval = config.get("scan_interval_minutes", 5) * 60
    logger.info(f"AI Self-Healer starting (interval: {interval}s)")

    while True:
        try:
            with _job_ledger_run(
                kind="heal",
                name="ai-self-healer",
                args={"mode": "loop"},
                timeout_s=_job_ledger_timeout_s(config),
            ) as _job:
                if _job is not None:
                    _job.phase("dispatch")
                summary = run_pipeline(config)
            activity = (
                summary.get("new_issues", 0)
                + summary.get("backlog_picked", 0)
                + summary.get("fixes_attempted", 0)
            )
            if activity > 0:
                logger.info(
                    f"Pipeline: {summary.get('new_issues', 0)} new, "
                    f"{summary.get('backlog_picked', 0)} backlog, "
                    f"{summary.get('fixes_attempted', 0)} fix attempts "
                    f"({summary.get('fixes_succeeded', 0)} succeeded), "
                    f"{summary.get('dismissed', 0)} dismissed, "
                    f"{summary.get('items_created', 0)} critical items, "
                    f"{summary.get('todos_created', 0)} TODOs"
                )
        except Exception as e:
            logger.error(f"Pipeline error: {e}")

        time.sleep(interval)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="AI Self-Healing Service (ADR-076)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--loop", action="store_true", help="Continuous daemon mode")
    group.add_argument("--scan", action="store_true", help="One-shot scan")
    group.add_argument("--discover", action="store_true", help="Discover untracked log files")
    group.add_argument("--status", action="store_true", help="Show registry stats")
    args = parser.parse_args()

    if args.status:
        return cmd_status()

    if args.discover:
        return cmd_discover()

    if args.loop:
        config = load_config()
        monitor_loop(config)
        return 0

    # Default: one-shot scan
    return cmd_scan()


if __name__ == "__main__":
    sys.exit(main())

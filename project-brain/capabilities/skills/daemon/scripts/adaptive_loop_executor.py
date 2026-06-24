#!/usr/bin/env python3
"""Adaptive Loop Engine -- daemon child service.

Runs as a persistent child of unified_daemon.py.
Orchestrates all adaptive loops on their configured schedules.
"""
# TODO_CLEANUP: This file is 807 lines — consider splitting into smaller modules
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent

try:
    from bootstrap_paths import ensure_project_paths, find_project_root
except ImportError:
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    from bootstrap_paths import ensure_project_paths, find_project_root


def _bootstrap_project_root() -> Path:
    """Find the active repo/worktree root before importing project modules.

    When PYTHONPATH already contains another Augur checkout, importing src.*
    before prepending the current worktree root can silently mix code from two
    different checkouts. Resolve the current worktree first and put it at the
    front of sys.path so every subsequent import comes from the same tree.
    """
    if os.environ.get("AUGUR_ROOT"):
        return find_project_root(__file__)

    candidates: list[Path] = []

    try:
        cwd = Path.cwd().resolve()
    except OSError:
        cwd = None

    if cwd is not None:
        candidates.extend((cwd, *cwd.parents))

    candidates.extend((find_project_root(__file__), *SCRIPTS_DIR.parents))

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (
            (candidate / "pyproject.toml").is_file()
            and (
                (candidate / "src" / "config" / "paths.py").is_file()
                or (candidate / "config" / "system").is_dir()
            )
        ):
            return candidate

    return find_project_root(__file__)


BOOTSTRAP_ROOT = ensure_project_paths(__file__)

try:
    from src.config.paths import (
        get_project_root,
        get_runtime_dir,
        get_config_dir,
        get_skill_root,
        invalidate_project_cache,
    )
    PROJECT_ROOT = get_project_root()
    try:
        SKILL_ROOT = get_skill_root("daemon")
    except ValueError:
        SKILL_ROOT = SCRIPTS_DIR.parent
except ImportError:
    # Fallback for standalone execution outside monorepo
    # This file is at: project-brain/capabilities/skills/daemon/scripts/adaptive_loop_executor.py
    SKILL_ROOT = SCRIPTS_DIR.parent
    PROJECT_ROOT = BOOTSTRAP_ROOT
    from src.config.paths import (
        get_project_root,
        get_runtime_dir,
        get_config_dir,
        get_skill_root,
        invalidate_project_cache,
    )

sys.path.insert(0, str(SCRIPTS_DIR))

import yaml  # noqa: E402
from src.logging import get_entity_logger  # noqa: E402

from adaptive.engine import AdaptiveLoopEngine, CycleReport  # noqa: E402
from adaptive.codex_schedule_manifest import (  # noqa: E402
    build_codex_schedule_manifest_from_project,
    detect_codex_schedule_states,
)
from adaptive.discovery import discover_auto_commands  # noqa: E402
from adaptive.evolve_queue import format_pending_report  # noqa: E402
from adaptive.adr_writer import create_centralized_adr  # noqa: E402
from adaptive.heal import (  # noqa: E402
    format_heal_fix_report,
    format_heal_report,
    heal_detect,
    heal_fix,
)
from adaptive.trust_state import CategoryState, LoopState  # noqa: E402
from adaptive.loop_reporter import (  # noqa: E402
    scan_pending_issues,
    print_pending_report,
    write_cli_metrics,
    run_evolve_phase,
    format_status,
)

# Backward-compatible aliases for tests that access private names
_scan_pending_issues = scan_pending_issues
_print_pending_report = print_pending_report
_write_cli_metrics = write_cli_metrics
_run_evolve_phase = run_evolve_phase
_create_centralized_adr = create_centralized_adr

logger = get_entity_logger("adaptive_loop_engine")

RUNNING = True


@contextmanager
def _job_ledger_run(**kwargs: Any):
    """Best-effort ledger wrapper. Import/write failures never block loop work."""
    try:
        from job_ledger.ledger import run as ledger_run
    except Exception as exc:  # noqa: BLE001
        logger.warning("job ledger unavailable: %s", exc)
        yield None
        return
    with ledger_run(**kwargs) as job:
        yield job


def _job_ledger_timeout_s(config: dict[str, Any]) -> int:
    engine_cfg = config.get("engine", {}) if isinstance(config.get("engine"), dict) else {}
    raw = engine_cfg.get("session_timeout_minutes", 30)
    try:
        return max(1, int(raw)) * 60
    except (TypeError, ValueError):
        return 1800


def _configure_windows_stdio() -> None:
    """Keep Unicode report tables printable from redirected Windows consoles."""
    if os.name != "nt":
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def signal_handler(sig, frame):
    global RUNNING
    logger.info(f"Received signal {sig}, shutting down")
    RUNNING = False


def load_config() -> dict:
    config_path = get_config_dir() / "system" / "adaptive_loops.yaml"
    if not config_path.exists():
        logger.warning(f"Config not found at {config_path}, using defaults")
        return {"engine": {"enabled": False}, "loops": {}}
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def _annotate_orchestrator_runner_markers(registry: dict[str, Any]) -> None:
    """Annotate discovered entries from command-doc runner frontmatter."""
    for entry in registry.values():
        runner = _read_command_runner(entry)
        if runner:
            setattr(entry, "runner", runner)


def _read_command_runner(entry: Any) -> str:
    plugin_root = getattr(entry, "plugin_root", None)
    command_name = getattr(entry, "name", "")
    if plugin_root is None or not command_name:
        return ""
    command_doc = Path(plugin_root) / "commands" / f"{command_name}.md"
    frontmatter = _read_markdown_frontmatter(command_doc)
    value = frontmatter.get("x-augur-runner")
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _read_markdown_frontmatter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    try:
        parsed = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def resolve_cli() -> str | None:
    """Find available CLI binary."""
    from src.lib.llm_retry import resolve_cli as _canonical_resolve_cli
    return _canonical_resolve_cli()


def _resolve_execution_project_root(
    args: argparse.Namespace,
    cwd: Path | None = None,
) -> Path:
    """Honor the current worktree for direct CLI runs.

    Codex shells often inherit ``AUGUR_ROOT`` pointing at the main checkout.
    For slash-command style invocations from a git worktree, that causes
    adaptive loops to apply fixes and commits to the wrong repository.

    Daemon ``--loop`` mode keeps the inherited root because it is launched as a
    background service outside an interactive repo worktree.
    """
    if args.loop:
        return get_project_root()

    candidate = (cwd or Path.cwd()).resolve()
    if not ((candidate / ".git").exists() and (candidate / "project.yaml").is_file()):
        return get_project_root()

    if Path(get_project_root()).resolve() == candidate:
        return candidate

    os.environ["AUGUR_ROOT"] = str(candidate)
    invalidate_project_cache()
    return candidate


def _normalize_cli_args(raw_args: list[str]) -> list[str]:
    """Normalize slash-command style args to flag-style argparse args.

    Supports both:
      - Flag style: --run self-heal, --run-all, --pending, --create-adr
      - Subcommand style: run self-heal, run --all, pending, create-adr, status
    """
    if not raw_args:
        return raw_args

    head = raw_args[0]
    tail = raw_args[1:]

    if head == "status":
        return ["--status", *tail]
    if head == "pending":
        return ["--pending", *tail]
    if head == "report":
        return ["--report", *tail]
    if head == "heal":
        return ["--heal", *tail]
    if head in ("create-adr", "create_adr"):
        return ["--create-adr", *tail]
    if head in ("run-all", "run_all"):
        return ["--run-all", *tail]
    if head == "run":
        if tail and tail[0] in ("--all", "all"):
            rest = tail[1:]
            # Handle bare integer as --cycles N (e.g., "run --all 3")
            if rest and rest[0].isdigit():
                return ["--run-all", "--cycles", rest[0], *rest[1:]]
            return ["--run-all", *rest]
        if tail:
            return ["--run", tail[0], *tail[1:]]
    if head in ("evolve-pending", "evolve_pending"):
        return ["--evolve-pending", *tail]
    if head == "local":
        return ["--local", *tail]
    if head == "all":
        # Shortcut: "all" = "run --all --cycles 10"
        return ["--run-all", "--cycles", "10", *tail]
    if head == "registry":
        return ["--registry", *tail]
    if head == "enable":
        return ["--enable", *tail]
    if head == "disable":
        return ["--disable", *tail]
    if head == "configure":
        return ["--configure", *tail]
    if head == "promote":
        return ["--promote", *tail]
    if head == "diagnose":
        return ["--diagnose", *tail]
    if head == "history":
        return ["--history", *tail]
    if head == "reset":
        return ["--reset", *tail]
    if head == "manifest":
        return ["--manifest", *tail]

    # Pass through --evolve, --cycles, --force anywhere in the arg list
    return raw_args


def _registration_should_persist(args: argparse.Namespace) -> bool:
    """Return whether discovery registration may update trust_state.json."""
    if args.loop or args.run or args.run_all:
        return True
    if args.enable or args.disable or args.configure or args.promote or args.reset:
        return True
    if args.heal and args.fix:
        return True

    one_shot = any(
        (
            args.status,
            args.pending,
            args.report,
            args.heal,
            args.create_adr,
            args.evolve_pending,
            args.registry,
        )
    )
    return not one_shot


def _current_repo_root() -> Path:
    """Resolve the repo root for the checkout containing this script."""
    return find_project_root(__file__)


def _rebind_repo_env_for_direct_cli(loop_mode: bool) -> Path:
    """Force direct CLI runs to operate on the current checkout, not inherited main."""
    repo_root = _current_repo_root()
    if loop_mode:
        return repo_root

    for env_name in ("AUGUR_ROOT", "AUGUR_CORE", "AUGUR_REPO"):
        current = os.environ.get(env_name)
        if current and Path(current).resolve() != repo_root:
            logger.info("Rebinding %s from %s to %s", env_name, current, repo_root)
        os.environ[env_name] = str(repo_root)
    return repo_root


def _resolve_checkout_root_from_cwd(cwd: Path | None = None) -> Path:
    """Resolve the checkout root for the current working directory.

    Walk upward from the active cwd so direct CLI invocations from nested
    subdirectories still bind to the actual checkout root instead of relying
    on inherited project-root state.
    """
    candidate = (cwd or Path.cwd()).resolve()
    for path in (candidate, *candidate.parents):
        if (path / "project.yaml").is_file():
            return path
    return get_project_root()


def _enforce_run_all_worktree(project_root: Path) -> None:
    """Prevent broad multi-loop runs from mutating the main checkout."""
    git_entry = project_root / ".git"
    if git_entry.is_file():
        return
    raise SystemExit(
        "`/a-loops run --all` requires an isolated git worktree. "
        "Create or reuse a routines-YYYY-MM-DD worktree, then run the command there."
    )


def _consume_and_materialize_post_exec_events(engine: AdaptiveLoopEngine) -> int:
    """Move queued command events into execution logs for drain-capable loops."""
    events = engine.consume_post_exec_queue()
    engine.materialize_post_exec_events(events)
    return len(events)


def _run_nightly_maintenance(engine: AdaptiveLoopEngine, config: dict[str, Any]) -> None:
    """Run the former daemon-owned nightly maintenance under an explicit Codex job."""
    logger.info("Generating self-heal validation report")
    logger.info("Morning report generated:\n%s", engine.generate_report())
    retention_days = config.get("engine", {}).get("history_retention_days", 30)
    cleaned = engine.journal_reader.cleanup(retention_days)
    logger.info("Ledger history cleanup removed %d stale entr%s", cleaned, "y" if cleaned == 1 else "ies")


def _run_split_auto_loop(
    engine: AdaptiveLoopEngine,
    loop_name: str,
    *,
    include_triggers: set[str] | None = None,
    trigger_filter: str | None = None,
) -> tuple[CycleReport, list[Any]]:
    """Run an auto loop against an explicit trigger subset."""
    entries = getattr(engine, "_auto_commands", {}).get(loop_name)
    if include_triggers is None or entries is None:
        report = engine.run_auto_cycle(loop_name, trigger_filter=trigger_filter)
        return report, getattr(report, "results", [])

    selected_entries = [entry for entry in entries if entry.trigger in include_triggers]
    original_entries = engine._auto_commands[loop_name]
    engine._auto_commands[loop_name] = selected_entries
    try:
        report = engine.run_auto_cycle(loop_name, trigger_filter=trigger_filter)
    finally:
        engine._auto_commands[loop_name] = original_entries
    return report, getattr(report, "results", [])


def _format_wiki_compile_handoff(report: CycleReport | None) -> str | None:
    """Return agent-mode wiki compile guidance for degraded wiki maintenance."""
    if report is None or report.loop_name != "knowledge-enrichment":
        return None

    relevant = []
    for category in getattr(report, "categories", []):
        text = f"{category.name} {category.action_summary}".lower()
        issue_count = (
            int(getattr(category, "issue_count", 0) or 0)
            + int(getattr(category, "actionable_count", 0) or 0)
            + int(getattr(category, "manual_count", 0) or 0)
            + int(getattr(category, "broken_count", 0) or 0)
        )
        if issue_count > 0 and ("wiki" in text or category.name == "auto-wiki-maintenance"):
            relevant.append(category)

    if not relevant:
        return None

    issue_total = sum(int(getattr(category, "issue_count", 0) or 0) for category in relevant)
    issue_text = f"{issue_total} issue(s)" if issue_total else "wiki quality findings"
    return "\n".join(
        [
            "",
            "Wiki Compile Handoff",
            f"- `knowledge-enrichment` found {issue_text} that need agent synthesis.",
            "- Run `/auto-wiki-maintenance --compile --cycles 5 --limit 25 --evolve` for bounded concept-first repair.",
            "- If the wiki needs a clean concept base, run `/auto-wiki-maintenance --reset --cycles 5 --limit 25 --evolve`.",
        ]
    )


JOURNAL_ENTRY_KEYS = (
    "loop",
    "action",
    "category",
    "result",
    "timestamp",
    "files",
    "commit",
    "error",
    "duration_ms",
)


def _known_loop_names(engine: AdaptiveLoopEngine) -> list[str]:
    return sorted(
        set(getattr(engine, "loops", {}).keys())
        | set(getattr(engine, "_auto_loop_names", set()))
    )


def _known_read_only_loop_names(
    engine: AdaptiveLoopEngine,
    journal_entries: list[dict[str, Any]] | None = None,
) -> list[str]:
    names = set(getattr(engine, "loops", {}).keys())
    names.update(getattr(engine, "_auto_loop_names", set()))
    ledger_loops = getattr(getattr(engine, "ledger", None), "_loops", {})
    if isinstance(ledger_loops, dict):
        names.update(ledger_loops.keys())
    for entry in journal_entries or []:
        loop_name = entry.get("loop")
        if loop_name:
            names.add(str(loop_name))
    return sorted(names)


def _require_loop(engine: AdaptiveLoopEngine, loop_name: str) -> str:
    valid = _known_loop_names(engine)
    if loop_name not in valid:
        valid_text = ", ".join(valid) if valid else "(none)"
        raise SystemExit(f"Unknown loop '{loop_name}'. Valid loops: {valid_text}")
    return loop_name


def _require_read_only_loop(
    engine: AdaptiveLoopEngine,
    loop_name: str,
    journal_entries: list[dict[str, Any]] | None = None,
) -> str:
    valid = _known_read_only_loop_names(engine, journal_entries)
    if loop_name not in valid:
        valid_text = ", ".join(valid) if valid else "(none)"
        raise SystemExit(f"Unknown loop '{loop_name}'. Valid loops: {valid_text}")
    return loop_name


def _require_category(engine: AdaptiveLoopEngine, loop_name: str, category: str) -> str:
    _require_loop(engine, loop_name)
    loop_state = engine.ledger.get_loop_state(loop_name)
    categories = getattr(loop_state, "categories", {}) or {}
    if category not in categories:
        valid = sorted(categories.keys())
        valid_text = ", ".join(valid) if valid else "(none)"
        raise SystemExit(
            f"Unknown category '{category}' for loop '{loop_name}'. "
            f"Valid categories: {valid_text}"
        )
    return category


def _journal_entry_to_dict(entry: Any) -> dict[str, Any]:
    if isinstance(entry, dict):
        raw = dict(entry)
    elif is_dataclass(entry):
        raw = asdict(entry)
    else:
        raw = {key: getattr(entry, key, None) for key in JOURNAL_ENTRY_KEYS}

    stable = {key: raw.get(key) for key in JOURNAL_ENTRY_KEYS if key in raw}
    for key in sorted(raw):
        if key not in stable:
            stable[key] = raw[key]
    return stable


def _format_diagnostics(report: dict[str, Any], loop_name: str | None = None) -> str:
    summary = report.get("summary", {})
    issues = list(report.get("issues", []))
    if loop_name is not None:
        issues = [issue for issue in issues if issue.get("loop") == loop_name]
        summary = {
            "total_issues": len(issues),
            "critical": sum(1 for issue in issues if issue.get("severity") == "critical"),
            "warning": sum(1 for issue in issues if issue.get("severity") == "warning"),
            "info": sum(1 for issue in issues if issue.get("severity") == "info"),
        }

    lines = [
        "Diagnostics summary: "
        f"total={summary.get('total_issues', 0)} "
        f"critical={summary.get('critical', 0)} "
        f"warning={summary.get('warning', 0)} "
        f"info={summary.get('info', 0)}"
    ]
    if not issues:
        lines.append("No diagnostic issues found.")
        return "\n".join(lines)

    for issue in issues:
        lines.append(
            " ".join(
                [
                    str(issue.get("severity", "info")),
                    str(issue.get("loop", "-")),
                    str(issue.get("category") or "-"),
                    str(issue.get("issue", "")),
                ]
            ).strip()
        )
        fix = issue.get("fix")
        if fix:
            lines.append(f"  fix: {fix}")
    return "\n".join(lines)


def _apply_dataclass_state(
    target: Any,
    data: dict[str, Any],
    *,
    skip: set[str] | None = None,
) -> None:
    skip = skip or set()
    for field in fields(target):
        if field.name in skip or field.name not in data:
            continue
        setattr(target, field.name, deepcopy(data[field.name]))


def _hydrate_persisted_dynamic_categories_for_read_only(
    engine: AdaptiveLoopEngine,
) -> None:
    """Load persisted ADR-200 categories without discovery, pruning, or saving."""
    ledger = getattr(engine, "ledger", None)
    state_file = getattr(ledger, "_state_file", None)
    loops = getattr(ledger, "_loops", None)
    if not isinstance(state_file, (str, Path)) or not isinstance(loops, dict):
        return

    path = Path(state_file)
    if not path.exists():
        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    persisted_loops = payload.get("loops", {})
    if not isinstance(persisted_loops, dict):
        return

    for loop_name, loop_data in persisted_loops.items():
        if not isinstance(loop_data, dict):
            continue
        loop_state = loops.get(loop_name)
        if loop_state is None:
            loop_state = LoopState()
            loops[loop_name] = loop_state
        _apply_dataclass_state(loop_state, loop_data, skip={"categories"})

        categories = loop_data.get("categories", {})
        if not isinstance(categories, dict):
            continue
        for category_name, category_data in categories.items():
            if not isinstance(category_data, dict):
                continue
            category_state = loop_state.categories.get(category_name)
            if category_state is None:
                category_state = CategoryState()
                loop_state.categories[category_name] = category_state
            _apply_dataclass_state(category_state, category_data)


def main(argv: list[str] | None = None):
    _configure_windows_stdio()
    cli_t0 = time.monotonic()
    parser = argparse.ArgumentParser(description="Adaptive Loop Engine")
    parser.add_argument("--loop", action="store_true", help="Run in daemon loop mode")
    parser.add_argument("--status", action="store_true", help="Print status and exit")
    run_group = parser.add_mutually_exclusive_group()
    run_group.add_argument(
        "--run",
        type=str,
        help="Run a single loop cycle by name and exit",
    )
    run_group.add_argument(
        "--run-all",
        action="store_true",
        help="Run one cycle for all loops and exit",
    )
    run_group.add_argument(
        "--pending",
        action="store_true",
        help="Scan all loops and print total pending issues/fixes",
    )
    run_group.add_argument(
        "--report",
        action="store_true",
        help="Print the executive adaptive loop report and exit",
    )
    run_group.add_argument(
        "--heal",
        action="store_true",
        help="Detect failed, idle, and trust-stuck categories and exit",
    )
    parser.add_argument(
        "--create-adr",
        action="store_true",
        help="Create a centralized ADR from pending issue scan results",
    )
    parser.add_argument(
        "--evolve",
        action="store_true",
        help="After --run-all, run git inspection and self-improvement analysis",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=1,
        help="Number of autonomous cycles for --run-all (default: 1)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --cycles, run all N cycles even if findings stabilize to 0",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="With --heal, investigate and attempt structural fixes",
    )
    parser.add_argument(
        "--drain",
        action="store_true",
        help="Run drain-only mode for drain-capable loops",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run validation-only mode for validation-capable loops",
    )
    parser.add_argument(
        "--evolve-pending",
        action="store_true",
        help="Show queued evolve improvements from ADR-458 remediation engine",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run with local Ollama backend instead of cloud AI client",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Window for report mode in days (default: 1)",
    )
    parser.add_argument(
        "--registry",
        action="store_true",
        help="Show the full loop registry and exit",
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Print the Codex migration manifest and exit",
    )
    parser.add_argument(
        "--enable",
        type=str,
        metavar="LOOP",
        help="Enable a disabled loop",
    )
    parser.add_argument(
        "--disable",
        type=str,
        metavar="LOOP",
        help="Disable a loop",
    )
    parser.add_argument(
        "--configure",
        type=str,
        metavar="LOOP",
        help="Configure a loop (use with --budget)",
    )
    parser.add_argument(
        "--budget",
        type=int,
        help="Budget value for --configure",
    )
    parser.add_argument(
        "--promote",
        nargs=2,
        metavar=("LOOP", "CATEGORY"),
        help="Promote a loop to a new category",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Diagnose loop health issues",
    )
    parser.add_argument(
        "--history",
        nargs="?",
        const="__all__",
        metavar="LOOP",
        help="Show execution history for a loop (or all loops)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum history entries to print (default: 20)",
    )
    parser.add_argument(
        "--reset",
        type=str,
        metavar="LOOP",
        help="Reset trust state only for a loop",
    )
    args = parser.parse_args(_normalize_cli_args(argv if argv is not None else sys.argv[1:]))
    project_root = _resolve_execution_project_root(args)
    if args.run_all:
        _enforce_run_all_worktree(project_root)

    if args.drain and args.validate:
        parser.error("--drain and --validate are mutually exclusive")
    if (args.drain or args.validate) and not args.run:
        parser.error("--drain/--validate require --run LOOP")

    if args.manifest:
        manifest_root = _resolve_checkout_root_from_cwd()
        manifest = build_codex_schedule_manifest_from_project(manifest_root)
        schedule_states = detect_codex_schedule_states(row["id"] for row in manifest)
        manifest = build_codex_schedule_manifest_from_project(
            manifest_root,
            schedule_states=schedule_states,
        )
        print(
            yaml.safe_dump(
                {"schedules": manifest},
                sort_keys=False,
            )
        )
        return

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    config = load_config()
    if not config.get("engine", {}).get("enabled", False):
        logger.info("Adaptive Loop Engine is disabled in config")
        if args.loop:
            # Stay alive but idle when running as daemon child
            while RUNNING:
                time.sleep(60)
        return

    runtime_dir = get_runtime_dir()

    engine = AdaptiveLoopEngine(config, runtime_dir=runtime_dir, project_root=project_root)

    # Propagate --local flag to engine for OpsContext injection
    if args.local:
        engine._local_client = "ollama"

    if args.diagnose:
        if args.fix:
            raise SystemExit("--fix is only supported with --heal")
        _hydrate_persisted_dynamic_categories_for_read_only(engine)
        journal_entries = [
            _journal_entry_to_dict(entry) for entry in engine.journal_reader.read_all()
        ]
        print(_format_diagnostics(engine.ledger.diagnose(journal_entries)))
        return

    if args.history:
        entries = [
            _journal_entry_to_dict(entry) for entry in engine.journal_reader.read_all()
        ]
        loop_name = (
            None
            if args.history == "__all__"
            else _require_read_only_loop(engine, args.history, entries)
        )
        if loop_name is not None:
            entries = [entry for entry in entries if entry.get("loop") == loop_name]
        if args.limit > 0:
            entries = entries[-args.limit:]
        if not entries:
            print("No history entries found")
            return
        for entry in entries:
            print(json.dumps(entry, sort_keys=False))
        return

    # Discover and register all auto-commands from SKILL.md frontmatter (ADR-200)
    discovery_t0 = time.monotonic()
    registry = discover_auto_commands(project_root)
    _annotate_orchestrator_runner_markers(registry)
    engine.register_auto_commands(
        registry,
        persist=_registration_should_persist(args),
    )
    discovery_duration_ms = int((time.monotonic() - discovery_t0) * 1000)
    logger.info(
        "Discovered %d auto-commands across %d loops",
        len(registry),
        len({e.loop_name for e in registry.values()}),
    )

    if args.create_adr and not args.pending:
        args.pending = True

    # ADR-458: Show evolve queue and exit
    if args.evolve_pending:
        report = format_pending_report()
        print(report)
        return

    if args.registry:
        loop_names = _known_loop_names(engine)
        print(f"Registered loops ({len(loop_names)}):")
        for name in loop_names:
            print(f"  - {name}")
        return

    if args.enable:
        loop_name = _require_loop(engine, args.enable)
        engine.ledger.set_loop_enabled(loop_name, True)
        print(f"Enabled loop: {loop_name}")
        return

    if args.disable:
        loop_name = _require_loop(engine, args.disable)
        engine.ledger.set_loop_enabled(loop_name, False)
        print(f"Disabled loop: {loop_name}")
        return

    if args.configure:
        loop_name = _require_loop(engine, args.configure)
        if args.budget is None:
            raise SystemExit("configure requires --budget")
        if args.budget <= 0:
            raise SystemExit("budget must be a positive integer")
        engine.ledger.set_budget(loop_name, args.budget)
        print(f"Updated {loop_name} budget to {args.budget}")
        return

    if args.promote:
        loop_name, category = args.promote
        _require_category(engine, loop_name, category)
        engine.ledger.promote_category(loop_name, category)
        print(f"Promoted {category} in {loop_name}")
        return

    if args.reset:
        loop_name = _require_loop(engine, args.reset)
        engine.ledger.reset_loop(loop_name)
        print(f"Reset loop state: {loop_name}")
        return

    def _run_single_loop(loop_name: str):
        """Run one cycle. Returns (CycleReport | None, list[LoopResult])."""
        if loop_name in engine.loops:
            return None, engine.run_cycle(loop_name)
        if loop_name in engine._auto_loop_names:
            if loop_name == "self-heal":
                return _run_split_auto_loop(
                    engine,
                    loop_name,
                    include_triggers={"continuous"},
                    trigger_filter="continuous",
                )
            if loop_name == "knowledge-enrichment":
                return _run_split_auto_loop(
                    engine,
                    loop_name,
                    include_triggers={"nightly", "weekly"},
                )
            report = engine.run_auto_cycle(loop_name)
            return report, report.results
        valid = sorted(set(engine.loops.keys()) | engine._auto_loop_names)
        raise ValueError(
            f"Unknown loop '{loop_name}'. Valid loops: {', '.join(valid)}"
        )

    if args.run:
        if args.drain:
            if args.run not in {"command-evolution", "knowledge-enrichment"}:
                parser.error(f"--drain is not supported for loop '{args.run}'")
        if args.validate and args.run != "self-heal":
            parser.error(f"--validate is not supported for loop '{args.run}'")

        logger.info(f"Running single cycle for: {args.run}")
        run_start_iso = datetime.now(timezone.utc).isoformat()
        run_t0 = time.monotonic()
        drained_events = 0
        try:
            with _job_ledger_run(
                kind="loop",
                name=args.run,
                args={
                    "mode": "run",
                    "drain": args.drain,
                    "validate": args.validate,
                    "evolve": args.evolve,
                },
                timeout_s=_job_ledger_timeout_s(config),
            ) as _job:
                if _job is not None:
                    _job.phase("dispatch")
                if args.drain and args.run == "command-evolution":
                    drained_events = _consume_and_materialize_post_exec_events(engine)
                    report, results = _run_split_auto_loop(
                        engine,
                        "command-evolution",
                        include_triggers={"post-execution", "nightly"},
                        trigger_filter="post-execution",
                    )
                elif args.drain and args.run == "knowledge-enrichment":
                    drained_events = _consume_and_materialize_post_exec_events(engine)
                    report, results = _run_split_auto_loop(
                        engine,
                        "knowledge-enrichment",
                        include_triggers={"post-execution"},
                        trigger_filter="post-execution",
                    )
                elif args.validate and args.run == "self-heal":
                    report, results = _run_split_auto_loop(
                        engine,
                        "self-heal",
                        include_triggers={"nightly"},
                        trigger_filter="nightly",
                    )
                    _run_nightly_maintenance(engine, config)
                else:
                    report, results = _run_single_loop(args.run)
        except ValueError as e:
            parser.error(str(e))
        run_duration_ms = int((time.monotonic() - run_t0) * 1000)
        print_t0 = time.monotonic()
        if report:
            print(report.format())
            handoff = _format_wiki_compile_handoff(report)
            if handoff:
                print(handoff)
        if drained_events:
            logger.info("Materialized %d post-execution events", drained_events)
        for r in results:
            status = "OK" if r.success else "FAIL"
            logger.info(f"  [{status}] {r.action} ({r.category})")
        evolve_duration_ms = 0
        if args.evolve and report:
            evolve_duration_ms = run_evolve_phase(
                engine,
                project_root,
                run_start_iso,
                [report],
            )
        print_duration_ms = int((time.monotonic() - print_t0) * 1000)
        total_duration_ms = int((time.monotonic() - cli_t0) * 1000)
        metrics_path = write_cli_metrics(
            runtime_dir,
            "run",
            {
                "mode": "run",
                "target_loop": args.run,
                "evolve": args.evolve,
                "discovery_duration_ms": discovery_duration_ms,
                "run_duration_ms": run_duration_ms,
                "evolve_duration_ms": evolve_duration_ms,
                "print_duration_ms": print_duration_ms,
                "executor_overhead_ms": max(
                    0,
                    total_duration_ms - discovery_duration_ms - run_duration_ms - evolve_duration_ms - print_duration_ms,
                ),
                "total_duration_ms": total_duration_ms,
                "loop_report_duration_ms": report.duration_ms if report else 0,
                "result_count": len(results),
                "drained_events": drained_events,
            },
        )
        if metrics_path:
            logger.info("CLI metrics written: %s", metrics_path)
        return

    if args.run_all:
        total_cycles = max(1, args.cycles)
        loop_names = sorted(set(engine.loops.keys()) | engine._auto_loop_names)
        logger.info("Running %s cycle(s) for all loops (%d)", total_cycles, len(loop_names))
        reports = []
        loop_metrics: list[dict[str, Any]] = []
        # Capture start time for --evolve git inspection
        run_start_iso = datetime.now(timezone.utc).isoformat()
        run_t0 = time.monotonic()
        prev_issue_count = -1
        for cycle_idx in range(total_cycles):
            if total_cycles > 1:
                print(f"\n{'='*20} Cycle {cycle_idx + 1}/{total_cycles} {'='*20}\n")
            cycle_reports: list[CycleReport] = []
            for loop_name in loop_names:
                loop_t0 = time.monotonic()
                with _job_ledger_run(
                    kind="loop",
                    name=loop_name,
                    args={
                        "mode": "run-all",
                        "cycle": cycle_idx + 1,
                        "cycles": total_cycles,
                        "evolve": args.evolve,
                    },
                    timeout_s=_job_ledger_timeout_s(config),
                ) as _job:
                    if _job is not None:
                        _job.phase("dispatch")
                    report, results = _run_single_loop(loop_name)
                wrapper_duration_ms = int((time.monotonic() - loop_t0) * 1000)
                if report:
                    cycle_reports.append(report)
                if not results:
                    logger.info(f"  {loop_name}: no actions")
                else:
                    successes = sum(1 for r in results if r.success)
                    failures = len(results) - successes
                    logger.info(f"  {loop_name}: {successes} success, {failures} failure")
                loop_metrics.append(
                    {
                        "loop": loop_name,
                        "wrapper_duration_ms": wrapper_duration_ms,
                        "engine_duration_ms": report.duration_ms if report else 0,
                        "result_count": len(results),
                        "had_report": bool(report),
                    }
                )
            # End of per-loop iteration within a cycle
            reports.extend(cycle_reports)
            # Print cycle summary
            if cycle_reports:
                print(CycleReport.format_all(cycle_reports))
                for cycle_report in cycle_reports:
                    handoff = _format_wiki_compile_handoff(cycle_report)
                    if handoff:
                        print(handoff)
            # Early exit: if findings stabilized to 0 and not --force, stop
            cycle_issue_count = sum(
                r.total_actionable for r in cycle_reports if hasattr(r, 'total_actionable')
            )
            if total_cycles > 1 and cycle_issue_count == 0 and not args.force:
                print(f"\nFindings stabilized to 0 after cycle {cycle_idx + 1}. Stopping early.")
                break
            if total_cycles > 1 and cycle_issue_count == prev_issue_count and not args.force:
                print(f"\nFindings unchanged ({cycle_issue_count}) after cycle {cycle_idx + 1}. Stopping early.")
                break
            prev_issue_count = cycle_issue_count

        # Print full reports with trust deltas and difficulty changes
        run_duration_ms = int((time.monotonic() - run_t0) * 1000)
        print_t0 = time.monotonic()

        # --evolve: git inspection + self-improvement analysis + queue persistence (ADR-458)
        evolve_duration_ms = 0
        if args.evolve:
            evolve_duration_ms = run_evolve_phase(
                engine,
                project_root,
                run_start_iso,
                reports,
            )

        print_duration_ms = int((time.monotonic() - print_t0) * 1000)
        total_duration_ms = int((time.monotonic() - cli_t0) * 1000)
        metrics_path = write_cli_metrics(
            runtime_dir,
            "run-all-evolve" if args.evolve else "run-all",
            {
                "mode": "run-all-evolve" if args.evolve else "run-all",
                "evolve": args.evolve,
                "discovery_duration_ms": discovery_duration_ms,
                "run_duration_ms": run_duration_ms,
                "evolve_duration_ms": evolve_duration_ms,
                "print_duration_ms": print_duration_ms,
                "executor_overhead_ms": max(
                    0,
                    total_duration_ms - discovery_duration_ms - run_duration_ms - print_duration_ms,
                ),
                "total_duration_ms": total_duration_ms,
                "loop_count": len(loop_names),
                "loop_metrics": loop_metrics,
            },
        )
        if metrics_path:
            logger.info("CLI metrics written: %s", metrics_path)
        return

    if args.pending:
        pending_t0 = time.monotonic()
        pending, total_issues = scan_pending_issues(engine, config, project_root)
        pending_duration_ms = int((time.monotonic() - pending_t0) * 1000)
        print_t0 = time.monotonic()
        print_pending_report(pending, total_issues)
        if args.create_adr:
            adr_path = create_centralized_adr(project_root, pending, total_issues)
            print(f"Centralized ADR created: {adr_path}")
        print_duration_ms = int((time.monotonic() - print_t0) * 1000)
        total_duration_ms = int((time.monotonic() - cli_t0) * 1000)
        metrics_path = write_cli_metrics(
            runtime_dir,
            "pending",
            {
                "mode": "pending",
                "discovery_duration_ms": discovery_duration_ms,
                "pending_scan_duration_ms": pending_duration_ms,
                "print_duration_ms": print_duration_ms,
                "executor_overhead_ms": max(
                    0,
                    total_duration_ms - discovery_duration_ms - pending_duration_ms - print_duration_ms,
                ),
                "total_duration_ms": total_duration_ms,
                "total_pending_issues": total_issues,
                "commands_scanned": len(pending),
                "create_adr": bool(args.create_adr),
            },
        )
        if metrics_path:
            logger.info("CLI metrics written: %s", metrics_path)
        return

    if args.report:
        report_t0 = time.monotonic()
        print(engine.generate_report(days=args.days))
        report_duration_ms = int((time.monotonic() - report_t0) * 1000)
        total_duration_ms = int((time.monotonic() - cli_t0) * 1000)
        metrics_path = write_cli_metrics(
            runtime_dir,
            "report",
            {
                "mode": "report",
                "days": args.days,
                "discovery_duration_ms": discovery_duration_ms,
                "report_duration_ms": report_duration_ms,
                "executor_overhead_ms": max(
                    0,
                    total_duration_ms - discovery_duration_ms - report_duration_ms,
                ),
                "total_duration_ms": total_duration_ms,
            },
        )
        if metrics_path:
            logger.info("CLI metrics written: %s", metrics_path)
        return

    if args.heal:
        heal_t0 = time.monotonic()
        journal_entries = engine.journal_reader.read_all()
        findings = heal_detect(engine.ledger, journal_entries)
        if args.fix:
            output = format_heal_fix_report(
                heal_fix(
                    findings,
                    ledger=engine.ledger,
                    registry=registry,
                    project_root=project_root,
                    journal_entries=journal_entries,
                    force=args.force,
                )
            )
        else:
            output = format_heal_report(findings)
        print(output)
        heal_duration_ms = int((time.monotonic() - heal_t0) * 1000)
        total_duration_ms = int((time.monotonic() - cli_t0) * 1000)
        metrics_path = write_cli_metrics(
            runtime_dir,
            "heal-fix" if args.fix else "heal",
            {
                "mode": "heal-fix" if args.fix else "heal",
                "fix": bool(args.fix),
                "force": bool(args.force),
                "finding_count": len(findings),
                "discovery_duration_ms": discovery_duration_ms,
                "heal_duration_ms": heal_duration_ms,
                "executor_overhead_ms": max(
                    0,
                    total_duration_ms - discovery_duration_ms - heal_duration_ms,
                ),
                "total_duration_ms": total_duration_ms,
            },
        )
        if metrics_path:
            logger.info("CLI metrics written: %s", metrics_path)
        return

    if args.status:
        status_t0 = time.monotonic()
        print(format_status(engine, config))
        status_duration_ms = int((time.monotonic() - status_t0) * 1000)
        total_duration_ms = int((time.monotonic() - cli_t0) * 1000)
        metrics_path = write_cli_metrics(
            runtime_dir,
            "status",
            {
                "mode": "status",
                "discovery_duration_ms": discovery_duration_ms,
                "status_duration_ms": status_duration_ms,
                "executor_overhead_ms": max(
                    0,
                    total_duration_ms - discovery_duration_ms - status_duration_ms,
                ),
                "total_duration_ms": total_duration_ms,
            },
        )
        if metrics_path:
            logger.info("CLI metrics written: %s", metrics_path)
        return

    # Daemon loop mode
    logger.info("Adaptive Loop Engine starting in daemon mode")

    while RUNNING:
        # Hot-reload config each cycle (ADR-216)
        config = load_config()
        engine._config = config
        poll_interval_raw = config.get("engine", {}).get("poll_interval_seconds", 300)
        try:
            poll_interval = max(1, int(poll_interval_raw))
        except (TypeError, ValueError):
            poll_interval = 300

        # Run continuous loops
        try:
            with _job_ledger_run(
                kind="loop",
                name="adaptive-continuous",
                args={"mode": "daemon", "trigger": "continuous"},
                timeout_s=_job_ledger_timeout_s(config),
            ) as _job:
                if _job is not None:
                    _job.phase("dispatch")
                results = engine.run_all_by_trigger("continuous")
            for loop_name, loop_results in results.items():
                if loop_results:
                    successes = sum(1 for r in loop_results if r.success)
                    logger.debug(f"  continuous/{loop_name}: {successes} actions")
        except Exception as e:
            logger.warning(f"Continuous loop cycle failed: {e}")

        time.sleep(poll_interval)

    logger.info("Adaptive Loop Engine stopped")


if __name__ == "__main__":
    main()
